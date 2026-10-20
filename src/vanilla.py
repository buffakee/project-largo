#!/usr/bin/python3
"""Suspend theme overrides reversibly; Vanilla is a mode, not another color palette."""
import copy
import hashlib
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

NAME = 'Vanilla Gnome'
DARK_NAME = 'Vanilla Gnome Dark'
NAMES = (NAME, DARK_NAME)


def active():
    if 'gnome' not in os.environ.get('XDG_CURRENT_DESKTOP', '').lower().split(':'):
        return False
    path = Path.home() / '.local/state/oma-theme/gnome.json'
    return path.exists() and json.loads(path.read_text()).get('palette') in NAMES


def setting(text, key, value, section=None):
    pattern = r'(?m)^' + re.escape(key) + r'\s*=.*$'
    updated, count = re.subn(pattern, lambda _: key + '=' + value, text)
    if not count:
        if section:
            updated = updated.replace('[' + section + ']', '[' + section + ']\n' + key + '=' + value, 1)
        else:
            updated = key + '=' + value + '\n' + updated
    return updated


def plan(e, directory, dark=False):
    from gi.repository import Gio
    original = e.selection()
    name = original.get('palette')
    if name in NAMES:
        name = original.get('previous_palette', 'oma Gruvbox')
    if name not in e.palettes():
        name = 'oma Gruvbox'
    generated, _, _ = e.stage_palette(name, directory, desktop='niri')
    outputs = {path: b'/* Vanilla Gnome: no palette override. */\n'
               for path in generated if path.suffix == '.css'}
    for relative in ('.config/kitty/themes/noctalia.conf', '.config/alacritty/themes/noctalia.toml',
                     '.config/foot/themes/noctalia'):
        path = e.HOME / relative
        if path.exists():
            outputs[path] = b''
    outputs[e.HOME / '.local/state/omarchy/current/theme/colors.toml'] = None
    outputs[e.HOME / '.local/state/omarchy/current/theme/zotero-pdf-theme.json'] = b'{"enabled":false}\n'
    for version in (3, 4):
        path = e.HOME / f'.config/gtk-{version}.0/settings.ini'
        text = path.read_text() if path.exists() else '[Settings]\n'
        for key, value in {'gtk-theme-name': 'Adwaita-dark' if dark and version == 3 else 'Adwaita', 'gtk-icon-theme-name': 'Adwaita',
                           'gtk-application-prefer-dark-theme': 'true' if dark else 'false',
                           'gtk-font-name': Gio.Settings.new(e.SCHEMA).get_default_value('font-name').unpack()}.items():
            text = setting(text, key, value, 'Settings')
        outputs[path] = text.encode()
    for version in (5, 6):
        path = e.HOME / f'.config/qt{version}ct/qt{version}ct.conf'
        if path.exists():
            outputs[path] = setting(path.read_text(), 'custom_palette', 'false', 'Appearance').encode()
    # Application profiles are suspended by guarded, independently recoverable adapters.
    tui = e.HOME / '.config/opencode/tui.json'
    if tui.exists():
        data = json.loads(tui.read_text())
        data.pop('theme', None)
        outputs[tui] = (json.dumps(data, indent=2) + '\n').encode()
    codex = e.HOME / '.codex/config.toml'
    if codex.exists():
        text = codex.read_text()
        expected = copy.deepcopy(tomllib.loads(text))
        desktop = expected.get('desktop', {})
        for key in ('appearanceTheme', 'appearanceDarkChromeTheme', 'appearanceLightChromeTheme'):
            desktop.pop(key, None)
        # Remove only appearance tables/keys; never print any other configuration.
        text = re.sub(r'(?ms)^\[desktop\.appearance(?:Dark|Light)ChromeTheme(?:\.[^\]]+)?\][^\n]*\n.*?(?=^\[|\Z)', '', text)
        def remove_key(text, table, key):
            pattern = r'(?ms)(^\[' + re.escape(table) + r'\][^\n]*\n)(.*?)(?=^\[|\Z)'
            return re.sub(pattern, lambda match: match[1] + re.sub(r'(?m)^' + re.escape(key) + r'\s*=.*\n?', '', match[2]), text)
        text = remove_key(text, 'desktop', 'appearanceTheme')
        if expected.get('tui', {}).get('theme') == 'noctalia':
            expected['tui'].pop('theme')
            text = remove_key(text, 'tui', 'theme')
        if tomllib.loads(text) != expected:
            raise ValueError('Unexpected non-theme Codex configuration change')
        outputs[codex] = text.encode()
    fastfetch = e.HOME / '.config/fastfetch/config.jsonc'
    if fastfetch.exists():
        text = re.sub(r'\s*// BEGIN NOCTALIA ROLE COLORS.*?// END NOCTALIA ROLE COLORS\n?', '\n', fastfetch.read_text(), flags=re.S)
        outputs[fastfetch] = text.encode()
    starship = Path(os.environ.get('STARSHIP_CONFIG', e.HOME / '.config/starship.toml')).expanduser()
    if starship.exists():
        text = re.sub(r'(?ms)^# >>> NOCTALIA STARSHIP PALETTE >>>\n.*?^# <<< NOCTALIA STARSHIP PALETTE <<<\n?', '', starship.read_text())
        text = re.sub(r'(?m)^palette\s*=\s*["\']noctalia["\']\s*\n?', '', text)
        tomllib.loads(text)
        outputs[starship] = text.encode()
    btop = e.HOME / '.config/btop/btop.conf'
    if btop.exists():
        outputs[btop] = setting(btop.read_text(), 'color_theme', '"Default"').encode()
    # YAMIS-only aliases have no Adwaita counterpart; use each web app's original icon.
    for launcher in (e.HOME / '.local/share/applications').glob('org.chromium.Chromium.chrome-*-Default.desktop'):
        icon_name = launcher.stem.removeprefix('org.chromium.Chromium.')
        icon = e.HOME / '.var/app/org.chromium.Chromium/data/icons/hicolor/512x512/apps' / (icon_name + '.png')
        if icon.is_file():
            outputs[launcher] = setting(launcher.read_text(), 'Icon', str(icon), 'Desktop Entry').encode()
    return outputs


