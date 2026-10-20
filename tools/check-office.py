#!/usr/bin/python3
"""Install/verify/restore the real native extension in a disposable profile only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def worker():
    sys.path.insert(0, str(Path.home() / '.config/oma-theme'))
    import engine
    import integration_apps
    import integrations
    home = Path.home()
    profile = home / '.config/libreoffice/4/user'
    profile.mkdir(parents=True)
    original = b'<oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/fixture"><prop oor:name="Keep"><value>preserve</value></prop></item></oor:items>'
    (profile / 'registrymodifications.xcu').write_bytes(original)
    # One deterministic desktop route, never launched by this check.
    launcher = home / '.local/share/applications/libreoffice-startcenter.desktop'
    launcher.write_text('[Desktop Entry]\nType=Application\nName=LibreOffice\nExec=/usr/bin/libreoffice %U\nMimeType=application/x-fixture;\n')
    context = integrations.Context()
    context.flatpak = lambda name: False
    # This profile is exclusively owned by this test and cannot be used by a live
    # suite. Both HOME and UserInstallation are isolated; no default profile call.
    context.processes = lambda names: []
    with integrations.locked(context), tempfile.TemporaryDirectory(prefix='render-', dir=home) as temporary:
        # Optional unrelated client corruption must not block first-run setup.
        optional = [home / '.config/fastfetch/config.jsonc', home / '.config/starship.toml']
        for path in optional:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('deliberately invalid optional client configuration {{{')
        artifacts, _ = engine.stage_integrations('oma Largo', Path(temporary) / 'setup')
        for path in optional:
            assert path.read_text() == 'deliberately invalid optional client configuration {{{'
            path.unlink()
        full, _, _ = engine.stage_palette('oma Largo', Path(temporary) / 'full', desktop='niri')
        assert all(full[path] == value for path, value in artifacts.items()), 'Setup and normal application artifacts diverged'
        report = integrations.execute(context, 'setup', app='libreoffice', artifacts=artifacts, palette='oma Largo')
        print(json.dumps(report, indent=2))
        row = next(r for r in report['results'] if r['target'].startswith('libreoffice:native:'))
        assert row['state'] == 'Restart required', row
        for desktop in (home / '.local/share/applications').glob('libreoffice*.desktop'):
            subprocess.run(['/usr/bin/desktop-file-validate', str(desktop)], check=True)
        adapter = integration_apps.LibreOffice(context)
        target = next(t for t in adapter.discover() if t['backend'] == 'native')
        assert adapter.extension_matches(target, adapter.office_colors(artifacts))
        again = integrations.execute(context, 'repair', app='libreoffice', artifacts=artifacts, palette='oma Largo')
        assert not again['failed'], again
        integrations.restore(context, row['operation'])
        assert (profile / 'registrymodifications.xcu').read_bytes() == original
        assert 'Exec=/usr/bin/libreoffice %U' in launcher.read_text()
    print('PASS: real native unopkg enrollment, exact registration/colors, idempotent repair and profile/launcher restoration in a disposable home')


if __name__ == '__main__':
    if sys.argv[1:] == ['--worker']:
        worker()
    else:
        if not shutil.which('unopkg'):
            raise SystemExit('Native LibreOffice/unopkg and GTK3 plugin are required for this optional check')
        with tempfile.TemporaryDirectory(prefix='largo-native-office-') as temporary:
            home = Path(temporary)
            env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
                       XDG_DATA_HOME=str(home / '.local/share'), XDG_STATE_HOME=str(home / '.local/state'),
                       XDG_CACHE_HOME=str(home / '.cache'), GSETTINGS_BACKEND='memory', SAL_USE_VCLPLUGIN='svp')
            subprocess.run([sys.executable, str(ROOT / 'install.py')], env=env, check=True, capture_output=True)
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker'], env=env, check=True, timeout=120)
