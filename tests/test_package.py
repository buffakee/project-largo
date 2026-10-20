"""Meaningful packaging/recovery checks without touching the real desktop."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'src' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class PaletteContract(unittest.TestCase):
    def test_shared_roles_and_readable_pairs(self):
        engine = module('engine')
        palettes = list((ROOT / 'assets/noctalia/palettes').glob('oma *.json'))
        self.assertEqual(len(palettes), 18)
        for path in palettes:
            with self.subTest(palette=path.stem):
                p = json.loads(path.read_text())['dark']
                for text, background in (('mOnSurface', 'mSurface'), ('mOnPrimary', 'mPrimary'),
                                         ('mOnError', 'mError'), ('mOnHover', 'mHover')):
                    self.assertGreaterEqual(engine.contrast(p[text], p[background]), 4.5)
                self.assertEqual(p['terminal']['selectionBg'], p['mPrimary'])
                self.assertEqual(p['terminal']['selectionFg'], p['mOnPrimary'])

    def test_no_machine_absolute_paths_or_runtime_state(self):
        for directory in ('src', 'assets', 'desktop', 'bin'):
            for path in (ROOT / directory).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    with self.subTest(path=path.relative_to(ROOT)):
                        self.assertNotIn(b'/home/buff/', path.read_bytes())
        for relative in ('src/gnome.json', 'src/wallpapers.json', 'assets/noctalia/settings.toml'):
            self.assertFalse((ROOT / relative).exists())


class Recovery(unittest.TestCase):
    def test_vanilla_json_recovery_preserves_unrelated_edits(self):
        vanilla = module('vanilla')
        original = {'theme': 'custom', 'enabledCssSnippets': ['noctalia', 'other'], 'fontSize': 16}
        suspended = {'enabledCssSnippets': ['other'], 'fontSize': 16}
        current = {'enabledCssSnippets': ['other', 'new'], 'fontSize': 19}
        result = vanilla.json_restore(original, suspended, current)
        self.assertEqual(result['theme'], 'custom')
        self.assertEqual(result['fontSize'], 19)
        self.assertEqual(set(result['enabledCssSnippets']), {'noctalia', 'other', 'new'})

    def test_install_repeat_and_uninstall_preserve_previous_files(self):
        if os.geteuid() == 0:
            self.skipTest('Installer is intentionally user-only; run as a non-root user')
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            env = dict(os.environ, HOME=str(home), GSETTINGS_BACKEND='memory')
            def call(*args):
                return subprocess.run([sys.executable, str(ROOT / 'install.py'), *args],
                                      env=env, capture_output=True, text=True, check=True)
            call('--dry-run')
            self.assertEqual(list(home.iterdir()), [])
            gtk = home / '.config/gtk-3.0/gtk.css'
            gtk.parent.mkdir(parents=True)
            original = b'/* Existing user styling must survive removal. */\n'
            gtk.write_bytes(original)
            call()
            self.assertIn(b'noctalia.css', gtk.read_bytes())
            for version in (3, 4):
                css = home / f'.config/gtk-{version}.0/noctalia.css'
                self.assertIn(b'generated when a custom palette is applied', css.read_bytes())
            # Generated colors are runtime state, and reinstall must not erase them.
            colors = home / '.config/gtk-4.0/noctalia.css'
            generated = b'@define-color window_bg_color #202724;\n'
            colors.write_bytes(generated)
            call()
            self.assertEqual(colors.read_bytes(), generated)
            self.assertEqual(gtk.read_bytes().count(b'@import'), 1)
            result = subprocess.run([sys.executable, str(home / '.local/bin/project-largo'), 'list'],
                                    env=env, capture_output=True, text=True, check=True)
            names = result.stdout.splitlines()
            self.assertEqual(len(names), 20)
            self.assertIn('Vanilla Gnome Dark', names)
            self.assertIn('oma Largo', names)
            status = subprocess.run([sys.executable, str(home / '.local/bin/project-largo'),
                                     'integrations', 'status', '--json'], env=env, capture_output=True, text=True)
            self.assertIn(status.returncode, (0, 2), status.stderr)
            report = json.loads(status.stdout)
            self.assertFalse(report['failed'], report)
            self.assertFalse((home / '.local/state/project-largo/integrations').exists(),
                             'Installed CLI status must not create integration state')
            call('--uninstall')
            self.assertEqual(gtk.read_bytes(), original)
            self.assertFalse((home / '.local/bin/project-largo').exists())
            self.assertEqual(colors.read_bytes(), generated)

    def test_removal_refuses_to_discard_later_source_edits(self):
        if os.geteuid() == 0:
            self.skipTest('User-only installer')
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            env = dict(os.environ, HOME=str(home), GSETTINGS_BACKEND='memory')
            command = [sys.executable, str(ROOT / 'install.py')]
            subprocess.run(command, env=env, check=True, capture_output=True)
            source = home / '.config/oma-theme/picker.py'
            source.write_text(source.read_text() + '\n# A later local edit\n')
            result = subprocess.run(command + ['--uninstall'], env=env, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Installed file changed', result.stderr)
            self.assertTrue(source.read_text().endswith('# A later local edit\n'))


class CleanInstall(unittest.TestCase):
    def test_optional_noctalia_settings_and_niri_selection(self):
        engine = module('engine')
        with tempfile.TemporaryDirectory() as directory:
            engine.HOME = Path(directory)
            self.assertEqual(engine.noctalia_settings(), {})
            self.assertEqual(engine.niri_selection(), {})
            self.assertEqual(list(engine.HOME.iterdir()), [])
            settings = engine.HOME / '.local/state/noctalia/settings.toml'
            settings.parent.mkdir(parents=True)
            settings.write_text('[theme]\ncustom_palette = "oma Nord"\n[templates]\nbuiltin_ids = ["btop"]\n')
            self.assertEqual(engine.niri_selection(), {'custom_palette': 'oma Nord'})
            self.assertEqual(engine.noctalia_settings()['templates']['builtin_ids'], ['btop'])

    def test_missing_gresource_is_actionable_before_rendering(self):
        engine = module('engine')
        engine.NOCTALIA = ROOT / 'assets/noctalia'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'render'
            with patch.object(engine.os, 'access', side_effect=lambda path, mode: path != '/usr/bin/gresource'):
                with self.assertRaisesRegex(ValueError, 'gresource.*dnf install glib2-devel'):
                    engine.stage_palette('oma Largo', output)
            self.assertFalse(output.exists())

    def test_gnome_appearance_without_noctalia_settings_and_with_pairings(self):
        if importlib.util.find_spec('gi') is None:
            self.skipTest('PyGObject required for in-memory GNOME settings')
        from gi.repository import Gio
        schema = Gio.SettingsSchemaSource.get_default().lookup('org.gnome.desktop.interface', True)
        if schema is None or not schema.has_key('accent-color'):
            self.skipTest('GNOME appearance test requires a schema with accent-color (GNOME 47+)')
        code = r'''
import tempfile
from pathlib import Path
from unittest.mock import Mock
from gi.repository import Gio
import engine
with tempfile.TemporaryDirectory() as directory:
    engine.HOME = Path(directory)
    engine.STATE = engine.HOME / '.local/state/oma-theme'
    interface = Gio.Settings.new(engine.SCHEMA)
    background = Gio.Settings.new('org.gnome.desktop.background')
    shell = Mock()
    shell.get_string.return_value = ''
    engine.settings_objects = lambda: {
        engine.SCHEMA: interface,
        'org.gnome.desktop.background': background,
        'org.gnome.shell.extensions.user-theme': shell,
    }
    original = {'picture-uri': 'file:///tmp/original-light.jpg',
                'picture-uri-dark': 'file:///tmp/original-dark.jpg', 'picture-options': 'scaled'}
    for key, value in original.items(): background.set_string(key, value)
    tokens = {'primary': '#91ad85'}
    engine.appearance(tokens, 'oma Largo', 'gnome')
    assert {key: background.get_string(key) for key in original} == original
    assert not (engine.HOME / '.local/state/noctalia/settings.toml').exists()
    assert interface.get_string('color-scheme') == 'prefer-dark'
    shell.set_string.assert_called_with('name', 'Oma-GNOME-a')
    # Existing optional favorites still work.
    image = engine.HOME / 'favorite.jpg'
    image.touch()
    settings = engine.HOME / '.local/state/noctalia/settings.toml'
    settings.parent.mkdir(parents=True)
    settings.write_text('[[wallpaper.favorite]]\ncustom_palette = "oma Largo"\npath = "' + str(image) + '"\n')
    engine.appearance(tokens, 'oma Largo', 'gnome')
    assert background.get_string('picture-uri') == image.as_uri()
    assert background.get_string('picture-uri-dark') == image.as_uri()
    # Saved GNOME wallpaper memory takes precedence over optional favorites.
    for key, value in original.items(): background.set_string(key, value)
    engine.remember_wallpaper('oma Largo')
    background.set_string('picture-uri', image.as_uri())
    engine.appearance(tokens, 'oma Largo', 'gnome')
    assert {key: background.get_string(key) for key in original} == original
'''
        env = dict(os.environ, GSETTINGS_BACKEND='memory', PYTHONPATH=str(ROOT / 'src'))
        result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class WallpaperMemory(unittest.TestCase):
    def test_independent_uri_slots_validation_and_startup_restore(self):
        if importlib.util.find_spec('gi') is None:
            self.skipTest('PyGObject is required for the optional memory-backend check')
        code = r'''
import importlib.util, json, tempfile
from pathlib import Path
import engine
engine.NOCTALIA = engine.ROOT.parent / 'assets/noctalia'
w = engine.load_module('wallpaper', engine.ROOT / 'wallpaper.py')
with tempfile.TemporaryDirectory() as directory:
    engine.STATE = Path(directory)
    obj = w.settings()
    a = {'picture-uri':'file:///tmp/light-a.png','picture-uri-dark':'file:///tmp/dark-a.png','picture-options':'zoom'}
    b = {'picture-uri':'file:///tmp/light-b.png','picture-uri-dark':'file:///tmp/dark-b.png','picture-options':'scaled'}
    for key,value in a.items(): obj.set_string(key,value)
    engine.remember_wallpaper('Vanilla Gnome')
    for key,value in b.items(): obj.set_string(key,value)
    engine.remember_wallpaper('Vanilla Gnome Dark')
    assert engine.restore_wallpaper('Vanilla Gnome')
    assert {key:obj.get_string(key) for key in w.KEYS} == a
    assert engine.restore_wallpaper('Vanilla Gnome Dark')
    assert {key:obj.get_string(key) for key in w.KEYS} == b
    saved = (engine.STATE/'wallpapers.json').read_bytes()
    data = w.load(engine)
    data['themes']['Vanilla Gnome']['picture-options'] = 'invalid'
    (engine.STATE/'wallpapers.json').write_text(json.dumps(data))
    try: engine.restore_wallpaper('Vanilla Gnome')
    except ValueError: pass
    else: raise AssertionError('Invalid option accepted')
    assert {key:obj.get_string(key) for key in w.KEYS} == b
    (engine.STATE/'wallpapers.json').write_bytes(saved)
    engine.atomic(engine.STATE/'gnome.json','{"palette":"Vanilla Gnome"}')
    # Avoid real publication while exercising the real switching wrapper.
    engine._apply_custom = lambda *args: None
    engine.apply('oma Largo')
    assert w.load(engine)['themes']['Vanilla Gnome'] == b
    for key,value in a.items(): obj.set_string(key,value)
    engine.apply('oma Largo', restore=True)
    assert w.load(engine)['themes']['Vanilla Gnome'] == b
'''
        env = dict(os.environ, GSETTINGS_BACKEND='memory', PYTHONPATH=str(ROOT / 'src'))
        result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