def json_restore(before, base, current):
    """Undo our semantic JSON edits while retaining unrelated subsequent settings."""
    if before == base:
        return current
    if isinstance(before, dict) and isinstance(base, dict) and isinstance(current, dict):
        result = copy.deepcopy(current)
        for key in before.keys() | base.keys():
            if before.get(key) == base.get(key) and (key in before) == (key in base):
                continue
            if key not in before:
                result.pop(key, None)
            elif key not in base:
                result[key] = copy.deepcopy(before[key])
            else:
                result[key] = json_restore(before[key], base[key], current.get(key))
        return result
    if all(isinstance(value, list) for value in (before, base, current)):
        result = [value for value in current if value not in base or value in before]
        return result + [value for value in before if value not in base and value not in result]
    return copy.deepcopy(before)


def resume_plan(e):
    directory = e.STATE / 'vanilla-suspended'
    manifest = directory / 'applied.json'
    if not manifest.exists():
        return {}
    before = {record['path']: record for record in json.loads((directory / 'files.json').read_text())}
    outputs = {}
    for record in json.loads(manifest.read_text()):
        path = Path(record['path'])
        previous = before[str(path)]
        original = (directory / previous['file']).read_bytes() if previous['exists'] else None
        default = (directory / ('default-' + previous['file'])).read_bytes() if record['exists'] else None
        current = path.read_bytes() if path.exists() else None
        if current == default:
            outputs[path] = original
        elif original == default:
            continue
        elif path.suffix == '.json' and all(value is not None for value in (original, default, current)):
            data = json_restore(json.loads(original), json.loads(default), json.loads(current))
            outputs[path] = (json.dumps(data, indent=2) + '\n').encode()
        elif all(value is not None for value in (original, default, current)):
            with tempfile.TemporaryDirectory(dir=e.STATE, prefix='merge-') as temporary:
                paths = [Path(temporary) / name for name in ('current', 'default', 'custom')]
                for file, value in zip(paths, (current, default, original)):
                    file.write_bytes(value)
                merged = subprocess.run(['/usr/bin/git', 'merge-file', '-p', *map(str, paths)], capture_output=True)
                if merged.returncode:
                    raise ValueError('Theme-related settings changed while Vanilla was selected; preserving ' + str(path))
                outputs[path] = merged.stdout
        else:
            raise ValueError('Theme override changed while Vanilla was selected; preserving ' + str(path))
    return outputs


def publish(e, outputs):
    changed = set()
    for path, value in outputs.items():
        if value is None:
            if path.exists():
                path.unlink()
                changed.add(path)
        elif e.atomic(path, value):
            changed.add(path)
    return changed


