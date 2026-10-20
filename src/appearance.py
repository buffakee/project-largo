#!/usr/bin/python3
"""Portable bundled appearance assets and reversible one-time enrollment."""
import configparser
import hashlib
import json
from pathlib import Path
import re
import tarfile

SCHEMA = 'org.gnome.desktop.interface'
CURSOR = 'Bibata-Modern-Ice'
ICONS = 'yet-another-monochrome-icon-set'
ICON_NAMES = (ICONS, 'yamis-noctalia-a', 'yamis-noctalia-b')


def asset_files(source, home):
    """Validate all bundled bytes before returning the installation plan."""
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest['version'] != 1:
        raise ValueError('Unsupported appearance manifest')
    files = {}
    for relative, entry in manifest['files'].items():
        path = source / relative
        if not path.resolve().is_relative_to(source.resolve()):
            raise ValueError('Invalid appearance asset path')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Appearance asset checksum mismatch: ' + relative)
        if entry['kind'] == 'wallpaper':
            files[home / '.local/share/project-largo' / relative] = (data, 0o644)
    with tarfile.open(source / manifest['icon_archive'], 'r:xz') as archive:
        for member in archive:
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or '..' in path.parts or path.parts[0] not in (CURSOR, ICONS):
                raise ValueError('Invalid appearance archive member: ' + member.name)
            files[home / '.local/share/icons' / path] = (archive.extractfile(member).read(), 0o644)
    for name, entry in manifest['themes'].items():
        for relative in entry['wallpapers']:
            if home / '.local/share/project-largo' / relative not in files:
                raise ValueError('Missing wallpaper for ' + name)
        if entry['default'] is not None and entry['default'] not in entry['wallpapers']:
            raise ValueError('Invalid default wallpaper for ' + name)
    files[home / '.local/share/project-largo/manifest.json'] = ((source / 'manifest.json').read_bytes(), 0o644)
    return files


def ini_value(text, key):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(text)
    return parser.get('Settings', key, fallback=None)


def ini_set(text, key, value):
    """Edit only one Settings key, retaining comments and unrelated sections."""
    section = re.search(r'(?m)^\[Settings\][^\n]*\n?', text)
    if section is None:
        return text if value is None else text.rstrip() + '\n[Settings]\n' + key + '=' + value + '\n'
    end = re.search(r'(?m)^\[', text[section.end():])
    stop = section.end() + end.start() if end else len(text)
    body = text[section.end():stop]
    pattern = r'(?m)^' + re.escape(key) + r'\s*=.*(?:\n|$)'
    replacement = '' if value is None else key + '=' + value + '\n'
    body, count = re.subn(pattern, lambda _: replacement, body)
    if count == 0 and value is not None:
        body = replacement + body
    return text[:section.end()].rstrip('\n') + '\n' + body + text[stop:]


def setup(home, write):
    """Install-time opt-in is the default; later reinstalls preserve user edits."""
    from gi.repository import Gio
    state = home / '.local/state/oma-theme/appearance-install.json'
    if state.exists():
        return False
    obj = Gio.Settings.new(SCHEMA)
    previous = {key: obj.get_user_value(key).print_(True) if obj.get_user_value(key) is not None else None
                for key in ('cursor-theme', 'icon-theme')}
    ini = {}
    for version in (3, 4):
        path = home / f'.config/gtk-{version}.0/settings.ini'
        text = path.read_text() if path.exists() else ''
        ini[str(version)] = {key: ini_value(text, key) for key in ('gtk-cursor-theme-name', 'gtk-icon-theme-name')}
    record = {'version': 1, 'settings': previous, 'gtk': ini}
    write(state, (json.dumps(record, indent=2) + '\n').encode(), 0o600)
    # Enrolling while Vanilla is selected must not replace its stock icons.
    selected = home / '.local/state/oma-theme/gnome.json'
    vanilla = selected.exists() and json.loads(selected.read_text()).get('palette') in ('Vanilla Gnome', 'Vanilla Gnome Dark')
    obj.set_string('cursor-theme', CURSOR)
    if not vanilla:
        obj.set_string('icon-theme', ICONS)
    for version in (3, 4):
        path = home / f'.config/gtk-{version}.0/settings.ini'
        text = path.read_text() if path.exists() else ''
        text = ini_set(text, 'gtk-cursor-theme-name', CURSOR)
        if not vanilla:
            text = ini_set(text, 'gtk-icon-theme-name', ICONS)
        write(path, text.encode(), 0o644)
    Gio.Settings.sync()
    return True


def restore_setup(home, write):
    from gi.repository import Gio, GLib
    state = home / '.local/state/oma-theme/appearance-install.json'
    if not state.exists():
        return
    record = json.loads(state.read_text())
    obj = Gio.Settings.new(SCHEMA)
    owned = {'cursor-theme': (CURSOR,), 'icon-theme': (*ICON_NAMES, 'Adwaita')}
    for key, old in record['settings'].items():
        if obj.get_string(key) in owned[key]:
            obj.reset(key) if old is None else obj.set_value(key, GLib.Variant.parse(None, old, None, None))
    for version in (3, 4):
        path = home / f'.config/gtk-{version}.0/settings.ini'
        if not path.exists():
            continue
        text = path.read_text()
        for key, old in record['gtk'][str(version)].items():
            allowed = (CURSOR,) if key == 'gtk-cursor-theme-name' else (*ICON_NAMES, 'Adwaita')
            if ini_value(text, key) in allowed:
                text = ini_set(text, key, old)
        write(path, text.encode(), 0o644)
    Gio.Settings.sync()
    state.unlink()


def default_wallpaper(engine, name):
    manifest_path = engine.HOME / '.local/share/project-largo/manifest.json'
    if not manifest_path.is_file():
        return False
    manifest = json.loads(manifest_path.read_text())
    relative = manifest['themes'].get(name, {}).get('default')
    if relative is None:
        return False
    root = manifest_path.parent
    image = root / relative
    if not image.resolve().is_relative_to(root.resolve()) or not image.is_file():
        raise ValueError('Missing installed default wallpaper for ' + name)
    from gi.repository import Gio
    obj = Gio.Settings.new('org.gnome.desktop.background')
    for key in ('picture-uri', 'picture-uri-dark'):
        obj.set_string(key, image.as_uri())
    obj.set_string('picture-options', 'zoom')
    return True


def enroll_icons(engine):
    """A custom palette after Vanilla re-enrolls the installed icon collection."""
    if not (engine.STATE / 'appearance-install.json').is_file():
        return
    from gi.repository import Gio
    obj = Gio.Settings.new(SCHEMA)
    # Preserve deliberately selected third-party themes after initial setup.
    if obj.get_string('icon-theme') == 'Adwaita':
        obj.set_string('icon-theme', ICONS)
