#!/usr/bin/python3
"""Parse adapted GDM resources for every palette without installing anything."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import gdm_admin
from renderer import NoctaliaRenderer


def main():
    backend = NoctaliaRenderer()
    env = dict(os.environ, GI_TYPELIB_PATH='/usr/lib64/gnome-shell:/usr/lib64/mutter-18',
               LD_LIBRARY_PATH='/usr/lib64/gnome-shell:/usr/lib64/mutter-18')
    with tempfile.TemporaryDirectory(prefix='largo-gdm-check-') as temporary:
        for palette in sorted((ROOT / 'assets/noctalia/palettes').glob('oma *.json')):
            directory = Path(temporary) / palette.stem
            directory.mkdir()
            tokens, _ = backend.render(json.loads(palette.read_text()), [], directory)
            request = dict(version=1, vanilla=False, palette=palette.stem, tokens=tokens)
            gdm_admin.render(request, directory)
            for variant in ('dark', 'light'):
                subprocess.run(['/usr/bin/python3', '-I', '-c',
                    'import gi,sys; gi.require_version("St","18"); from gi.repository import St,Gio; '
                    'St.Theme().load_stylesheet(Gio.File.new_for_path(sys.argv[1]))',
                    str(directory / f'gnome-shell-{variant}.css')], env=env, check=True, timeout=30)
            print(palette.stem, 'PASS (GDM dark/light)')
        for light in (True, False):
            directory = Path(temporary) / ('vanilla-light' if light else 'vanilla-dark')
            directory.mkdir()
            gdm_admin.render(dict(version=1, vanilla=True, light=light, palette='Vanilla'), directory)
            stock = gdm_admin.command('/usr/bin/gresource', 'extract', gdm_admin.RESOURCE,
                                      f'/org/gnome/shell/theme/gnome-shell-{"light" if light else "dark"}.css')
            for variant in ('dark', 'light'):
                assert (directory / f'gnome-shell-{variant}.css').read_text() == stock
        print('PASS: 36 native GDM stylesheet parses and exact Vanilla stock resources; no system installation or login test')


if __name__ == '__main__':
    main()
