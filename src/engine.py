#!/usr/bin/python3
"""Project Largo: coordinated GNOME and application palettes using Noctalia."""
import argparse
import configparser
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import types
import xml.etree.ElementTree as ET

HOME = Path.home()
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
NOCTALIA = HOME / '.config/noctalia'
STATE = HOME / '.local/state/oma-theme'
INSTALL = STATE / 'baseline'
EXTENSION = 'user-theme@gnome-shell-extensions.gcampax.github.com'
RESOURCE = '/usr/share/gnome-shell/gnome-shell-theme.gresource'
SCHEMA = 'org.gnome.desktop.interface'


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, text=True,
                          capture_output=True, timeout=120, **kwargs).stdout


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def atomic(path, content):
    """Preserve writable symlink targets and avoid unchanged writes."""
    path = Path(path)
    if path.is_symlink():
        path = path.resolve(strict=True)
    content = content.encode() if isinstance(content, str) else content
    if path.exists() and path.read_bytes() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        os.fchmod(fd, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


def palettes():
    return {p.stem: p for p in sorted((NOCTALIA / 'palettes').glob('oma *.json'))}


def presets():
    return {'Vanilla Gnome': None, 'Vanilla Gnome Dark': None, **palettes()}


def remember_wallpaper(name):
    load_module('oma_wallpaper', ROOT / 'wallpaper.py').remember(types.SimpleNamespace(**globals()), name)


def restore_wallpaper(name):
    return load_module('oma_wallpaper', ROOT / 'wallpaper.py').restore(types.SimpleNamespace(**globals()), name)


def default_wallpaper(name):
    return load_module('oma_appearance', ROOT / 'appearance.py').default_wallpaper(types.SimpleNamespace(**globals()), name)


def rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def contrast(a, b):
    def luminance(color):
        channels = [n / 255 for n in rgb(color)]
        return sum(w * (v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4)
                   for w, v in zip((.2126, .7152, .0722), channels))
    a, b = sorted((luminance(a), luminance(b)))
    return (b + .05) / (a + .05)


def noctalia_settings():
    """Optional compatibility input; GNOME installs need no Noctalia session."""
    path = HOME / '.local/state/noctalia/settings.toml'
    try:
        text = path.read_text()
    except FileNotFoundError:
        return {}
    return tomllib.loads(text)


def niri_selection():
    # Noctalia remains the sole owner of Niri's saved palette.
    return noctalia_settings().get('theme', {})


def selection():
    path = STATE / 'gnome.json'
    return json.loads(path.read_text()) if path.exists() else {'palette': 'oma Gruvbox'}


def shell_css(tokens, stock, panel_background_role='shadow'):
    """Adapt stock GNOME 50 color constants; retain every native geometry rule."""
    def color(value):
        value = value.lower()
        channels = rgb(value)
        if value == '#000000':
            return value  # Physical shadows/scrims retain black.
        if max(channels) - min(channels) > 30:
            return tokens['terminal_normal_yellow' if channels[1] > 80 else 'error']
        if value == '#222226':
            return tokens['surface']
        if value in ('#2e2e33', '#333333', '#38383b'):
            return tokens['surface_container']
        if value == '#36363a':
            return tokens['surface_container_high']
        if max(channels) >= 200:
            return tokens['on_surface']
        if max(channels) >= 110:
            return tokens['on_surface_variant']
        return tokens['hover']

    # One substitution pass avoids accidentally mapping a generated color twice.
    pattern = r'#[0-9a-fA-F]{6}\b|rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)|-st-accent-fg-color|-st-accent-color'
    def replace(match):
        text = match[0]
        if text == '-st-accent-fg-color':
            return tokens['on_primary']
        if text == '-st-accent-color':
            return tokens['primary']
        if text.startswith('#'):
            return color(text)
        original = '#' + ''.join(f'{int(match[i]):02x}' for i in (1, 2, 3))
        converted = rgb(color(original))
        return 'rgba(' + ', '.join(map(str, converted)) + ', ' + match[4] + ')'
    css = re.sub(pattern, replace, stock)
    # Colored action backgrounds need the palette's paired foreground, not body text.
    css += '\n/* Oma semantic action pairs; native spacing and shapes are retained. */\n'
    css += f'''
.button.destructive-action, .button.destructive-action:hover,
.button.destructive-action:active {{ background-color: {tokens['error']}; color: {tokens['on_error']}; }}
StEntry {{ selection-background-color: {tokens['primary']}; selected-color: {tokens['on_primary']}; }}
'''
    if panel_background_role is not None:
        if panel_background_role not in ('surface', 'shadow'):
            raise ValueError('Unsupported GNOME panel background role: ' + str(panel_background_role))
        css += f'\n/* Palette-owned GNOME top bar background. */\n#panel {{ background-color: {tokens[panel_background_role]}; }}\n'
    return '/* Oma GNOME 50 palette adapter; regenerate with oma-theme. */\n' + css


def template_specs():
    # Existing user-owned sources are reused without running their compositor hooks.
    return [
        ('application-palette.json', '.local/state/noctalia/application-themes/palette.json'),
        ('roles-gtk3.css', '.config/gtk-3.0/noctalia.css'),
        ('roles-gtk4.css', '.config/gtk-4.0/noctalia.css'),
        ('opencode-transparent.json', '.config/opencode/themes/matugen-transparent.json'),
        ('opencode-transparent.json', '.config/opencode/themes/matugen.json'),
        ('roles-obsidian.css', '.local/state/project-largo/rendered/obsidian.css'),
        ('roles-zen-chrome.css', '.cache/noctalia/zen-browser/zen-userChrome.css'),
        ('roles-zen-content.css', '.cache/noctalia/zen-browser/zen-userContent.css'),
        ('zotero-pdf-theme.json', '.local/state/omarchy/current/theme/zotero-pdf-theme.json'),
        ('spotify-ziro.json', '.config/spicetify/Themes/marketplace/assets/noctalia-ziro.json'),
        ('yamis-colour.json', '.local/state/noctalia/yamis-colour.json'),
        ('libreoffice-colors.xcu', '.local/state/noctalia/libreoffice-theme-staging/Theme_Colors.xcu'),
        ('roles-fastfetch.jsonc', '.config/fastfetch/themes/noctalia.jsonc'),
    ]


def expand_output(value):
    for key, directory in {'XDG_CONFIG_HOME': HOME / '.config', 'XDG_STATE_HOME': HOME / '.local/state',
                           'XDG_CACHE_HOME': HOME / '.cache', 'XDG_DATA_HOME': HOME / '.local/share'}.items():
        value = value.replace('$' + key, str(directory))
    return Path(value.replace('~/', str(HOME) + '/'))


def check_render_dependencies(desktop):
    commands = [('/usr/bin/noctalia', 'Install the native Noctalia package (Fedora: sudo dnf install noctalia).')]
    if desktop == 'gnome':
        commands.append(('/usr/bin/gresource', 'Fedora: sudo dnf install glib2-devel'))
    for executable, hint in commands:
        if not os.access(executable, os.X_OK):
            raise ValueError('Missing required command: ' + executable + '. ' + hint)
    if not Path('/usr/share/noctalia/assets/templates/builtin.toml').is_file():
        raise ValueError('Missing native Noctalia template assets. Install/reinstall the native noctalia package.')
    if desktop == 'gnome' and not Path(RESOURCE).is_file():
        raise ValueError('Missing GNOME Shell theme resource: ' + RESOURCE + '. Install/reinstall gnome-shell.')


def stage_integrations(name, directory):
    """Render maintained adapter inputs without inspecting optional client configs.

    Setup must not depend on Fastfetch/Starship/Steam configuration being valid.
    The ordinary desktop stage retains its existing, broader output contract.
    """
    source = palettes().get(name)
    if source is None:
        raise ValueError('Unknown custom palette: ' + name)
    check_render_dependencies('applications')
    definition = json.loads(source.read_text())
    directory.mkdir(parents=True, exist_ok=True)
    needed = {'application-palette.json', 'roles-obsidian.css', 'roles-zen-chrome.css',
              'roles-zen-content.css', 'zotero-pdf-theme.json', 'libreoffice-colors.xcu'}
    specs = [(NOCTALIA / 'templates' / template, HOME / target)
             for template, target in template_specs() if template in needed]
    backend = load_module('largo_setup_renderer', ROOT / 'renderer.py').NoctaliaRenderer()
    tokens, rendered = backend.render(definition, [p for p, _ in specs], directory)
    for key, original in (('primary', 'mPrimary'), ('surface', 'mSurface'), ('on_surface', 'mOnSurface')):
        if tokens[key] != definition['dark'][original]:
            raise ValueError('Renderer changed palette role: ' + key)
    outputs = {}
    for index, (template, target) in enumerate(specs):
        value = rendered[index]
        if template.suffix == '.json':
            json.loads(value)
        elif template.suffix == '.xcu':
            ET.fromstring(value)
        outputs[target] = value
    app_renderer = load_module('largo_setup_css', NOCTALIA / 'application-themes/render.py')
    app_renderer.STATE = directory / 'apps'
    app_renderer.GTK = directory / 'home/.local/share/themes/Noctalia-LibreOffice/gtk-3.0'
    app_renderer.STATE.mkdir(exist_ok=True)
    (app_renderer.STATE / 'palette.json').write_bytes(outputs[HOME / '.local/state/noctalia/application-themes/palette.json'])
    app_renderer.render(home=directory / 'home')
    outputs[HOME / '.local/state/noctalia/application-themes/zotero.css'] = (app_renderer.STATE / 'zotero.css').read_bytes()
    for css in app_renderer.GTK.glob('*.css'):
        outputs[HOME / '.local/share/themes/Noctalia-LibreOffice/gtk-3.0' / css.name] = css.read_bytes()
    outputs[HOME / '.local/state/project-largo/rendered/tokens.json'] = (json.dumps(tokens, indent=2) + '\n').encode()
    return outputs, tokens


def stage_palette(name, directory, desktop='gnome'):
    source = palettes().get(name)
    if source is None:
        raise ValueError('Unknown palette: ' + name)
    check_render_dependencies(desktop)
    definition = json.loads(source.read_text())
    original = definition['dark']
    directory.mkdir(parents=True, exist_ok=True)
    # Both maps support templates with legacy dark/light compatibility branches.
    palette = directory / 'input.json'
    palette.write_text(json.dumps({'dark': original, 'light': original}))
    specs = [(NOCTALIA / 'templates' / template, target) for template, target in template_specs()]
    specs += [
        (Path('/usr/share/noctalia/assets/templates/kitty/kitty.conf'), '.config/kitty/themes/noctalia.conf'),
        (NOCTALIA / 'role-adapters/codex.tmTheme', '.codex/themes/noctalia.tmTheme'),
        (NOCTALIA / 'codex-appearance/palette.json.tpl', '.config/noctalia/codex-appearance/palette.json'),
    ]
    builtin_root = Path('/usr/share/noctalia/assets/templates')
    builtin = tomllib.loads((builtin_root / 'builtin.toml').read_text())['templates']
    # Integration configuration belongs to Largo. Noctalia session settings are
    # optional inputs only for Niri selection and historical wallpaper pairings.
    import integrations
    enabled = integrations.Context(HOME).config().get('templates', ['alacritty', 'btop', 'foot', 'helix', 'starship'])
    for name in ('alacritty', 'btop', 'foot', 'helix', 'starship'):
        entry = builtin[name]
        target = expand_output(entry['output_path'])
        if name in enabled and target.is_file():
            specs.append((builtin_root / entry['input_path'], str(target)))
    steam = HOME / '.local/state/noctalia/community-templates/steam'
    if (steam / 'template.toml').is_file():
        steam_config = tomllib.loads((steam / 'template.toml').read_text())['templates']['steam']
        steam_target = expand_output(steam_config['output_path'])
        if steam_target.is_file():
            specs.append((steam / steam_config['input_path'], str(steam_target)))
    backend = load_module('largo_renderer', ROOT / 'renderer.py').NoctaliaRenderer()
    tokens, artifacts = backend.render(definition, [template for template, _ in specs], directory)
    for key, value in tokens.items():
        if not re.fullmatch(r'#[\da-fA-F]{6}', value):
            raise ValueError('Invalid rendered token: ' + key)
    for key, original_key in [('primary', 'mPrimary'), ('surface', 'mSurface'), ('on_surface', 'mOnSurface')]:
        assert tokens[key] == original[original_key]
    outputs = {}
    for index, (template, target) in enumerate(specs):
        path = directory / f'{index}-{template.name}'
        text = artifacts[index].decode()
        if '{{' in text:
            raise ValueError('Unresolved template: ' + template.name)
        if template.suffix == '.json' or template.name.endswith('.json.tpl'):
            json.loads(text)
        if template.suffix in ('.xcu', '.tmTheme'):
            ET.fromstring(text)
        if template.suffix == '.toml':
            tomllib.loads(text)
        if target:
            outputs[HOME / target] = text.encode()
    outputs[HOME / '.local/state/project-largo/rendered/tokens.json'] = (json.dumps(tokens, indent=2) + '\n').encode()
    renderer = load_module('oma_apps', NOCTALIA / 'application-themes/render.py')
    renderer.STATE = directory / 'apps'
    renderer.GTK = directory / 'home/.local/share/themes/Noctalia-LibreOffice/gtk-3.0'
    renderer.STATE.mkdir(exist_ok=True)
    (renderer.STATE / 'palette.json').write_bytes(outputs[HOME / '.local/state/noctalia/application-themes/palette.json'])
    renderer.render(home=directory / 'home')
    for path in renderer.STATE.glob('*.css'):
        outputs[HOME / '.local/state/noctalia/application-themes' / path.name] = path.read_bytes()
    for path in (directory / 'home').rglob('*'):
        if path.is_file():
            outputs[HOME / path.relative_to(directory / 'home')] = path.read_bytes()
    fastfetch = HOME / '.config/fastfetch/config.jsonc'
    if fastfetch.exists():
        adapter = load_module('oma_fastfetch', NOCTALIA / 'role-adapters/fastfetch.py')
        colors = json.loads(outputs[HOME / '.config/fastfetch/themes/noctalia.jsonc'])
        outputs[fastfetch] = adapter.merge(fastfetch.read_text(), colors).encode()
    starship = Path(os.environ.get('STARSHIP_CONFIG', HOME / '.config/starship.toml')).expanduser()
    starship_palette = HOME / '.cache/noctalia/starship-palette.toml'
    if starship.exists() and starship_palette in outputs:
        text = starship.read_text()
        pattern = r'(?ms)(^# >>> NOCTALIA STARSHIP PALETTE >>>\n).*?(^# <<< NOCTALIA STARSHIP PALETTE <<<$)'
        updated, count = re.subn(pattern, lambda match: match[1] + outputs[starship_palette].decode().rstrip() + '\n' + match[2], text)
        if count == 1:
            before, after = tomllib.loads(text), tomllib.loads(updated)
            before.get('palettes', {}).pop('noctalia', None)
            after.get('palettes', {}).pop('noctalia', None)
            if before != after:
                raise ValueError('Unexpected Starship configuration change')
            outputs[starship] = updated.encode()
    # Profile publication belongs to guarded adapters, never to the renderer.
    if desktop == 'gnome':
        version = run(['/usr/bin/gnome-shell', '--version']).strip()
        if not re.search(r'\b50\.', version):
            raise ValueError('Shell adapter requires GNOME 50; review it for ' + version)
        stock = run(['/usr/bin/gresource', 'extract', RESOURCE, '/org/gnome/shell/theme/gnome-shell-dark.css'])
        css = shell_css(tokens, stock, definition.get('_gnome_panel_background_role', 'shadow'))
        (directory / 'gnome-shell.css').write_text(css)
        for slot in ('a', 'b'):
            outputs[HOME / f'.local/share/themes/Oma-GNOME-{slot}/gnome-shell/gnome-shell.css'] = css.encode()
    pairs = [('on_surface', 'surface'), ('on_surface', 'surface_container'),
             ('on_surface_variant', 'surface_container'), ('on_primary', 'primary'),
             ('on_error', 'error'), ('on_hover', 'hover'),
             ('terminal_normal_green', 'surface_container'), ('terminal_normal_yellow', 'surface_container')]
    contrasts = {a + '/' + b: contrast(tokens[a], tokens[b]) for a, b in pairs}
    if min(contrasts.values()) < 4.5:
        raise ValueError('Text contrast below 4.5:1: ' + str(contrasts))
    return outputs, tokens, contrasts


def settings_objects():
    from gi.repository import Gio
    result = {SCHEMA: Gio.Settings.new(SCHEMA)}
    result['org.gnome.desktop.background'] = Gio.Settings.new('org.gnome.desktop.background')
    directory = HOME / '.local/share/gnome-shell/extensions' / EXTENSION / 'schemas'
    source = Gio.SettingsSchemaSource.get_default()
    for directory in (HOME / '.local/share/gnome-shell/extensions' / EXTENSION / 'schemas',
                      Path('/usr/share/gnome-shell/extensions') / EXTENSION / 'schemas'):
        if (directory / 'gschemas.compiled').is_file():
            source = Gio.SettingsSchemaSource.new_from_directory(str(directory), source, False)
    schema = source.lookup('org.gnome.shell.extensions.user-theme', False)
    if schema is None:
        raise ValueError('Install GNOME User Themes for GNOME 50 before applying a palette.')
    result['org.gnome.shell.extensions.user-theme'] = Gio.Settings.new_full(schema, None, None)
    return result


def capture_settings():
    settings = settings_objects()
    keys = {SCHEMA: ['gtk-theme', 'color-scheme', 'accent-color', 'icon-theme',
                     'font-name', 'document-font-name', 'monospace-font-name'],
            'org.gnome.desktop.background': ['picture-uri', 'picture-uri-dark', 'picture-options'],
            'org.gnome.shell.extensions.user-theme': ['name']}
    return {schema: {key: obj.get_value(key).print_(True) for key in keys[schema]}
            for schema, obj in settings.items()}


def shell_status():
    from gi.repository import Gio, GLib
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        value = bus.call_sync('org.gnome.Shell', '/org/gnome/Shell', 'org.gnome.Shell.Extensions',
                              'GetExtensionInfo', GLib.Variant('(s)', (EXTENSION,)),
                              None, Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
        return {'active': value.get('state') == 1, 'state': value.get('state'),
                'error': value.get('error', ''), 'version': value.get('version')}
    except GLib.Error as error:
        return {'active': False, 'error': str(error)}


def restore_settings(values):
    from gi.repository import Gio, GLib
    for schema, keys in values.items():
        obj = settings_objects()[schema]
        for key, value in keys.items():
            obj.set_value(key, GLib.Variant.parse(None, value, None, None))
    Gio.Settings.sync()


def snapshot(directory, paths):
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    manifest = directory / 'files.json'
    records = json.loads(manifest.read_text()) if manifest.exists() else []
    captured = {record['path'] for record in records}
    for path in sorted(set(paths)):
        if path.is_symlink():
            target = path.resolve(strict=True)
        else:
            target = path
        if str(target) in captured:
            continue
        index = len(records)
        exists = target.is_file()
        if exists:
            shutil.copy2(target, directory / str(index))
        records.append({'path': str(target), 'exists': exists, 'file': str(index)})
    manifest.write_text(json.dumps(records, indent=2))
    if not (directory / 'settings.json').exists():
        (directory / 'settings.json').write_text(json.dumps(capture_settings(), indent=2))


def restore_snapshot(directory):
    for record in json.loads((directory / 'files.json').read_text()):
        path = Path(record['path'])
        if record['exists']:
            atomic(path, (directory / record['file']).read_bytes())
        else:
            path.unlink(missing_ok=True)
    restore_settings(json.loads((directory / 'settings.json').read_text()))


def appearance(tokens, name, desktop, restore=False):
    from gi.repository import Gio
    settings = settings_objects()
    obj = settings[SCHEMA]
    obj.set_string('gtk-theme', 'adw-gtk3-dark')
    obj.set_string('color-scheme', 'prefer-dark')
    # Standard GNOME accent is a fallback for clients that ignore custom CSS.
    accents = {'blue': '#3584e4', 'teal': '#2190a4', 'green': '#3a944a', 'yellow': '#c88800',
               'orange': '#ed5b00', 'red': '#e62d42', 'pink': '#d56199', 'purple': '#9141ac', 'slate': '#6f8396'}
    closest = min(accents, key=lambda key: sum((a - b) ** 2 for a, b in zip(rgb(tokens['primary']), rgb(accents[key]))))
    obj.set_string('accent-color', closest)
    if desktop == 'gnome':
        theme = settings['org.gnome.shell.extensions.user-theme']
        current = theme.get_string('name')
        theme.set_string('name', 'Oma-GNOME-b' if current == 'Oma-GNOME-a' else 'Oma-GNOME-a')
        if not restore_wallpaper(name) and (not restore or not (STATE / 'gnome.json').exists()):
            native = noctalia_settings()
            favorite = next((item['path'] for item in native.get('wallpaper', {}).get('favorite', [])
                             if item.get('custom_palette') == name and Path(item['path']).is_file()), None)
            if favorite:
                for key in ('picture-uri', 'picture-uri-dark'):
                    settings['org.gnome.desktop.background'].set_string(key, Path(favorite).as_uri())
            else:
                default_wallpaper(name)
        load_module('oma_appearance', ROOT / 'appearance.py').enroll_icons(types.SimpleNamespace(**globals()))
    Gio.Settings.sync()


def refresh_apps(changed_paths=()):
    """Application refreshes are best effort; their failures are visible in status."""
    hooks = [
        ('icons', ['/usr/bin/python3', NOCTALIA / 'yamis-colour.py']),
        ('kitty', ['/usr/bin/bash', '/usr/share/noctalia/assets/templates/kitty/apply.sh']),
        ('codex', ['/usr/bin/python3', NOCTALIA / 'codex-appearance/sync.py', '--mode', 'dark']),
    ]
    spicetify = HOME / '.spicetify/spicetify'
    if spicetify.exists():
        action = 'apply' if (STATE / 'vanilla-suspended/applied.json').exists() or (STATE / 'spotify-needs-apply').exists() else 'refresh'
        hooks.append(('spotify', [spicetify, '-q', action, '--no-restart']))
    if (HOME / '.config/btop/btop.conf').exists():
        hooks.append(('btop', ['/usr/bin/bash', '/usr/share/noctalia/assets/templates/btop/apply.sh']))
    previous_path = STATE / 'last-application.json'
    previous = json.loads(previous_path.read_text()).get('hooks', {}) if previous_path.exists() else {}
    inputs = {
        'icons': HOME / '.local/state/noctalia/yamis-colour.json',
        'kitty': HOME / '.config/kitty/themes/noctalia.conf',
        'codex': NOCTALIA / 'codex-appearance/palette.json',
        'libreoffice': HOME / '.local/state/noctalia/libreoffice-theme-staging/Theme_Colors.xcu',
        'office-scheme': HOME / '.local/state/noctalia/libreoffice-theme-staging/Theme_Colors.xcu',
        'spotify': HOME / '.config/spicetify/Themes/marketplace/assets/noctalia-ziro.json',
        'btop': HOME / '.config/btop/themes/noctalia.theme',
    }
    results = {}
    for name, command in hooks:
        if (not inputs[name].is_file() or
            (name == 'codex' and not (HOME / '.codex/config.toml').is_file()) or
            (name == 'libreoffice' and not (HOME / '.config/libreoffice').exists()
             and not (HOME / '.var/app/org.libreoffice.LibreOffice').exists())):
            results[name] = {'ok': True, 'skipped': True, 'detail': 'Application integration is not configured'}
            continue
        digest = hashlib.sha256(inputs[name].read_bytes()).hexdigest()
        prior = previous.get(name, {})
        skip = prior.get('ok') and not prior.get('pending') and prior.get('sha256') == digest and inputs[name] not in changed_paths
        if name == 'icons':
            from gi.repository import Gio
            selected = Gio.Settings.new(SCHEMA).get_string('icon-theme')
            marker = HOME / '.local/share/icons' / selected / '.noctalia-accent'
            expected = json.loads(inputs[name].read_text())['accent']
            skip = marker.exists() and marker.read_text().strip() == expected
        if name == 'spotify' and ((STATE / 'vanilla-suspended/applied.json').exists() or (STATE / 'spotify-needs-apply').exists()):
            skip = False
        if skip:
            results[name] = dict(prior, skipped=True, sha256=digest, ok=True)
            continue
        try:
            process = subprocess.run([str(arg) for arg in command], capture_output=True, text=True, timeout=60, check=True)
            output = (process.stdout + process.stderr).strip()
            results[name] = {'ok': True, 'detail': output[-2500:], 'sha256': digest,
                             'pending': 'skipping extension install' in output or 'deferred until reopen' in output}
            if name == 'spotify':
                (STATE / 'spotify-needs-apply').unlink(missing_ok=True)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            results[name] = {'ok': False, 'detail': str(getattr(error, 'stderr', '') or error)[-2500:]}
    return results


def refresh_integrations(palette=None, explicit=True):
    import integrations
    context = integrations.Context(HOME)
    if not context.registry():
        return {}
    selected = palette or selection()['palette']
    with integrations.locked(context):
        cached = context.current_artifacts()
        # Refresh the diagnostic artifact snapshot from this palette's already
        # published outputs; setup snapshots are never an authority for readiness.
        for path in cached:
            if path.is_file():
                cached[path] = path.read_bytes()
        atomic(context.state / 'artifacts.json', integrations.json_bytes({str(p): v.hex() for p, v in cached.items()}))
        report = integrations.execute(context, 'apply', palette=selected, enrolled_only=True,
                                      skip_apps=() if explicit else ('gdm',))
        atomic(context.state / 'last-results.json', json.dumps(report, indent=2) + '\n')
    return {'integration:' + row['target']: dict(ok=row['state'] != 'Failed',
            pending=row['state'] not in ('Ready', 'Not installed'), detail=row['detail'], state=row['state'])
            for row in report['results']}


def validate_css(directory, shell=True):
    for version in ('3.0', '4.0'):
        run(['/usr/bin/python3', ROOT / 'validate-css.py', version, directory])
    if shell:
        env = dict(os.environ)
        env['GI_TYPELIB_PATH'] = '/usr/lib64/gnome-shell:/usr/lib64/mutter-18'
        env['LD_LIBRARY_PATH'] = '/usr/lib64/gnome-shell:/usr/lib64/mutter-18'
        run(['/usr/bin/python3', ROOT / 'validate-css.py', 'shell', directory], env=env)


def _apply_custom(name, desktop='gnome', restore=False):
    STATE.mkdir(parents=True, exist_ok=True)
    with contextlib.nullcontext():
        with tempfile.TemporaryDirectory(prefix='render-', dir=STATE) as temporary:
            outputs, tokens, contrasts = stage_palette(name, Path(temporary), desktop)
            validate_css(Path(temporary), shell=desktop == 'gnome')
            extra = [HOME / f'.config/gtk-{version}.0/settings.ini' for version in (3, 4)]
            # Helpers below update only application appearance; keep recovery copies private.
            extra += [HOME / '.codex/config.toml', HOME / '.config/kitty/kitty.conf',
                      HOME / '.config/btop/btop.conf', STATE / 'gnome.json']
            for slot in ('a', 'b'):
                outputs.pop(HOME / f'.local/share/themes/Oma-GNOME-{slot}/gnome-shell/gnome-shell.css', None)
            if desktop == 'gnome':
                active = settings_objects()['org.gnome.shell.extensions.user-theme'].get_string('name')
                slot = 'b' if active == 'Oma-GNOME-a' else 'a'
                outputs[HOME / f'.local/share/themes/Oma-GNOME-{slot}/gnome-shell/gnome-shell.css'] = (Path(temporary) / 'gnome-shell.css').read_bytes()
            snapshot(INSTALL / 'application-before', list(outputs) + extra)
            transaction = STATE / 'transactions' / str(time.time_ns())
            snapshot(transaction, list(outputs) + extra)
            before = selection()
            try:
                changed_paths = {path for path, content in outputs.items() if atomic(path, content)}
                changed = len(changed_paths)
                appearance(tokens, name, desktop, restore)
            except Exception:
                restore_snapshot(transaction)
                raise
            results = refresh_apps(changed_paths)
            results.update(refresh_integrations(name, explicit=not restore))
            record = {'palette': name, 'desktop': desktop, 'changed_files': changed,
                      'minimum_contrast': min(contrasts.values()), 'hooks': results,
                      'transaction': str(transaction), 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
            if desktop == 'gnome':
                record['previous_palette'] = before.get('palette') if before.get('palette') != name else before.get('previous_palette', name)
                record['shell_extension'] = shell_status()
                atomic(STATE / 'gnome.json', json.dumps(record, indent=2) + '\n')
                remember_wallpaper(name)
            atomic(STATE / 'last-application.json', json.dumps(record, indent=2) + '\n')
            old = sorted((STATE / 'transactions').iterdir())[:-2]
            for directory in old:
                shutil.rmtree(directory)
            print(json.dumps(record, indent=2))


def apply(name, desktop='gnome', restore=False):
    vanilla = load_module('oma_vanilla', ROOT / 'vanilla.py')
    engine = types.SimpleNamespace(**globals())
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'apply.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if name not in presets():
            raise ValueError('Unknown preset: ' + name)
        if desktop == 'gnome' and not restore and (STATE / 'gnome.json').exists():
            remember_wallpaper(selection()['palette'])
        if name in vanilla.NAMES:
            if desktop != 'gnome':
                raise ValueError('Vanilla Gnome is a GNOME-only preset')
            vanilla.apply_default(engine, restore, name=name)
            return
        outputs = vanilla.resume_plan(engine)
        if not outputs:
            _apply_custom(name, desktop, restore)
            return
        recovery = STATE / 'resume-recovery' / str(time.time_ns())
        snapshot(recovery, list(outputs))
        try:
            vanilla.publish(engine, outputs)
            saved = json.loads((STATE / 'vanilla-suspended/settings.json').read_text())
            if desktop == 'niri':
                saved = {schema: values for schema, values in saved.items() if schema == SCHEMA}
            restore_settings(saved)
            _apply_custom(name, desktop, restore)
        except Exception:
            restore_snapshot(recovery)
            raise
        else:
            last = STATE / 'vanilla-last-suspended'
            if last.exists():
                shutil.rmtree(last)
            (STATE / 'vanilla-suspended').rename(last)
        finally:
            shutil.rmtree(recovery)


def restore_niri():
    # ExecStartPre runs before the compositor; no GNOME Shell setting is changed.
    selected = niri_selection()
    if selected.get('source') == 'custom' and selected.get('mode') == 'dark':
        apply(selected['custom_palette'], 'niri', restore=True)
    else:
        print('Niri uses a non-custom/dark palette; its native Noctalia startup owns restoration')


def main():
    if sys.argv[1:2] == ['integrations']:
        import integrations
        raise SystemExit(integrations.main(sys.argv[2:], types.SimpleNamespace(**globals())))
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('list')
    sub.add_parser('status')
    sub.add_parser('integrations', help='Application setup, status, repair and restoration')
    sub.add_parser('pick')
    sub.add_parser('restore-gnome')
    sub.add_parser('restore-niri')
    sub.add_parser('rollback')
    sub.add_parser('wallpaper-default')
    command = sub.add_parser('apply')
    command.add_argument('palette')
    command = sub.add_parser('verify')
    command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'list':
        print('\n'.join(presets()))
    elif args.action == 'status':
        niri = niri_selection()
        print(json.dumps({'gnome': selection(), 'shell_extension': shell_status(), 'niri': {key: niri.get(key) for key in
                         ('source', 'mode', 'custom_palette', 'builtin', 'community_palette')}}, indent=2))
    elif args.action == 'verify':
        results = []
        for name in palettes():
            directory = args.output / name
            _, _, contrasts = stage_palette(name, directory)
            validate_css(directory)
            results.append({'palette': name, 'contrasts': contrasts})
            print(name, 'PASS', round(min(contrasts.values()), 2))
        atomic(args.output / 'results.json', json.dumps(results, indent=2) + '\n')
    elif args.action == 'restore-niri':
        restore_niri()
    elif args.action == 'pick':
        os.execv('/usr/bin/python3', ['/usr/bin/python3', str(ROOT / 'picker.py')])
    elif args.action == 'wallpaper-default':
        if 'gnome' not in os.environ.get('XDG_CURRENT_DESKTOP', '').lower().split(':'):
            raise ValueError('Use GNOME for this action.')
        with (STATE / 'apply.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            name = selection()['palette']
            if not default_wallpaper(name):
                raise ValueError('No bundled default wallpaper for ' + name)
            remember_wallpaper(name)
            from gi.repository import Gio
            Gio.Settings.sync()
            print('Restored bundled default wallpaper for ' + name)
    else:
        desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower().split(':')
        if 'gnome' not in desktop:
            raise SystemExit('Use GNOME for this action. Niri keeps its native Noctalia palette picker.')
        name = args.palette if args.action == 'apply' else selection()['palette']
        if args.action == 'rollback':
            name = selection().get('previous_palette', name)
        apply(name, restore=args.action == 'restore-gnome')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        if getattr(error, 'stderr', None):
            print(error.stderr, file=sys.stderr)
        raise SystemExit(1)