def hook(command):
    try:
        process = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=90, check=True)
        output = (process.stdout + process.stderr).strip()
        return {'ok': True, 'detail': output[-1500:], 'pending': 'deferred until reopen' in output}
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        return {'ok': False, 'returncode': getattr(error, 'returncode', None),
                'detail': str(getattr(error, 'stderr', '') or error)[-1500:]}


def apply_default(e, restore=False, name=NAME):
    from gi.repository import Gio
    before = e.selection()
    dark = name == DARK_NAME
    cursor = Gio.Settings.new(e.SCHEMA)
    cursor_before = [cursor.get_value(key).unpack() for key in ('cursor-theme', 'cursor-size')]
    with tempfile.TemporaryDirectory(dir=e.STATE, prefix='vanilla-render-') as temporary:
        outputs = plan(e, Path(temporary), dark=dark)
        suspended = e.STATE / 'vanilla-suspended'
        already_suspended = (suspended / 'applied.json').exists()
        transaction = e.STATE / 'transactions' / str(time.time_ns())
        extra = [e.STATE / 'gnome.json']
        e.snapshot(e.INSTALL / 'application-before', list(outputs))
        e.snapshot(suspended, list(outputs))
        e.snapshot(transaction, list(outputs) + extra)
        try:
            changed = publish(e, outputs)
            settings = e.settings_objects()
            for key in ('gtk-theme', 'icon-theme', 'color-scheme', 'accent-color',
                        'font-name', 'document-font-name', 'monospace-font-name'):
                settings[e.SCHEMA].reset(key)
            settings['org.gnome.shell.extensions.user-theme'].set_string('name', '')
            if dark:
                settings[e.SCHEMA].set_string('color-scheme', 'prefer-dark')
                settings[e.SCHEMA].set_string('gtk-theme', 'Adwaita-dark')
            if not e.restore_wallpaper(name) and not restore:
                for key in ('picture-uri', 'picture-uri-dark'):
                    settings['org.gnome.desktop.background'].reset(key)
            Gio.Settings.sync()
            assert cursor_before == [cursor.get_value(key).unpack() for key in ('cursor-theme', 'cursor-size')]
        except Exception:
            e.restore_snapshot(transaction)
            if not already_suspended:
                shutil.rmtree(suspended)
            raise
        records = {record['path']: record for record in json.loads((suspended / 'files.json').read_text())}
        applied = []
        for path, value in outputs.items():
            record = records[str(path.resolve()) if path.is_symlink() else str(path)]
            if value is not None:
                e.atomic(suspended / ('default-' + record['file']), value)
            applied.append({'path': record['path'], 'exists': value is not None})
        e.atomic(suspended / 'applied.json', json.dumps(applied, indent=2) + '\n')
        results = {
            'kitty': hook(['/usr/bin/pkill', '-USR1', '-x', 'kitty']),
        }
        # pkill's no-matching-process status simply means no terminal needs reloading.
        if results['kitty'].get('returncode') == 1:
            results['kitty'] = {'ok': True, 'detail': 'No running Kitty instance'}
        results.update(e.refresh_integrations(name, explicit=not restore))
        spotify = e.HOME / '.spicetify/spicetify'
        if spotify.exists():
            results['spotify'] = hook([spotify, '-q', 'restore', '--no-restart'])
            if results['spotify']['ok']:
                e.atomic(e.STATE / 'spotify-needs-apply', 'Restore saved Spicetify configuration on the next Oma/Niri application.\n')
        record = {'palette': name, 'desktop': 'gnome', 'changed_files': len(changed), 'hooks': results,
                  'previous_palette': before.get('palette') if before.get('palette') != name else before.get('previous_palette', 'oma Gruvbox'),
                  'shell_extension': e.shell_status(), 'transaction': str(transaction),
                  'cursor_preserved': True, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
        e.atomic(e.STATE / 'gnome.json', json.dumps(record, indent=2) + '\n')
        e.remember_wallpaper(name)
        e.atomic(e.STATE / 'last-application.json', json.dumps(record, indent=2) + '\n')
        for directory in sorted((e.STATE / 'transactions').iterdir())[:-2]:
            shutil.rmtree(directory)
        print(json.dumps(record, indent=2))


if __name__ == '__main__':
    raise SystemExit(0 if active() else 1)
