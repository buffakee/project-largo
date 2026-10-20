#!/usr/bin/python3
"""Use each toolkit's own CSS parser in a separate process."""
from pathlib import Path
import sys
import gi

version, directory = sys.argv[1], Path(sys.argv[2])
if version == 'shell':
    gi.require_version('St', '18')
    from gi.repository import Gio, St
    theme = St.Theme()
    theme.load_stylesheet(Gio.File.new_for_path(str(directory / 'gnome-shell.css')))
    print('GNOME Shell native CSS parser passed')
else:
    gi.require_version('Gtk', version)
    from gi.repository import Gtk
    paths = list(directory.glob('*-roles-gtk' + version[0] + '.css'))
    if version == '3.0':
        Gtk.init_check([])
        paths += list((directory / 'home/.local/share/themes').glob('*/gtk-3.0/gtk.css'))
    errors = []
    for path in paths:
        provider = Gtk.CssProvider()
        provider.connect('parsing-error', lambda _p, _s, error: errors.append(str(error)))
        provider.load_from_path(str(path))
    if errors:
        raise SystemExit('\n'.join(errors))
    print('GTK', version, len(paths), 'native CSS parses passed')
