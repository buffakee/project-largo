#!/usr/bin/python3
"""Native fresh-home appearance switching/recovery check; no real desktop writes."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def worker():
    import gi
    gi.require_version('GdkPixbuf', '2.0')
    from gi.repository import Gio, GdkPixbuf
    spec = importlib.util.spec_from_file_location('installer', ROOT / 'install.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    interface = Gio.Settings.new('org.gnome.desktop.interface')
    interface.set_string('cursor-theme', 'Adwaita')
    interface.set_int('cursor-size', 32)
    interface.set_string('icon-theme', 'Adwaita')
    installer.install()
    assert interface.get_string('cursor-theme') == 'Bibata-Modern-Ice'
    assert interface.get_int('cursor-size') == 32
    assert interface.get_string('icon-theme') == 'yet-another-monochrome-icon-set'
    assert (Path.home() / '.local/share/icons/Bibata-Modern-Ice/cursors/left_ptr').read_bytes().startswith(b'Xcur')
    for image in (Path.home() / '.local/share/project-largo/wallpapers').iterdir():
        info = GdkPixbuf.Pixbuf.get_file_info(str(image))
        assert info[0] is not None and info[1] > 0 and info[2] > 0, image
    # Provide only the Shell extension schema in the isolated home.
    schemas = Path.home() / '.local/share/gnome-shell/extensions/user-theme@gnome-shell-extensions.gcampax.github.com/schemas'
    schemas.mkdir(parents=True)
    (schemas / 'theme.gschema.xml').write_text('''<schemalist><schema id="org.gnome.shell.extensions.user-theme" path="/org/gnome/shell/extensions/user-theme/"><key name="name" type="s"><default>''</default></key></schema></schemalist>''')
    subprocess.run(['/usr/bin/glib-compile-schemas', str(schemas)], check=True)
    sys.path.insert(0, str(Path.home() / '.config/oma-theme'))
    import engine
    # Never contact the live Shell or refresh unrelated real applications.
    engine.shell_status = lambda: {'active': True, 'test': 'memory backend'}
    native_load = engine.load_module
    def load(name, path):
        module = native_load(name, path)
        if Path(path).name == 'vanilla.py':
            module.hook = lambda command: {'ok': True, 'detail': 'External application refresh isolated'}
        return module
    engine.load_module = load
    yamis = native_load('yamis', engine.NOCTALIA / 'yamis-colour.py')
    native_run = subprocess.run
    def command(args, **kwargs):
        # Bridge only the helper's gsettings CLI to the same in-memory backend.
        if args[0] == '/usr/bin/gsettings':
            if args[1] == 'get':
                return None
            interface.set_string(args[3], args[4])
            return subprocess.CompletedProcess(args, 0)
        return native_run(args, **kwargs)
    def refresh(changed_paths=()):
        with patch.object(yamis.subprocess, 'check_output', return_value=repr(interface.get_string('icon-theme'))), \
             patch.object(yamis.subprocess, 'run', side_effect=command):
            yamis.main()
        return {'icons': {'ok': True}}
    engine.refresh_apps = refresh
    background = Gio.Settings.new('org.gnome.desktop.background')
    background.set_string('picture-uri', 'file:///tmp/original-background.jpg')
    background.set_string('picture-uri-dark', 'file:///tmp/original-background.jpg')
    # First application must not remember Fedora's background as Gruvbox's choice.
    engine.apply('oma Gruvbox')
    assert 'gruvbox_1-the-backwater.jpg' in background.get_string('picture-uri')
    manifest = json.loads((Path.home() / '.local/share/project-largo/manifest.json').read_text())
    for name, entry in manifest['themes'].items():
        if entry['default']:
            assert engine.default_wallpaper(name)
            assert background.get_string('picture-uri') == (Path.home() / '.local/share/project-largo' / entry['default']).as_uri()
            assert background.get_string('picture-uri-dark') == background.get_string('picture-uri')
    assert not engine.default_wallpaper('oma Solarized')
    engine.apply('oma Largo')
    slot_a = interface.get_string('icon-theme')
    assert slot_a.startswith('yamis-noctalia-')
    assert (Path.home() / '.local/share/icons' / slot_a / '.noctalia-accent').read_text().strip() == '#ede0b7'
    assert '#ede0b7' in (Path.home() / '.local/share/icons' / slot_a / 'apps/scalable/firefox.svg').read_text()
    # A user's later choice takes precedence over the bundled default.
    background.set_string('picture-uri', 'file:///tmp/custom-light.jpg')
    background.set_string('picture-uri-dark', 'file:///tmp/custom-dark.jpg')
    engine.apply('oma Nord')
    slot_b = interface.get_string('icon-theme')
    assert slot_a != slot_b
    assert (Path.home() / '.local/share/icons' / slot_b / '.noctalia-accent').read_text().strip() == '#d8dee9'
    assert '#d8dee9' in (Path.home() / '.local/share/icons' / slot_b / 'apps/scalable/firefox.svg').read_text()
    engine.apply('oma Largo')
    assert background.get_string('picture-uri') == 'file:///tmp/custom-light.jpg'
    assert background.get_string('picture-uri-dark') == 'file:///tmp/custom-dark.jpg'
    engine.apply('Vanilla Gnome')
    assert interface.get_string('icon-theme') == 'Adwaita'
    assert interface.get_string('cursor-theme') == 'Bibata-Modern-Ice'
    assert interface.get_int('cursor-size') == 32
    engine.apply('Vanilla Gnome Dark')
    assert interface.get_string('color-scheme') == 'prefer-dark'
    engine.apply('oma Largo')
    assert interface.get_string('icon-theme').startswith('yamis-noctalia-')
    assert background.get_string('picture-uri') == 'file:///tmp/custom-light.jpg'
    # Reinstall must not reset cursor choice, size, icon slot or wallpaper memory.
    interface.set_string('cursor-theme', 'UserCursor')
    previous_icons = interface.get_string('icon-theme')
    memory = (engine.STATE / 'wallpapers.json').read_bytes()
    installer.install()
    assert interface.get_string('cursor-theme') == 'UserCursor'
    assert interface.get_string('icon-theme') == previous_icons
    assert (engine.STATE / 'wallpapers.json').read_bytes() == memory
    # Restore the bundled default on explicit request, then restore prior settings.
    assert engine.default_wallpaper('oma Largo')
    assert 'largo_wallpaper_1_desktop.jpg' in background.get_string('picture-uri')
    engine.apply('Vanilla Gnome')
    interface.set_string('cursor-theme', 'Bibata-Modern-Ice')
    installer.uninstall()
    assert interface.get_string('cursor-theme') == 'Adwaita'
    assert interface.get_string('icon-theme') == 'Adwaita'
    assert interface.get_int('cursor-size') == 32
    print('PASS: native fresh install, 17 wallpaper defaults, 2 icon colors/slots, Light/Dark/custom recovery, reinstall and removal')


if __name__ == '__main__':
    if sys.argv[1:] == ['--worker']:
        worker()
    else:
        with tempfile.TemporaryDirectory(prefix='largo-appearance-') as home:
            env = dict(os.environ, HOME=home, GSETTINGS_BACKEND='memory')
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker'], env=env, check=True)
