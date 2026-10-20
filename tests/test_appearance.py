"""Appearance enrollment/recovery checks independent of a running desktop."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Appearance(unittest.TestCase):
    def test_ini_edits_preserve_comments_and_unrelated_sections(self):
        spec = importlib.util.spec_from_file_location('appearance', ROOT / 'src/appearance.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = '# User comment\n[Settings]\n# Keep this\ngtk-icon-theme-name=Old\ngtk-font-name=Example 12\n[Other]\ngtk-icon-theme-name=Unrelated\n'
        updated = module.ini_set(original, 'gtk-icon-theme-name', 'New')
        self.assertIn('# User comment', updated)
        self.assertIn('# Keep this', updated)
        self.assertIn('gtk-font-name=Example 12', updated)
        self.assertIn('[Other]\ngtk-icon-theme-name=Unrelated', updated)
        self.assertEqual(module.ini_set(updated, 'gtk-icon-theme-name', 'Old'), original)
        removed = module.ini_set(updated, 'gtk-icon-theme-name', None)
        self.assertIsNone(module.ini_value(removed, 'gtk-icon-theme-name'))
        self.assertIn('[Other]\ngtk-icon-theme-name=Unrelated', removed)

    def test_enrollment_is_once_and_restores_only_owned_selections(self):
        if importlib.util.find_spec('gi') is None:
            self.skipTest('PyGObject required for in-memory settings')
        code = r'''
from pathlib import Path
import tempfile
from gi.repository import Gio
import appearance
with tempfile.TemporaryDirectory() as directory:
    home = Path(directory)
    def write(path, data, mode):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    obj = Gio.Settings.new(appearance.SCHEMA)
    obj.set_string('icon-theme', 'OriginalIcons')
    obj.set_string('cursor-theme', 'OriginalCursor')
    obj.set_int('cursor-size', 48)
    ini = home / '.config/gtk-3.0/settings.ini'
    write(ini, b'# Comment\n[Settings]\ngtk-icon-theme-name=OriginalIcons\ngtk-font-name=UserFont 13\n', 0o644)
    assert appearance.setup(home, write)
    assert obj.get_string('cursor-theme') == appearance.CURSOR
    assert obj.get_string('icon-theme') == appearance.ICONS
    assert obj.get_int('cursor-size') == 48
    saved = (home / '.local/state/oma-theme/appearance-install.json').read_bytes()
    obj.set_string('cursor-theme', 'LaterCursor')
    obj.set_string('icon-theme', 'LaterIcons')
    assert not appearance.setup(home, write)
    assert obj.get_string('cursor-theme') == 'LaterCursor'
    assert obj.get_string('icon-theme') == 'LaterIcons'
    assert (home / '.local/state/oma-theme/appearance-install.json').read_bytes() == saved
    appearance.restore_setup(home, write)
    assert obj.get_string('cursor-theme') == 'LaterCursor'
    assert obj.get_string('icon-theme') == 'LaterIcons'
    assert '# Comment' in ini.read_text() and 'gtk-font-name=UserFont 13' in ini.read_text()
    assert appearance.ini_value(ini.read_text(), 'gtk-icon-theme-name') == 'OriginalIcons'
    assert appearance.ini_value(ini.read_text(), 'gtk-cursor-theme-name') is None
    appearance.setup(home, write)
    appearance.restore_setup(home, write)
    assert obj.get_string('cursor-theme') == 'LaterCursor'
    assert obj.get_string('icon-theme') == 'LaterIcons'
    assert obj.get_int('cursor-size') == 48
'''
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True,
            env=dict(os.environ, GSETTINGS_BACKEND='memory', PYTHONPATH=str(ROOT / 'src')))
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
