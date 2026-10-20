"""Maintained application adapters. Profile discovery never traverses documents."""
import configparser
import contextlib
import copy
import ctypes
import ctypes.util
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from urllib.parse import unquote, urlparse

from integrations import Blocked, VANILLA, digest, json_bytes, read, result

STYLE_PREF = 'toolkit.legacyUserProfileCustomizations.stylesheets'
OFFICE_ID = 'dev.noctalia.libreoffice.theme'
PDF_ID = 'omarchy-pdf-theme@local'
PDF_VERSION = '1.0.4'


def profiles(base):
    """Only profiles explicitly registered by the application."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(base / 'profiles.ini')
    found = []
    for section in parser.sections():
        if section.startswith('Profile') and parser.has_option(section, 'Path'):
            path = Path(parser[section]['Path']).expanduser()
            if parser[section].get('IsRelative', '1') == '1':
                path = base / path
            elif not path.is_absolute():
                raise ValueError('Registered absolute profile path is relative')
            if path.is_dir():
                found.append(path.resolve())
    return sorted(set(found))


def managed(text, body, label):
    begin, end = f'/* Project Largo: {label} */', f'/* End Project Largo: {label} */'
    block = begin + '\n' + body.rstrip() + '\n' + end
    if text.count(begin) != text.count(end) or text.count(begin) > 1:
        raise ValueError('Ambiguous Project Largo managed block')
    if begin in text:
        return re.sub(re.escape(begin) + '.*?' + re.escape(end), lambda _: block, text, flags=re.S)
    return text.rstrip() + ('\n\n' if text.strip() else '') + block + '\n'


def pref_text(text):
    # user.js is JavaScript; comments must use JS-compatible syntax (CSS blocks work).
    pattern = r'(?m)^\s*user_pref\(["\']' + re.escape(STYLE_PREF) + r'["\']\s*,\s*(?:true|false)\s*\);[^\n]*$'
    return managed(re.sub(pattern, '', text), f'user_pref("{STYLE_PREF}", true);', 'browser stylesheets')


def css_import(text, path, destination, aliases=()):
    """Adopt/deduplicate only imports resolving to known Largo-owned styles."""
    scan = re.sub(r'/\*.*?\*/', lambda m: ' ' * len(m[0]), text, flags=re.S)
    pattern = r'@import\s+(?:url\(\s*)?(?:"([^"]+)"|\'([^\']+)\'|([^\s;)]+))\s*\)?\s*;'
    owned = {p.resolve() for p in (destination, *aliases)}
    matches = []
    for match in re.finditer(pattern, scan):
        value = next(v for v in match.groups() if v is not None)
        uri = urlparse(value)
        if uri.scheme and uri.scheme != 'file':
            continue
        file = Path(unquote(uri.path)) if uri.scheme == 'file' else path.parent / value
        if file.resolve() in owned:
            matches.append(match)
    relative = os.path.relpath(destination, path.parent)
    line = f'@import url("{relative}");'
    if not matches:
        return line + '\n' + text
    # Normalize the first owned import and remove only subsequent owned copies.
    for index in range(len(matches) - 1, -1, -1):
        match = matches[index]
        text = text[:match.start()] + (line if index == 0 else '') + text[match.end():]
    return text


def unpack_session(raw):
    if raw is None or raw[:8] != b'mozLz40\0' or len(raw) < 12:
        raise ValueError('Unknown Zen session format; no workspace data changed')
    size = int.from_bytes(raw[8:12], 'little')
    if not 0 < size <= 64 * 1024 * 1024:
        raise ValueError('Zen session exceeds supported size')
    library = ctypes.util.find_library('lz4')
    if not library:
        raise ValueError('Zen workspace enrollment requires liblz4')
    lib = ctypes.CDLL(library)
    output = ctypes.create_string_buffer(size)
    count = lib.LZ4_decompress_safe(raw[12:], output, len(raw) - 12, size)
    if count != size:
        raise ValueError('Invalid Zen session compression')
    data = json.loads(output.raw)
    if not isinstance(data.get('spaces'), list) or not data['spaces']:
        raise Blocked('Open app once', 'Create a Zen workspace, close Zen, then retry.')
    if any(not isinstance(s, dict) or not isinstance(s.get('uuid'), str) or (s.get('theme') is not None and not isinstance(s['theme'], dict))
           for s in data['spaces']):
        raise ValueError('Unknown Zen workspace schema; preserving session')
    return data


def pack_session(data):
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
    lib = ctypes.CDLL(ctypes.util.find_library('lz4'))
    output = ctypes.create_string_buffer(lib.LZ4_compressBound(len(raw)))
    size = lib.LZ4_compress_default(raw, output, len(raw), len(output))
    if size <= 0:
        raise ValueError('Could not encode Zen session')
    encoded = b'mozLz40\0' + len(raw).to_bytes(4, 'little') + output.raw[:size]
    if unpack_session(encoded) != data:
        raise ValueError('Zen session round-trip failed')
    return encoded


def gradient():
    return [dict(c=f'var(--oma-zen-gradient-{i}, #131313)', isCustom=True, isPrimary=i == 1)
            for i in range(1, 4)]


def restore_session(before, after, current):
    original, installed, live = map(unpack_session, (before, after, current))
    old = {s['uuid']: (s.get('theme'), 'theme' in s) for s in original['spaces']}
    added = {s['uuid']: s['theme'] for s in installed['spaces']}
    for space in live['spaces']:
        uid = space['uuid']
        if uid in added:
            if space.get('theme') not in (added[uid], old[uid][0]):
                raise ValueError('Zen workspace theme changed; preserving it')
            if old[uid][1]:
                space['theme'] = old[uid][0]
            else:
                space.pop('theme', None)
    return pack_session(live)


def artifact(context, supplied, name):
    paths = {
        'zen-chrome': '.cache/noctalia/zen-browser/zen-userChrome.css',
        'zen-content': '.cache/noctalia/zen-browser/zen-userContent.css',
        'obsidian': '.local/state/project-largo/rendered/obsidian.css',
        'zotero': '.local/state/noctalia/application-themes/zotero.css',
        'zotero-pdf': '.local/state/omarchy/current/theme/zotero-pdf-theme.json',
        'office': '.local/state/noctalia/libreoffice-theme-staging/Theme_Colors.xcu',
        'office-gtk': '.local/share/themes/Noctalia-LibreOffice/gtk-3.0/gtk.css',
        'office-gtk-dark': '.local/share/themes/Noctalia-LibreOffice/gtk-3.0/gtk-dark.css',
    }
    path = context.home / paths[name]
    value = supplied.get(path) if supplied is not None else read(path)
    if value is None:
        raise Blocked('Setup needed', 'Apply a palette or run integration setup to generate ' + name)
    return value


class Adapter:
    names = ()
    restart_required = True

    def __init__(self, context):
        self.c = context

    def target(self, backend, profile=None, **extra):
        return dict(key=self.name + ':' + backend + (':' + str(profile) if profile else ''),
                    backend=backend, profile=str(profile) if profile else None, **extra)

    def guard(self, target):
        if self.c.processes(self.names):
            raise Blocked('Close app and retry', 'Close all ' + self.name + ' windows before changing its profile.')
        if self.name == 'libreoffice' and target.get('profile'):
            profile = Path(target['profile'])
            if any(p.exists() or p.is_symlink() for p in (profile / '.lock', profile.parent / '.lock')):
                raise Blocked('Close app and retry', 'LibreOffice profile lock is present; close the suite (or open and close it once after a crash), then retry.')
        if self.name == 'obsidian':
            root = self.c.home / ('.config/obsidian' if target['backend'] == 'native' else '.var/app/md.obsidian.Obsidian/config/obsidian')
            lock = root / 'SingletonLock'
            if lock.exists() or lock.is_symlink():
                raise Blocked('Close app and retry', 'Obsidian application lock is present; close the app, then retry.')

    @contextlib.contextmanager
    def profile_lock(self, target):
        self.guard(target)
        if self.name in ('zen', 'zotero') and target.get('profile'):
            lock_path = Path(target['profile']) / '.parentlock'
            if lock_path.is_symlink():
                raise Blocked('Close app and retry', 'Browser profile lock requires closing the application.')
            with lock_path.open('a') as stream:
                try:
                    fcntl.lockf(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise Blocked('Close app and retry', 'The browser profile is locked.')
                yield
        else:
            yield

    def inspect(self, target, artifacts=None, palette=None):
        if target.get('error'):
            return result(self.name, target['key'], 'Failed', target['error'])
        if target.get('absent'):
            return result(self.name, target['key'], 'Not installed', 'Optional application is not installed.')
        if not target.get('profile'):
            return result(self.name, target['key'], 'Open app once', 'Open the application once, close it, then retry.')
        self.check_paths(target)
        # While open, do not read session files or extension-manager storage.
        if self.c.processes(self.names):
            return result(self.name, target['key'], 'Close app and retry', 'Close the application to verify and repair its profile safely.')
        self.guard(target)
        changes = self.plan(target, artifacts, palette)
        needed = [str(path) for path, data, kind in changes if read(path) != data]
        if needed:
            return result(self.name, target['key'], 'Setup needed', 'Missing or outdated palette hooks.', paths=needed)
        return result(self.name, target['key'], 'Ready', 'Owned configuration and current generated assets verified.')

    def enroll(self, target, tx, artifacts, palette):
        for path, data, kind in self.plan(target, artifacts, palette):
            tx.write(path, data, kind)

    def running_outputs(self, target, palette):
        return []

    def restart_signature(self, target):
        return None

    def activation_ready(self, target):
        return True

    def running_complete(self, target, palette):
        return True

    def check_paths(self, target):
        profile = Path(target['profile'])
        paths = []
        if self.name == 'obsidian':
            paths = [profile, profile / 'snippets', profile / 'appearance.json', profile / 'snippets/noctalia.css']
        elif self.name in ('zen', 'zotero'):
            paths = [profile / 'chrome', profile / 'chrome/noctalia', profile / 'chrome/largo']
        if any(path.is_symlink() for path in paths):
            raise ValueError('Profile configuration symlink requires review; no shared target will be modified')


class Zen(Adapter):
    name, names = 'zen', ('zen', 'zen-bin', 'zen-browser')

    def discover(self):
        targets = []
        for backend, bases in (
            ('native', [self.c.home / '.zen', self.c.home / '.config/zen']),
            ('flatpak', [self.c.home / '.var/app/app.zen_browser.zen/.zen'])):
            installed = self.c.flatpak('app.zen_browser.zen') if backend == 'flatpak' else bool(self.c.native('zen') or self.c.native('zen-browser'))
            if not installed:
                targets.append(self.target(backend, absent=True))
                continue
            found = sorted({p for base in bases for p in profiles(base)})
            targets.extend(self.target(backend, p) for p in found)
            if not found:
                targets.append(self.target(backend, absent=not installed))
        return targets

    def plan(self, target, artifacts, palette):
        profile = Path(target['profile'])
        changes = []
        vanilla = palette in VANILLA
        for kind in ('Chrome', 'Content'):
            css = b'/* Vanilla Gnome: no palette override. */\n' if vanilla else artifact(self.c, artifacts, 'zen-' + kind.lower())
            path = profile / f'chrome/user{kind}.css'
            text = (read(path) or b'').decode()
            text = css_import(text, path, profile / f'chrome/noctalia/zen-user{kind}.css',
                              [self.c.home / f'.cache/noctalia/zen-browser/zen-user{kind}.css'])
            changes += [(path, text.encode(), 'text'),
                        (profile / f'chrome/noctalia/zen-user{kind}.css', css, 'file')]
        path = profile / 'user.js'
        changes.append((path, pref_text((read(path) or b'').decode()).encode(), 'text'))
        session = profile / 'zen-sessions.jsonlz4'
        if not session.exists():
            raise Blocked('Open app once', 'Open Zen and create a workspace, then close it and retry.')
        # Vanilla neutralizes the variables, retaining native workspace references.
        original = unpack_session(session.read_bytes())
        updated = copy.deepcopy(original)
        for space in updated['spaces']:
            if space.get('theme') is None:
                space['theme'] = {}
            theme = space['theme']
            theme.update(type='gradient', gradientColors=gradient())
            theme.setdefault('opacity', 0.5)
            theme.setdefault('texture', 0)
            # Preserve existing native opacity/texture and all other theme fields.
        protected = copy.deepcopy(updated)
        for before, after in zip(original['spaces'], protected['spaces']):
            if 'theme' in before:
                after['theme'] = before['theme']
            else:
                after.pop('theme', None)
        if protected != original:
            raise ValueError('Unexpected non-theme Zen session change')
        if original != updated:
            changes.append((session, pack_session(updated), 'session'))
        return changes

    def running_outputs(self, target, palette):
        profile = Path(target['profile'])
        return [(profile / f'chrome/noctalia/zen-user{kind}.css',
                 b'/* Vanilla Gnome: no palette override. */\n' if palette in VANILLA else artifact(self.c, None, 'zen-' + kind.lower()))
                for kind in ('Chrome', 'Content')]

    def restart_signature(self, target):
        if not target.get('profile'):
            return None
        profile = Path(target['profile'])
        return {str(path): digest(read(path)) for path in [profile / 'user.js'] +
                [profile / 'chrome' / name for name in ('userChrome.css', 'userContent.css',
                    'noctalia/zen-userChrome.css', 'noctalia/zen-userContent.css')]}


class Obsidian(Adapter):
    name, names = 'obsidian', ('obsidian', 'Obsidian')

    def discover(self):
        targets = []
        for backend, registry in (
            ('native', self.c.home / '.config/obsidian/obsidian.json'),
            ('flatpak', self.c.home / '.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json')):
            installed = self.c.flatpak('md.obsidian.Obsidian') if backend == 'flatpak' else bool(self.c.native('obsidian'))
            if not installed:
                targets.append(self.target(backend, absent=True))
                continue
            if registry.is_symlink():
                targets.append(self.target(backend, error='Obsidian registry symlink requires review'))
                continue
            data = json.loads(registry.read_text()) if registry.is_file() else {}
            seen = set()
            for identifier, item in data.get('vaults', {}).items():
                if not isinstance(item, dict) or not isinstance(item.get('path'), str) or not Path(item['path']).is_absolute():
                    targets.append(self.target(backend, error='Invalid registered Obsidian vault path: ' + identifier))
                    continue
                path = Path(item['path']).expanduser() / '.obsidian'
                if path.is_dir() and path not in seen:
                    targets.append(self.target(backend, path))
                    seen.add(path)
            if not seen:
                targets.append(self.target(backend, absent=not installed and not registry.exists()))
        return targets

    def plan(self, target, artifacts, palette):
        profile = Path(target['profile'])
        if profile.name != '.obsidian':
            raise ValueError('Obsidian adapter requires a registered .obsidian directory')
        path = profile / 'appearance.json'
        data = json.loads(read(path) or b'{}')
        enabled = data.get('enabledCssSnippets', [])
        if not isinstance(enabled, list) or not all(isinstance(v, str) for v in enabled):
            raise ValueError('Unknown Obsidian snippet configuration')
        suspension = self.c.state / 'vanilla' / (hashlib_key(target['key']) + '.json')
        saved = json.loads(read(suspension) or b'{}')
        if palette in VANILLA:
            original = copy.deepcopy(data)
            data['enabledCssSnippets'] = [v for v in enabled if v != 'noctalia']
            data.pop('cssTheme', None)
            data.pop('theme', None)
            if palette == VANILLA[1]:
                data['theme'] = 'obsidian'
            css = b'/* Vanilla Gnome: no palette override. */\n'
        else:
            if saved:
                from integrations import merge_restore
                data = merge_restore(saved['before'], saved['after'], data)
                enabled = data.get('enabledCssSnippets', [])
            data['enabledCssSnippets'] = list(dict.fromkeys(enabled + ['noctalia']))
            css = artifact(self.c, artifacts, 'obsidian')
        appearance = json_bytes(data)
        if read(path) is not None and json.loads(read(path)) == data:
            appearance = read(path)
        changes = [(path, appearance, 'json'), (profile / 'snippets/noctalia.css', css, 'file')]
        if palette in VANILLA:
            changes.insert(0, (suspension, json_bytes(dict(before=saved.get('before', original), after=data)), 'json'))
        elif saved:
            changes.append((suspension, None, 'file'))
        return changes

    def running_outputs(self, target, palette):
        self.check_paths(target)
        # Enabled snippets are watched by Obsidian. Disabling the override does
        # not require rewriting appearance.json while Obsidian owns that file.
        css = b'/* Vanilla Gnome: no palette override. */\n' if palette in VANILLA else artifact(self.c, None, 'obsidian')
        return [(Path(target['profile']) / 'snippets/noctalia.css', css)]

    def running_complete(self, target, palette):
        data = json.loads(read(Path(target['profile']) / 'appearance.json') or b'{}')
        enabled = 'noctalia' in data.get('enabledCssSnippets', [])
        if palette in VANILLA:
            return not enabled and not data.get('cssTheme') and (data.get('theme') == 'obsidian' if palette == VANILLA[1] else not data.get('theme'))
        return enabled

    def restart_signature(self, target):
        if not target.get('profile'):
            return None
        profile = Path(target['profile'])
        data = json.loads(read(profile / 'appearance.json') or b'{}')
        return dict(enabled='noctalia' in data.get('enabledCssSnippets', []),
                    css=digest(read(profile / 'snippets/noctalia.css')))


class Zotero(Adapter):
    name, names = 'zotero', ('zotero', 'zotero-bin')

    def discover(self):
        found = sorted({p for base in (self.c.home / '.zotero/zotero', self.c.home / '.zotero') for p in profiles(base)})
        installed = bool(self.c.native('zotero', [Path('/opt/zotero/zotero')]))
        if not installed:
            return [self.target('native', absent=True)]
        targets = [self.target('native', p) for p in found] or [self.target('native', absent=not installed)]
        return targets

    def bridge(self):
        manifest = dict(manifest_version=2, name='Project Largo PDF palette bridge', version=PDF_VERSION,
                        applications={'zotero': {'id': PDF_ID,
                                                  'strict_min_version': '7.0', 'strict_max_version': '9.*'}})
        import io
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in [('manifest.json', json_bytes(manifest)),
                               ('bootstrap.js', (self.c.root / 'zotero-pdf-bootstrap.js').read_bytes())]:
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                archive.writestr(info, data)
        return stream.getvalue()

    def plan(self, target, artifacts, palette):
        profile = Path(target['profile'])
        changes = []
        css = b'/* Vanilla Gnome: no palette override. */\n' if palette in VANILLA else artifact(self.c, artifacts, 'zotero')
        for kind in ('Chrome', 'Content'):
            path = profile / f'chrome/user{kind}.css'
            text = (read(path) or b'').decode()
            text = css_import(text, path, profile / 'chrome/largo/zotero.css',
                              [self.c.home / '.local/state/noctalia/application-themes/zotero.css'])
            changes.append((path, text.encode(), 'text'))
        changes += [(profile / 'chrome/largo/zotero.css', css, 'file'),
                    (profile / 'user.js', pref_text((read(profile / 'user.js') or b'').decode()).encode(), 'text'),
                    (profile / f'extensions/{PDF_ID}.xpi', self.bridge(), 'file')]
        pdf = b'{"enabled":false}\n' if palette in VANILLA else artifact(self.c, artifacts, 'zotero-pdf')
        changes.append((self.c.home / '.local/state/omarchy/current/theme/zotero-pdf-theme.json', pdf, 'file'))
        existing = profile / f'extensions/{PDF_ID}.xpi'
        if existing.is_file():
            try:
                with zipfile.ZipFile(existing) as archive:
                    version = json.loads(archive.read('manifest.json')).get('version', '')
                if re.fullmatch(r'\d+(?:\.\d+)*', version) and tuple(map(int, version.split('.'))) > tuple(map(int, PDF_VERSION.split('.'))):
                    raise ValueError('A newer Zotero PDF bridge is installed; preserving it for compatibility review')
            except (zipfile.BadZipFile, KeyError):
                pass  # A broken package is backed up before repair.
        return changes

    def inspect(self, target, artifacts=None, palette=None):
        outcome = super().inspect(target, artifacts, palette)
        if outcome['state'] == 'Ready':
            path = Path(target['profile']) / 'extensions.json'
            data = json.loads(read(path) or b'{}')
            extension = next((a for a in data.get('addons', []) if a.get('id') == PDF_ID), {})
            if extension.get('userDisabled') or extension.get('appDisabled'):
                outcome.update(state='Setup needed', detail='Bridge package is installed but Zotero reports it disabled; enable it in Zotero’s plugin manager or resolve its compatibility warning.')
            elif extension.get('version') != PDF_VERSION or not extension.get('active'):
                outcome.update(state='Restart required', detail='UI hooks and bridge package verified; reopen Zotero to activate the bridge.')
        return outcome

    def running_outputs(self, target, palette):
        css = b'/* Vanilla Gnome: no palette override. */\n' if palette in VANILLA else artifact(self.c, None, 'zotero')
        return [(Path(target['profile']) / 'chrome/largo/zotero.css', css)]

    def restart_signature(self, target):
        if not target.get('profile'):
            return None
        profile = Path(target['profile'])
        return {str(path): digest(read(path)) for path in [profile / 'user.js'] +
                [profile / relative for relative in ('chrome/userChrome.css', 'chrome/userContent.css',
                    'chrome/largo/zotero.css', f'extensions/{PDF_ID}.xpi')]}

    def activation_ready(self, target):
        if not target.get('profile'):
            return False
        data = json.loads(read(Path(target['profile']) / 'extensions.json') or b'{}')
        return any(addon.get('id') == PDF_ID and addon.get('version') == PDF_VERSION and addon.get('active')
                   for addon in data.get('addons', []))


def hashlib_key(text):
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


def office_scheme(original, scheme):
    ns = 'http://openoffice.org/2001/registry'
    config_path = '/org.openoffice.Office.UI/ColorScheme'
    root = ET.fromstring(original)
    matches = [p for item in root if item.get(f'{{{ns}}}path') == config_path
               for p in item if p.get(f'{{{ns}}}name') == 'CurrentColorScheme']
    if len(matches) > 1:
        raise ValueError('Ambiguous LibreOffice scheme selection')
    if matches and matches[0].findtext('value') == scheme:
        return original
    text = original.decode()
    if matches:
        item_pattern = r'<item\b[^>]*\boor:path=["\']' + re.escape(config_path) + r'["\'][^>]*>.*?</item>'
        prop_pattern = r'(<prop\b[^>]*\boor:name=["\']CurrentColorScheme["\'][^>]*>\s*<value>)[^<]*(</value>)'
        text, count = re.subn(item_pattern, lambda m: re.sub(prop_pattern, lambda p: p[1] + scheme + p[2], m[0]), text, flags=re.S)
        if count != 1:
            raise ValueError('Unknown LibreOffice scheme serialization')
    else:
        if text.count('</oor:items>') != 1:
            raise ValueError('Unknown LibreOffice configuration root')
        text = text.replace('</oor:items>', f'<item oor:path="{config_path}"><prop oor:name="CurrentColorScheme" oor:op="fuse"><value>{scheme}</value></prop></item>\n</oor:items>')
    verified = ET.fromstring(text)
    selected = [p.findtext('value') for item in verified if item.get(f'{{{ns}}}path') == config_path
                for p in item if p.get(f'{{{ns}}}name') == 'CurrentColorScheme']
    if selected != [scheme]:
        raise ValueError('Could not verify LibreOffice scheme selection')
    return text.encode()


def restore_office_scheme(before, after, current):
    ns = 'http://openoffice.org/2001/registry'
    config_path = '/org.openoffice.Office.UI/ColorScheme'
    def selected(value):
        root = ET.fromstring(value)
        values = [p.findtext('value') for item in root if item.get(f'{{{ns}}}path') == config_path
                  for p in item if p.get(f'{{{ns}}}name') == 'CurrentColorScheme']
        if len(values) > 1:
            raise ValueError('Ambiguous office scheme during restoration')
        return values[0] if values else None
    old, installed, live = map(selected, (before, after, current))
    if live == old or old == installed:
        return current
    if live != installed:
        raise ValueError('LibreOffice scheme changed; preserving the user selection')
    if old is not None:
        return office_scheme(current, old)
    item_pattern = r'<item\b[^>]*\boor:path=["\']' + re.escape(config_path) + r'["\'][^>]*>.*?</item>'
    prop_pattern = r'<prop\b[^>]*\boor:name=["\']CurrentColorScheme["\'][^>]*>.*?</prop>'
    def remove(match):
        text = re.sub(prop_pattern, '', match[0], flags=re.S)
        return '' if not list(ET.fromstring('<root xmlns:oor="' + ns + '">' + text + '</root>')[0]) else text
    value = re.sub(item_pattern, remove, current.decode(), flags=re.S).encode()
    if selected(value) is not None:
        raise ValueError('Could not restore original LibreOffice selection')
    return value


class LibreOffice(Adapter):
    name, names = 'libreoffice', ('soffice.bin', 'soffice', 'oosplash', 'unopkg.bin', 'unopkg')

    def discover(self):
        targets = []
        candidates = [Path('/usr/lib64/libreoffice/program/unopkg'), Path('/usr/lib/libreoffice/program/unopkg')]
        candidates += sorted(Path('/opt').glob('libreoffice*/program/unopkg'))
        native = self.c.native('unopkg', candidates)
        native_app = native or self.c.native('libreoffice') or self.c.native('soffice')
        for backend, installed, base in (
            ('native', bool(native_app), self.c.home / '.config/libreoffice'),
            ('flatpak', self.c.flatpak('org.libreoffice.LibreOffice'), self.c.home / '.var/app/org.libreoffice.LibreOffice/config/libreoffice')):
            if not installed:
                targets.append(self.target(backend, absent=True))
                continue
            found = [p for p in sorted(base.glob('*/user')) if (p / 'registrymodifications.xcu').is_file()]
            targets += [self.target(backend, p, executable=native if backend == 'native' else None) for p in found]
            if not found:
                targets.append(self.target(backend, absent=not installed))
        return targets

    def office_colors(self, artifacts):
        raw = artifact(self.c, artifacts, 'office')
        return re.sub(rb'<value>([0-9a-fA-F]{6})</value>', lambda m: b'<value>' + str(int(m[1], 16)).encode() + b'</value>', raw)

    def extension_matches(self, target, colors):
        base = Path(target['profile']) / 'uno_packages/cache/uno_packages'
        matches = [p for p in base.glob('*/noctalia-theme.oxt/Theme_Colors.xcu') if p.is_file()]
        # Verify both package identity and payload, not merely an old staging hash.
        for path in matches:
            description = path.with_name('description.xml')
            if description.is_file() and OFFICE_ID in description.read_text() and path.read_bytes() == colors:
                cache = Path(target['profile']) / 'uno_packages/cache'
                mapping = read(cache / 'uno_packages.pmap') or b''
                registry = cache / 'registry/com.sun.star.comp.deployment.bundle.PackageRegistryBackend/backenddb.xml'
                if OFFICE_ID.encode() in mapping and registry.is_file():
                    root = ET.fromstring(registry.read_bytes())
                    suffix = '/' + path.parent.parent.name + '/noctalia-theme.oxt'
                    if any(node.get('url', '').endswith(suffix) and node.get('revoked') != 'true' for node in root):
                        config = cache / 'registry/com.sun.star.comp.deployment.configuration.PackageRegistryBackend/backenddb.xml'
                        if config.is_file() and any(node.get('url', '').endswith(suffix + '/Theme_Colors.xcu') and node.get('revoked') != 'true'
                                                    for node in ET.fromstring(config.read_bytes())):
                            return True
        return False

    def command(self, target):
        profile = Path(target['profile']).parent
        if target['backend'] == 'native':
            if not target.get('executable'):
                raise ValueError('Native unopkg executable is unavailable')
            return [target['executable'], '-env:UserInstallation=' + profile.as_uri()]
        # Resolve in the actual sandbox, not from the host installation layout.
        executable = self.c.runner(['flatpak', 'run', '--command=sh', 'org.libreoffice.LibreOffice', '-c',
            'command -v unopkg || { for p in /app/bin/unopkg /app/libreoffice/program/unopkg; do if [ -x "$p" ]; then printf "%s\\n" "$p"; break; fi; done; }']).strip()
        if not re.fullmatch(r'/app/[A-Za-z0-9_./-]+', executable):
            raise ValueError('Cannot discover unopkg inside LibreOffice sandbox')
        # Flatpak maps its config home to this host directory; use the sandbox's own value.
        sandbox_config = self.c.runner(['flatpak', 'run', '--command=sh', 'org.libreoffice.LibreOffice',
                                        '-c', 'printf "%s" "$XDG_CONFIG_HOME"']).strip()
        if not sandbox_config.startswith('/') or '\n' in sandbox_config:
            raise ValueError('Cannot resolve Flatpak LibreOffice profile')
        uri = (Path(sandbox_config) / 'libreoffice' / profile.name).as_uri()
        return ['flatpak', 'run', '--command=' + executable, 'org.libreoffice.LibreOffice', '-env:UserInstallation=' + uri]

    def launcher(self, target, palette):
        # A suite-wide desktop route preserves original IDs, MIME types and arguments.
        roots = [self.c.home / '.local/share/applications', Path('/usr/share/applications')]
        if target['backend'] == 'flatpak':
            roots += [self.c.home / '.local/share/flatpak/exports/share/applications', Path('/var/lib/flatpak/exports/share/applications')]
        names = ('org.libreoffice.LibreOffice.desktop',) if target['backend'] == 'flatpak' else (
            'libreoffice-startcenter.desktop', 'libreoffice-writer.desktop', 'libreoffice-calc.desktop',
            'libreoffice-impress.desktop', 'libreoffice-draw.desktop', 'libreoffice-base.desktop', 'libreoffice-math.desktop')
        changes = []
        for name in names:
            source = next((root / name for root in roots if (root / name).is_file()), None)
            if not source:
                continue
            text = source.read_text()
            wrapper = self.c.home / '.local/bin/project-largo-office'
            # Preserve the actual original Exec command, including desktop action routes.
            def replace(match):
                command = match[1]
                parsed = shlex.split(command)
                original = parsed[2:] if parsed[:1] == [str(wrapper)] else parsed
                if target['backend'] == 'flatpak' and (len(original) < 3 or Path(original[0]).name != 'flatpak' or original[1] != 'run'
                    or not any(arg == 'org.libreoffice.LibreOffice' or arg.startswith('org.libreoffice.LibreOffice/') for arg in original[2:])):
                    raise ValueError('Unsupported Flatpak desktop launch route; preserving original launcher')
                if str(wrapper) in command:
                    return match[0]
                if target['backend'] == 'flatpak':
                    return 'Exec="' + str(wrapper) + '" flatpak ' + command
                return 'Exec="' + str(wrapper) + '" native ' + command
            updated = re.sub(r'(?m)^Exec=(.*)$', replace, text)
            changes.append((self.c.home / '.local/share/applications' / name, updated.encode(), 'text'))
        if not changes:
            raise ValueError('No supported LibreOffice desktop launcher found; GTK launch route not enrolled')
        script = '''#!/usr/bin/python3
import json, os, pathlib, subprocess, sys
state = pathlib.Path.home() / '.local/state/oma-theme/gnome.json'
name = json.loads(state.read_text()).get('palette') if state.exists() else None
vanilla = name in ('Vanilla Gnome', 'Vanilla Gnome Dark')
args = sys.argv[2:]
engine = pathlib.Path.home() / '.config/oma-theme/engine.py'
# Safely complete deferred extension updates before LibreOffice starts.
if engine.is_file():
    subprocess.run([sys.executable, str(engine), 'integrations', 'repair', '--app', 'libreoffice', '--json'], stdout=subprocess.DEVNULL)
if sys.argv[1] == 'native':
    os.environ['SAL_USE_VCLPLUGIN'] = 'gtk3'
    if vanilla: os.environ.pop('GTK_THEME', None)
    else: os.environ['GTK_THEME'] = 'Noctalia-LibreOffice'
    if pathlib.Path(args[0]).name == 'env':
        end = 1
        while end < len(args) and '=' in args[end] and args[end].partition('=')[0].isidentifier(): end += 1
        args = [args[0]] + [arg for arg in args[1:end] if not arg.startswith(('SAL_USE_VCLPLUGIN=', 'GTK_THEME='))] + args[end:]
else:
    index = args.index('run') + 1
    application = next(i for i in range(index, len(args)) if args[i] == 'org.libreoffice.LibreOffice' or args[i].startswith('org.libreoffice.LibreOffice/'))
    options = [arg for arg in args[index:application] if not arg.startswith(('--env=SAL_USE_VCLPLUGIN=', '--env=GTK_THEME='))]
    args = args[:index] + ['--env=SAL_USE_VCLPLUGIN=gtk3', '--env=GTK_THEME=' + ('' if vanilla else 'Noctalia-LibreOffice')] + options + args[application:]
os.execvp(args[0], args)
'''
        changes.append((self.c.home / '.local/bin/project-largo-office', script.encode(), 'executable'))
        return changes

    def plan(self, target, artifacts, palette):
        profile = Path(target['profile'])
        path = profile / 'registrymodifications.xcu'
        scheme = 'COLOR_SCHEME_LIBREOFFICE_AUTOMATIC' if palette in VANILLA else 'Noctalia'
        changes = [(path, office_scheme(path.read_bytes(), scheme), 'office-scheme')]
        changes += self.launcher(target, palette)
        if palette not in VANILLA:
            for name, key in (('gtk.css', 'office-gtk'), ('gtk-dark.css', 'office-gtk-dark')):
                # Native and sandbox GTK discover their own data directory.
                root = self.c.home / '.local/share/themes'
                if target['backend'] == 'flatpak':
                    root = self.c.home / '.var/app/org.libreoffice.LibreOffice/data/themes'
                changes.append((root / 'Noctalia-LibreOffice/gtk-3.0' / name, artifact(self.c, artifacts, key), 'file'))
        return changes

    def inspect(self, target, artifacts=None, palette=None):
        if not target.get('absent') and target['backend'] == 'native' and target.get('profile') and not target.get('executable'):
            return result(self.name, target['key'], 'Administrator setup required',
                          'LibreOffice is installed but unopkg is unavailable; install its native extension-manager/core component, then retry.')
        outcome = super().inspect(target, artifacts, palette)
        if outcome['state'] == 'Ready':
            self.verify_toolkit(target)
            if palette not in VANILLA and not self.extension_matches(target, self.office_colors(artifacts)):
                outcome.update(state='Setup needed', detail='Color extension registration or deployed palette is missing/outdated.')
        return outcome

    def enroll(self, target, tx, artifacts, palette):
        self.verify_toolkit(target)
        for path, data, kind in self.plan(target, artifacts, palette):
            tx.write(path, data, kind, mode=0o755 if kind == 'executable' else None)
        if palette in VANILLA:
            return
        colors = self.office_colors(artifacts)
        if self.extension_matches(target, colors):
            return
        profile = Path(target['profile'])
        # Extension commands can update registrymodifications as well as caches.
        for name in ('uno_packages', 'extensions'):
            tx.tree(profile / name)
        tx.external(profile / 'registrymodifications.xcu')
        source = self.c.home / '.local/state/noctalia/community-templates/libreoffice'
        package_root = self.c.state
        sandbox_data = None
        if target['backend'] == 'flatpak':
            sandbox_data = self.c.runner(['flatpak', 'run', '--command=sh', 'org.libreoffice.LibreOffice',
                                          '-c', 'printf "%s" "$XDG_DATA_HOME"']).strip()
            if not sandbox_data.startswith('/') or '\n' in sandbox_data:
                raise ValueError('Cannot resolve sandbox package staging directory')
            package_root = self.c.home / '.var/app/org.libreoffice.LibreOffice/data/project-largo'
            package_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix='largo-office-', dir=package_root) as temporary:
            package = Path(temporary) / 'noctalia-theme.oxt'
            with zipfile.ZipFile(package, 'w') as archive:
                for name in ('description.xml', 'Paths.xcu', 'pkg-description.en'):
                    archive.writestr(name, (source / name).read_bytes())
                archive.writestr('Theme_Colors.xcu', colors)
                archive.writestr('META-INF/manifest.xml', '<?xml version="1.0"?><manifest:manifest xmlns:manifest="http://openoffice.org/2001/manifest"><manifest:file-entry manifest:full-path="Theme_Colors.xcu" manifest:media-type="application/vnd.sun.star.configuration-data"/><manifest:file-entry manifest:full-path="Paths.xcu" manifest:media-type="application/vnd.sun.star.configuration-data"/></manifest:manifest>')
            command = self.command(target)
            # Listing a missing *specific* ID exits nonzero on real unopkg.
            # List the user scope instead so a fresh profile is a normal case.
            self.guard(target)
            listing = self.c.runner(command + ['list'])
            self.guard(target)
            if re.search(r'(?m)^\s*Identifier:\s*' + re.escape(OFFICE_ID) + r'\s*$', listing):
                self.c.runner(command + ['remove', OFFICE_ID])
                self.guard(target)
            self.guard(target)
            package_argument = str(package)
            if sandbox_data:
                package_argument = str(Path(sandbox_data) / 'project-largo' / Path(temporary).name / package.name)
            self.c.runner(command + ['add', '--force', package_argument])
            self.guard(target)
            listing = self.c.runner(command + ['list'])
            if not re.search(r'(?m)^\s*Identifier:\s*' + re.escape(OFFICE_ID) + r'\s*$', listing) or not self.extension_matches(target, colors):
                raise ValueError('unopkg did not verify extension registration and exact deployed colors')

    def verify_toolkit(self, target):
        if target['backend'] == 'native':
            executable = Path(target.get('executable') or '/nonexistent')
            candidates = [executable.resolve().parent / 'libvclplug_gtk3lo.so',
                          Path('/usr/lib64/libreoffice/program/libvclplug_gtk3lo.so'),
                          Path('/usr/lib/libreoffice/program/libvclplug_gtk3lo.so')]
            if not any(path.is_file() for path in candidates):
                raise Blocked('Administrator setup required', 'Install the LibreOffice GTK3 backend (Fedora: libreoffice-gtk3), then retry.')
        else:
            output = self.c.runner(['flatpak', 'run', '--command=sh', 'org.libreoffice.LibreOffice', '-c',
                'for p in /app/lib64/libreoffice/program/libvclplug_gtk3lo.so /app/lib/libreoffice/program/libvclplug_gtk3lo.so /app/libreoffice/program/libvclplug_gtk3lo.so /app/lib64/libreoffice/libvclplug_gtk3lo.so; do if [ -f "$p" ]; then printf gtk3; exit 0; fi; done; exit 1'])
            if output.strip() != 'gtk3':
                raise ValueError('Flatpak does not expose the supported GTK3 backend')

    def restart_signature(self, target):
        if not target.get('profile'):
            return None
        profile = Path(target['profile'])
        ns = 'http://openoffice.org/2001/registry'
        root = ET.fromstring((profile / 'registrymodifications.xcu').read_bytes())
        schemes = [p.findtext('value') for item in root
                   if item.get(f'{{{ns}}}path') == '/org.openoffice.Office.UI/ColorScheme'
                   for p in item if p.get(f'{{{ns}}}name') == 'CurrentColorScheme']
        payloads = sorted((profile / 'uno_packages/cache/uno_packages').glob('*/noctalia-theme.oxt/Theme_Colors.xcu'))
        colors = [digest(path.read_bytes()) for path in payloads if self.extension_matches(target, path.read_bytes())]
        return dict(schemes=schemes, registered_colors=colors,
                    launcher=digest(read(self.c.home / '.local/bin/project-largo-office')))


class GDM(Adapter):
    name = 'gdm'
    restart_required = False

    def discover(self):
        installed = Path('/usr/sbin/gdm').is_file() or Path('/usr/lib/systemd/system/gdm.service').is_file()
        return [self.target('system', self.c.home, absent=not installed)]

    def guard(self, target):
        pass

    def inspect(self, target, artifacts=None, palette=None):
        if target.get('absent'):
            return result(self.name, target['key'], 'Not installed', 'GDM is not installed; no administrator setup is needed.')
        helper = Path('/usr/local/libexec/project-largo-gdm')
        config = Path('/etc/project-largo-gdm.json')
        if not helper.is_file() or not config.is_file():
            return result(self.name, target['key'], 'Administrator setup required', 'Use the separate GDM administrator setup action.')
        info = json.loads(config.read_text())
        if info.get('home') != str(self.c.home) or info.get('version') != 1:
            return result(self.name, target['key'], 'Administrator setup required', 'GDM installation belongs to another account or needs migration.')
        expected = (self.c.root / 'gdm_admin.py').read_bytes()
        if helper.read_bytes() != expected:
            return result(self.name, target['key'], 'Administrator setup required', 'The installed GDM helper needs an administrator refresh.')
        import pwd
        import gdm_admin
        files = gdm_admin.setup_files(pwd.getpwuid(os.getuid()), expected)
        for path, value in files.items():
            if not path.is_file() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022 or path.read_bytes() != value:
                return result(self.name, target['key'], 'Administrator setup required', 'Missing, changed or unsafe system GDM configuration: ' + str(path))
        for unit, query in (('project-largo-gdm.path', 'is-active'), ('project-largo-gdm.service', 'is-enabled')):
            try:
                self.c.runner(['/usr/bin/systemctl', query, unit])
            except subprocess.CalledProcessError:
                return result(self.name, target['key'], 'Administrator setup required', 'GDM publisher unit needs administrator setup: ' + unit)
        try:
            failure = self.c.runner(['/usr/bin/systemctl', 'is-failed', 'project-largo-gdm.service']).strip()
        except subprocess.CalledProcessError as error:
            if error.returncode != 1:
                raise
            failure = ''
        if failure == 'failed':
            return result(self.name, target['key'], 'Failed',
                'GDM publisher failed. Check project-largo-gdm.service; setup/repair queues a fresh retry without restarting GDM.', retryable=True)
        if palette and info.get('home') == str(self.c.home):
            queue = self.c.home / '.local/state/project-largo/gdm/request.json'
            request = json.loads(read(queue) or b'{}')
            if request.get('palette') != palette:
                return result(self.name, target['key'], 'Setup needed', 'Queue the current palette for GDM.')
            published = Path('/usr/local/share/project-largo/gdm/current/status.json')
            status = json.loads(read(published) or b'{}')
            import hashlib
            gdm_admin.validate(request)
            fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
            if status.get('palette') != palette or status.get('request_sha256') != fingerprint:
                return result(self.name, target['key'], 'Setup needed', 'Current palette is queued but root publication is not yet verified; check project-largo-gdm.service.')
        return result(self.name, target['key'], 'Ready', 'Root helper, units, account binding and palette publication verified; greeter visuals require a future login.')

    def enroll(self, target, tx, artifacts, palette):
        from gdm_client import request
        data, image = request(self.c, palette, artifacts or {})
        queue = self.c.home / '.local/state/project-largo/gdm'
        if image:
            tx.write(queue / (data['wallpaper'] + '.png'), image)
        tx.write(queue / 'request.json', json_bytes(data), 'json')


def adapters(context, app=None):
    classes = (LibreOffice, Zen, Obsidian, Zotero, GDM)
    if app and app not in {cls.name for cls in classes}:
        raise ValueError('Unknown maintained integration: ' + app)
    return [cls(context) for cls in classes if app is None or cls.name == app]
