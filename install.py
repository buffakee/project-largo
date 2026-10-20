#!/usr/bin/python3
"""Install the current Project Largo snapshot into the calling user's home."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
import appearance

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
BACKUP = HOME / '.local/state/oma-theme/project-largo-install'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def plan(home=HOME):
    files = {}
    for source_dir, destination in (
        (ROOT / 'src', home / '.config/oma-theme'),
        (ROOT / 'assets/noctalia', home / '.config/noctalia'),
        (ROOT / 'assets/community', home / '.local/state/noctalia/community-templates'),
    ):
        for source in sorted(source_dir.rglob('*')):
            if source.is_file() and '__pycache__' not in source.parts and source.suffix != '.pyc':
                files[destination / source.relative_to(source_dir)] = (source.read_bytes(), 0o644)
    launcher = (ROOT / 'bin/project-largo').read_bytes()
    for name in ('project-largo', 'oma-theme'):
        files[home / '.local/bin' / name] = (launcher, 0o755)
    # Keep existing technical IDs so upgrades do not duplicate launchers or memory.
    for template, destination in (
        ('oma-themes.desktop.in', '.local/share/applications/oma-themes.desktop'),
        ('oma-theme-gnome.desktop.in', '.config/autostart/oma-theme-gnome.desktop'),
        ('oma-wallpaper-memory.service.in', '.config/systemd/user/oma-wallpaper-memory.service'),
    ):
        text = (ROOT / 'desktop' / template).read_text().replace('@HOME@', str(home))
        files[home / destination] = (text.encode(), 0o644)
    for version in (3, 4):
        path = home / f'.config/gtk-{version}.0/gtk.css'
        text = path.read_text() if path.exists() else ''
        if 'noctalia.css' not in text:
            text += '\n/* Project Largo palette colors */\n@import url("noctalia.css");\n'
        files[path] = (text.encode(), 0o644)
    files.update(appearance.asset_files(ROOT / 'assets/appearance', home))
    return files


def write(path, data, mode):
    if path.is_symlink():
        path = path.resolve(strict=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def install(dry_run=False):
    files = plan()
    if dry_run:
        print(f'Project Largo: {len(files)} source/configuration files would be installed under {HOME}')
        print('No files, GNOME settings, services or application profiles were changed.')
        return
    BACKUP.mkdir(parents=True, exist_ok=True, mode=0o700)
    BACKUP.chmod(0o700)
    manifest = BACKUP / 'files.json'
    records = json.loads(manifest.read_text()) if manifest.exists() else []
    known = {record['path']: record for record in records}
    # Capture every previous file before publishing any installation files.
    for path, (data, mode) in files.items():
        target = path.resolve(strict=True) if path.is_symlink() else path
        if str(target) not in known:
            record = {'path': str(target), 'exists': target.is_file(), 'file': str(len(records)),
                      'mode': target.stat().st_mode & 0o777 if target.exists() else mode}
            if record['exists']:
                write(BACKUP / record['file'], target.read_bytes(), 0o600)
            records.append(record)
            known[str(target)] = record
        known[str(target)]['installed_sha256'] = digest(data)
    write(manifest, (json.dumps(records, indent=2) + '\n').encode(), 0o600)
    # These are mutable runtime outputs, not installer-owned source files.
    # Seed absent outputs before publishing their imports; never replace a palette.
    for version in (3, 4):
        css = HOME / f'.config/gtk-{version}.0/noctalia.css'
        if not css.exists():
            write(css, b'/* Project Largo colors are generated when a custom palette is applied. */\n', 0o644)
    for path, (data, mode) in files.items():
        write(path, data, mode)
    enrolled = appearance.setup(HOME, write)
    print('Installed Project Largo, associated wallpapers, Bibata Modern Ice and YAMIS icons.')
    print('Selected Bibata/YAMIS for initial appearance setup.' if enrolled else 'Existing appearance enrollment retained; selections preserved.')
    print('No color palette was applied and no service was started.')
    print('Enable GNOME User Themes, then launch ~/.local/bin/project-largo pick.')
    print('To enable immediate wallpaper saving:')
    print('  systemctl --user daemon-reload')
    print('  systemctl --user enable --now oma-wallpaper-memory.service')
    print('Installer rollback manifest:', manifest)


def uninstall():
    manifest = BACKUP / 'files.json'
    if not manifest.is_file():
        raise SystemExit('No Project Largo installation manifest found.')
    state = HOME / '.local/state/oma-theme/gnome.json'
    if state.exists() and json.loads(state.read_text()).get('palette') not in ('Vanilla Gnome', 'Vanilla Gnome Dark'):
        raise SystemExit('Apply Vanilla Gnome first, then disable the wallpaper service before uninstalling. See README.')
    records = json.loads(manifest.read_text())
    # Source edits should not be silently discarded during removal.
    for record in records:
        path = Path(record['path'])
        if path.exists() and digest(path.read_bytes()) != record['installed_sha256']:
            raise SystemExit('Installed file changed; preserve/review it before uninstalling: ' + str(path))
    appearance.restore_setup(HOME, write)
    for record in reversed(records):
        path = Path(record['path'])
        if record['exists']:
            write(path, (BACKUP / record['file']).read_bytes(), record['mode'])
        else:
            path.unlink(missing_ok=True)
    print('Restored installer-owned files. Runtime memories and recovery snapshots remain under ~/.local/state/oma-theme.')
    print('Run systemctl --user daemon-reload after removal.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--dry-run', action='store_true')
    group.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('Run as your desktop user, without sudo.')
    uninstall() if args.uninstall else install(args.dry_run)


if __name__ == '__main__':
    main()
