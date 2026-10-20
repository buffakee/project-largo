#!/usr/bin/python3
"""GNOME-only per-preset wallpaper memory, serialized with palette application."""
import fcntl
import json
from pathlib import Path
import sys

KEYS = ('picture-uri', 'picture-uri-dark', 'picture-options')


def settings():
    from gi.repository import Gio
    return Gio.Settings.new('org.gnome.desktop.background')


def load(engine):
    path = engine.STATE / 'wallpapers.json'
    data = json.loads(path.read_text()) if path.exists() else {'version': 1, 'themes': {}}
    if data.get('version') != 1 or not isinstance(data.get('themes'), dict):
        raise ValueError('Unsupported wallpaper memory format')
    return data


def remember(engine, name):
    """Caller must hold apply.lock; never infer a Niri theme from GNOME state."""
    if name not in engine.presets():
        return
    data = load(engine)
    obj = settings()
    data['themes'][name] = {key: obj.get_string(key) for key in KEYS}
    engine.atomic(engine.STATE / 'wallpapers.json', json.dumps(data, indent=2) + '\n')


def restore(engine, name):
    saved = load(engine)['themes'].get(name)
    if saved is None:
        return False
    if set(saved) != set(KEYS) or not all(isinstance(saved[key], str) for key in KEYS):
        raise ValueError('Invalid wallpaper memory for ' + name)
    obj = settings()
    # Validate the whole record before changing anything.
    from gi.repository import GLib
    for key in KEYS:
        if not obj.props.settings_schema.get_key(key).range_check(GLib.Variant('s', saved[key])):
            raise ValueError('Invalid saved background setting: ' + key)
    for key in KEYS:
        obj.set_string(key, saved[key])
    return True


def watch():
    import engine
    from gi.repository import Gio, GLib
    engine.STATE.mkdir(parents=True, exist_ok=True)
    obj = settings()
    pending = 0

    def save():
        nonlocal pending
        if not (engine.STATE / 'gnome.json').exists():
            pending = 0
            return GLib.SOURCE_REMOVE
        # Changes made during a palette transaction are coalesced and sampled
        # only after gnome.json identifies the successfully applied destination.
        with (engine.STATE / 'apply.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return GLib.SOURCE_CONTINUE
            remember(engine, engine.selection()['palette'])
            Gio.Settings.sync()
        pending = 0
        return GLib.SOURCE_REMOVE

    def changed(_settings, key):
        nonlocal pending
        if key in KEYS:
            if pending:
                GLib.source_remove(pending)
            pending = GLib.timeout_add(300, save)

    obj.connect('changed', changed)
    # Existing memory is restored by the palette autostart. Do not replace it
    # with an intermediate login background just because the listener started.
    GLib.MainLoop().run()


if __name__ == '__main__':
    if sys.argv[1:] != ['watch']:
        raise SystemExit('Usage: wallpaper.py watch')
    watch()
