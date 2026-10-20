#!/usr/bin/python3
"""Standalone root-owned GDM publisher and explicit setup/restore tool.

No imports or executable input from a user's home. GNOME Shell 50 only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import tempfile
import time

CONFIG = Path('/etc/project-largo-gdm.json')
TARGET = Path('/usr/local/share/project-largo/gdm')
HELPER = Path('/usr/local/libexec/project-largo-gdm')
BACKUP = Path('/var/lib/project-largo-gdm-backup')
RESOURCE = '/usr/share/gnome-shell/gnome-shell-theme.gresource'
KEYS = ('surface', 'surface_container', 'surface_container_high', 'on_surface',
        'on_surface_variant', 'hover', 'primary', 'on_primary', 'shadow',
        'error', 'on_error', 'terminal_normal_yellow')


def command(*args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, capture_output=True,
                          text=True, timeout=60, **kwargs).stdout


def atomic(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('Review existing symlink before setup: ' + str(path))
    fd, name = tempfile.mkstemp(prefix='.largo-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def validate(request):
    if request.get('version') != 1 or type(request.get('vanilla')) is not bool or type(request.get('light', False)) is not bool:
        raise ValueError('Invalid GDM request')
    if not isinstance(request.get('palette'), str) or len(request['palette']) > 128:
        raise ValueError('Invalid palette identity')
    if not request['vanilla']:
        for key in KEYS:
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', request.get('tokens', {}).get(key, '')):
                raise ValueError('Invalid GDM token: ' + key)
    if 'wallpaper' in request and not re.fullmatch(r'[0-9a-f]{64}', request['wallpaper']):
        raise ValueError('Invalid wallpaper identifier')


def read_request_file(directory_fd, name, maximum, uid):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_size > maximum:
            raise ValueError('Invalid request owner, size or type')
        data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError('Request exceeds maximum size')
        return data


def css(tokens, stock, wallpaper=False):
    def rgb(value):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))

    def color(value):
        value = value.lower()
        channels = rgb(value)
        if value == '#000000':
            return value
        if max(channels) - min(channels) > 30:
            return tokens['terminal_normal_yellow' if channels[1] > 80 else 'error']
        if value == '#222226':
            return tokens['surface']
        if value in ('#2e2e33', '#333333', '#38383b'):
            return tokens['surface_container']
        if value == '#36363a':
            return tokens['surface_container_high']
        return tokens['on_surface' if max(channels) >= 200 else 'on_surface_variant' if max(channels) >= 110 else 'hover']

    def replace(match):
        if match[0] == '-st-accent-fg-color':
            return tokens['on_primary']
        if match[0] == '-st-accent-color':
            return tokens['primary']
        if match[0].startswith('#'):
            return color(match[0])
        original = '#' + ''.join(f'{int(match[i]):02x}' for i in (1, 2, 3))
        return 'rgba(' + ', '.join(map(str, rgb(color(original)))) + ', ' + match[4] + ')'

    pattern = r'#[0-9a-fA-F]{6}\b|rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)|-st-accent-fg-color|-st-accent-color'
    result = re.sub(pattern, replace, stock)
    image = 'background-image: url("resource:///org/gnome/shell/theme/largo-wallpaper.png"); background-size: cover; background-position: center;' if wallpaper else ''
    return result + f'''
/* Project Largo GDM: native geometry retained. */
#lockDialogGroup {{ background-color: {tokens['surface']}; {image} }}
#panel.login-screen {{ background-color: {tokens['shadow']}; color: {tokens['on_surface']}; }}
.login-dialog {{ color: {tokens['on_surface']}; }}
.login-dialog-user-list-item {{ background-color: {tokens['surface']}; color: {tokens['on_surface']}; }}
.login-dialog-user-list-item:hover {{ background-color: {tokens['hover']}; }}
.login-dialog-user-list-item:selected, .login-dialog-user-list-item:focus {{ background-color: {tokens['primary']}; color: {tokens['on_primary']}; }}
.login-dialog StEntry {{ background-color: {tokens['surface_container']}; color: {tokens['on_surface']}; selection-background-color: {tokens['primary']}; selected-color: {tokens['on_primary']}; }}
.login-dialog .button.default {{ background-color: {tokens['primary']}; color: {tokens['on_primary']}; }}
'''


def render(request, directory, image=None):
    validate(request)
    version = command('/usr/bin/gnome-shell', '--version')
    custom = not request['vanilla'] and bool(re.search(r'\b50\.', version))
    for variant in ('dark', 'light'):
        stock_variant = ('light' if request.get('light') else 'dark') if request['vanilla'] else variant
        stock = command('/usr/bin/gresource', 'extract', RESOURCE, f'/org/gnome/shell/theme/gnome-shell-{stock_variant}.css')
        (directory / f'gnome-shell-{variant}.css').write_text(css(request['tokens'], stock, image is not None) if custom else stock)
    if custom and image is not None:
        (directory / 'largo-wallpaper.png').write_bytes(image)
    status = {k: request.get(k) for k in ('palette', 'desktop', 'vanilla', 'wallpaper')}
    status['request_sha256'] = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    (directory / 'status.json').write_text(json.dumps(status) + '\n')


def publish():
    config = json.loads(CONFIG.read_text())
    account = pwd.getpwuid(config['uid'])
    if account.pw_dir != config['home']:
        raise ValueError('Account home changed; administrator setup required')
    source = Path(config['home']) / '.local/state/project-largo/gdm'
    fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        request = json.loads(read_request_file(fd, 'request.json', 65536, config['uid']))
        validate(request)
        image = None
        if request.get('wallpaper') and not request['vanilla']:
            image = read_request_file(fd, request['wallpaper'] + '.png', 32 * 1024 * 1024, config['uid'])
            if hashlib.sha256(image).hexdigest() != request['wallpaper'] or not image.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Invalid wallpaper data')
    finally:
        os.close(fd)
    TARGET.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='generation-', dir=TARGET))
    try:
        render(request, directory, image)
        env = dict(os.environ, GI_TYPELIB_PATH='/usr/lib64/gnome-shell:/usr/lib64/mutter-18',
                   LD_LIBRARY_PATH='/usr/lib64/gnome-shell:/usr/lib64/mutter-18')
        # Current Shell 50 parser. New majors retain stock CSS; review before custom support.
        if re.search(r'\b50\.', command('/usr/bin/gnome-shell', '--version')):
            for variant in ('dark', 'light'):
                command('/usr/bin/python3', '-I', '-c',
                    'import gi,sys; gi.require_version("St","18"); from gi.repository import St,Gio; '
                    'St.Theme().load_stylesheet(Gio.File.new_for_path(sys.argv[1]))',
                    directory / f'gnome-shell-{variant}.css', env=env)
        directory.chmod(0o755)
        for file in directory.iterdir():
            file.chmod(0o644)
        if Path('/usr/sbin/restorecon').is_file():
            command('/usr/sbin/restorecon', '-RF', directory)
        link = TARGET / '.current-new'
        link.unlink(missing_ok=True)
        link.symlink_to(directory.name)
        link.replace(TARGET / 'current')
    except Exception:
        shutil.rmtree(directory)
        raise


def setup_files(account, source):
    home = account.pw_dir
    if any(c in home for c in '\n\r%') or not re.fullmatch(r'/[A-Za-z0-9_./-]+', home):
        raise ValueError('Unsupported account home for systemd path units')
    return {
        HELPER: source,
        CONFIG: (json.dumps(dict(version=1, uid=account.pw_uid, home=home), indent=2) + '\n').encode(),
        Path('/etc/systemd/system/project-largo-gdm.service'): f'''[Unit]
Description=Publish Project Largo palette for GDM
After=local-fs.target
Before=gdm.service
ConditionPathExists={home}/.local/state/project-largo/gdm/request.json
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 -I {HELPER} publish
UMask=0022
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=/usr/local/share/project-largo
ProtectHome=read-only
TimeoutStartSec=90
[Install]
WantedBy=graphical.target
'''.encode(),
        Path('/etc/systemd/system/project-largo-gdm.path'): f'''[Unit]
Description=Watch Project Largo GDM requests
[Path]
PathChanged={home}/.local/state/project-largo/gdm/request.json
Unit=project-largo-gdm.service
[Install]
WantedBy=multi-user.target
'''.encode(),
        Path('/etc/systemd/user/org.gnome.Shell@gdm.service.d/50-project-largo.conf'): (
            '[Service]\nEnvironment=G_RESOURCE_OVERLAYS=/org/gnome/shell/theme=/usr/local/share/project-largo/gdm/current\n').encode(),
    }


def reload_gdm_manager():
    try:
        account = pwd.getpwnam('gdm')
    except KeyError:
        return
    if Path(f'/run/user/{account.pw_uid}/bus').exists():
        command('/usr/bin/systemctl', '--user', '--machine=gdm@.host', 'daemon-reload')


def gdm_available():
    return Path('/usr/sbin/gdm').is_file() or Path('/usr/lib/systemd/system/gdm.service').is_file()


def setup(user):
    if not gdm_available():
        raise ValueError('GDM is not installed; no system integration is needed')
    account = pwd.getpwnam(user)
    if account.pw_uid == 0:
        raise ValueError('Select a desktop user')
    files = setup_files(account, Path(__file__).read_bytes())
    if not re.search(r'\b50\.', command('/usr/bin/gnome-shell', '--version')):
        raise ValueError('GDM setup currently targets GNOME Shell 50')
    backup = BACKUP / str(time.time_ns())
    backup.mkdir(parents=True, mode=0o700)
    records = []
    for path, data in files.items():
        if path.is_symlink():
            raise ValueError('Existing system configuration symlink requires review: ' + str(path))
        before = path.read_bytes() if path.exists() else None
        if before == data:
            continue
        index = str(len(records))
        if before is not None:
            (backup / index).write_bytes(before)
        records.append(dict(path=str(path), exists=before is not None, backup=index,
                            before=hashlib.sha256(before).hexdigest() if before is not None else None,
                            after=hashlib.sha256(data).hexdigest(), mode=path.stat().st_mode & 0o777 if path.exists() else 0o644))
    enabled = {unit: subprocess.run(['/usr/bin/systemctl', 'is-enabled', unit], capture_output=True, text=True).stdout.strip()
               for unit in ('project-largo-gdm.path', 'project-largo-gdm.service')}
    active = {unit: subprocess.run(['/usr/bin/systemctl', 'is-active', unit], capture_output=True, text=True).stdout.strip()
              for unit in enabled}
    current = TARGET / 'current'
    previous_link = os.readlink(current) if current.is_symlink() else None
    if current.exists() and not current.is_symlink():
        raise ValueError('Existing GDM current resource is not a managed symlink')
    manifest = dict(files=records, enabled=enabled, active=active, previous_link=previous_link, published_link=None)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    try:
        try:
            command('/usr/bin/systemctl', 'stop', 'project-largo-gdm.path', 'project-largo-gdm.service')
        except subprocess.CalledProcessError as error:
            if error.returncode != 5:  # Fresh installation: units do not exist yet.
                raise
        manifest['previous_link'] = os.readlink(current) if current.is_symlink() else None
        (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        for path, data in files.items():
            atomic(path, data)
        if Path('/usr/sbin/restorecon').is_file():
            command('/usr/sbin/restorecon', '-F', *files)
        TARGET.mkdir(parents=True, exist_ok=True)
        command('/usr/bin/systemctl', 'daemon-reload')
        reload_gdm_manager()
        queue = Path(account.pw_dir) / '.local/state/project-largo/gdm/request.json'
        if queue.exists():
            publish()
        manifest['published_link'] = os.readlink(current) if current.is_symlink() else None
        (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        command('/usr/bin/systemctl', 'enable', '--now', 'project-largo-gdm.path')
        command('/usr/bin/systemctl', 'enable', 'project-largo-gdm.service')
    except Exception:
        print('Administrator setup failed. Recovery operation:', backup.name)
        print('Recovery command: sudo /usr/bin/python3 -I ' + str(Path(__file__).resolve()) + ' restore ' + backup.name)
        raise
    print('GDM installed. Restore operation:', backup.name)
    print('No session or GDM restart performed; appearance loads on a future greeter startup.')


def restore(operation):
    if not operation.isdecimal():
        raise ValueError('Invalid restore operation')
    backup = BACKUP / operation
    manifest = json.loads((backup / 'manifest.json').read_text())
    for record in manifest['files']:
        path = Path(record['path'])
        current = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if path.is_symlink() or current not in (record['after'], record.get('before')):
            raise ValueError('System file changed; preserving ' + str(path))
    current = TARGET / 'current'
    # Ordinary later palette publications are Largo-owned generations too. Keep
    # the original resource generation available and restore its pointer.
    if current.exists() and not current.is_symlink():
        raise ValueError('GDM resource pointer changed; preserving it')
    if current.is_symlink() and not re.fullmatch(r'generation-[A-Za-z0-9_-]+', os.readlink(current)):
        raise ValueError('Unknown GDM resource pointer; preserving it')
    command('/usr/bin/systemctl', 'stop', 'project-largo-gdm.path', 'project-largo-gdm.service')
    for record in reversed(manifest['files']):
        path = Path(record['path'])
        if record['exists']:
            atomic(path, (backup / record['backup']).read_bytes(), record['mode'])
        else:
            path.unlink(missing_ok=True)
    current.unlink(missing_ok=True)
    if manifest.get('previous_link'):
        current.symlink_to(manifest['previous_link'])
    command('/usr/bin/systemctl', 'daemon-reload')
    reload_gdm_manager()
    for unit, state in manifest['enabled'].items():
        if state == 'enabled':
            command('/usr/bin/systemctl', 'enable', unit)
        else:
            command('/usr/bin/systemctl', 'disable', unit)
        if unit.endswith('.path') and manifest.get('active', {}).get(unit) == 'active':
            command('/usr/bin/systemctl', 'start', unit)
    print('System GDM configuration restored; no login manager restart performed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('setup', 'publish', 'restore'))
    parser.add_argument('argument', nargs='?')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Administrator authentication is required')
    if args.action == 'setup':
        setup(args.argument)
    elif args.action == 'restore':
        restore(args.argument)
    else:
        publish()


if __name__ == '__main__':
    main()
