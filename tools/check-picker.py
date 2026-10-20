#!/usr/bin/python3
"""Exercise GTK controls on disposable Broadway, never the user's display."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def worker():
    sys.path.insert(0, str(Path.home() / '.config/oma-theme'))
    import picker
    from gi.repository import Gio, GLib
    from unittest.mock import patch
    app = picker.PalettePicker()
    app.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
    app.register(None)
    app.activate()
    assert app.setup.get_label() == 'Set up / Refresh integrations'
    assert len(app.window.get_title()) > 0
    states = ['Ready', 'Not installed', 'Setup needed', 'Open app once', 'Restart required',
              'Close app and retry', 'Administrator setup required', 'Failed']
    payload = dict(palette='oma Gruvbox', failed=True,
        results=[dict(app='fixture', target='fixture:' + str(i), state=state,
                      detail='Verification detail', operation='123' if i == 0 else None)
                 for i, state in enumerate(states)])
    def command(args, **kwargs):
        assert args[-2:] == ['setup', '--json']
        return subprocess.CompletedProcess(args, 1, json.dumps(payload), '')
    with patch.object(picker.subprocess, 'run', side_effect=command):
        app.setup.emit('clicked')
        deadline = time.monotonic() + 10
        while app.integration_busy and time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
            time.sleep(0.01)
        assert not app.integration_busy
    labels = []
    child = app.integration_rows.get_first_child()
    while child:
        labels.append(child.get_label())
        child = child.get_next_sibling()
    assert len(labels) == len(states)
    assert all(state in label for state, label in zip(states, labels))
    assert 'project-largo integrations restore 123' in labels[0]
    assert app.setup.get_sensitive()
    assert app.integration_controls[-1].get_label() == 'Set up GDM (Administrator…)'
    app.integration_window.destroy()
    app.window.destroy()
    print('PASS: headless GTK setup action, async completion, eight states, recovery detail and separate admin control')


if __name__ == '__main__':
    if sys.argv[1:] == ['--worker']:
        worker()
    else:
        server = Path('/usr/bin/gtk4-broadwayd')
        if not server.is_file():
            raise SystemExit('GTK4 Broadway is required for this optional headless picker check')
        with tempfile.TemporaryDirectory(prefix='largo-picker-') as temporary:
            home = Path(temporary)
            runtime = home / 'runtime'
            runtime.mkdir(mode=0o700)
            env = dict(os.environ, HOME=str(home), XDG_RUNTIME_DIR=str(runtime),
                       GSETTINGS_BACKEND='memory', GDK_BACKEND='broadway', BROADWAY_DISPLAY=':7')
            subprocess.run([sys.executable, str(ROOT / 'install.py')], env=env, check=True, capture_output=True)
            with subprocess.Popen([str(server), '--address=127.0.0.1', '--port=0', ':7'],
                                  env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as process:
                try:
                    deadline = time.monotonic() + 10
                    while not (runtime / 'broadway7.socket').exists() and time.monotonic() < deadline:
                        if process.poll() is not None:
                            raise RuntimeError(process.stderr.read().decode())
                        time.sleep(0.02)
                    subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker'], env=env,
                                   check=True, timeout=30)
                finally:
                    process.terminate()
                    process.wait(timeout=10)
