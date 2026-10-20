"""Rescannable application enrollment and conflict-aware private recovery."""
import contextlib
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tempfile
import time

STATES = ('Ready', 'Not installed', 'Setup needed', 'Open app once', 'Restart required',
          'Close app and retry', 'Administrator setup required', 'Failed')
VANILLA = ('Vanilla Gnome', 'Vanilla Gnome Dark')


class Blocked(ValueError):
    def __init__(self, state, detail):
        self.state, self.detail = state, detail
        super().__init__(detail)


def read(path):
    if Path(path).is_symlink():
        raise ValueError('Configuration symlink requires review: ' + str(path))
    try:
        return Path(path).read_bytes()
    except FileNotFoundError:
        return None


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def atomic(path, data, mode=0o600):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refusing to replace a symlink: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    if data is None:
        path.unlink(missing_ok=True)
        return
    fd, temporary = tempfile.mkstemp(prefix='.largo-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def json_bytes(data):
    return (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode()


def merge_restore(before, after, current):
    """Undo only owned JSON changes; reject conflicts in owned scalar fields."""
    if before == after:
        return current
    if current == after:
        return copy.deepcopy(before)
    if all(isinstance(v, dict) for v in (before, after, current)):
        result = copy.deepcopy(current)
        for key in before.keys() | after.keys():
            if before.get(key) == after.get(key) and (key in before) == (key in after):
                continue
            if key not in before:
                if key in current and current[key] != after[key]:
                    raise ValueError('An owned setting changed: ' + key)
                result.pop(key, None)
            elif key not in after:
                if key in current and current[key] != before[key]:
                    raise ValueError('An owned setting changed: ' + key)
                result[key] = copy.deepcopy(before[key])
            else:
                result[key] = merge_restore(before[key], after[key], current.get(key))
        return result
    if all(isinstance(v, list) for v in (before, after, current)):
        result = [v for v in current if v not in after or v in before]
        return result + [v for v in before if v not in after and v not in result]
    if current == before:
        return current
    raise ValueError('An owned setting changed; restoration needs review')


class Context:
    def __init__(self, home=None, runner=None, processes=None):
        self.home = Path.home() if home is None else Path(home)
        self.root = Path(__file__).resolve().parent
        self.state = self.home / '.local/state/project-largo/integrations'
        self.sources = self.home / '.config/noctalia'
        self.runner = runner or self._run
        self.processes = processes or self._processes
        self._flatpak_apps = None

    @staticmethod
    def _run(args):
        return subprocess.run(list(map(str, args)), check=True, capture_output=True,
                              text=True, timeout=120).stdout

    @staticmethod
    def _processes(names):
        # Read only process identities, never document arguments or environment.
        found = []
        for path in Path('/proc').iterdir():
            if not path.name.isdecimal():
                continue
            try:
                if path.stat().st_uid == os.getuid() and (path / 'comm').read_text().strip() in names:
                    found.append(path.name + ':' + (path / 'stat').read_text().split(') ', 1)[1].split()[19])
            except (FileNotFoundError, ProcessLookupError):
                continue
            except PermissionError as error:
                raise ValueError('Unable to establish application process safety') from error
        return sorted(found)

    def flatpak(self, app):
        if not shutil.which('flatpak'):
            return False
        if self._flatpak_apps is None:
            self._flatpak_apps = set(self.runner(['flatpak', 'list', '--app', '--columns=application']).splitlines())
        return app in self._flatpak_apps

    def native(self, name, candidates=()):
        return shutil.which(name) or next((str(p) for p in candidates if os.access(p, os.X_OK)), None)

    def config(self):
        path = self.home / '.config/project-largo/integrations.json'
        return json.loads(path.read_text()) if path.exists() else {}

    def started_after(self, names, timestamp):
        processes = self.processes(names)
        if not processes:
            return False
        boot = time.time() - float(Path('/proc/uptime').read_text().split()[0])
        ticks = os.sysconf('SC_CLK_TCK')
        return all(boot + int(identity.split(':')[1]) / ticks > timestamp for identity in processes)

    def registry(self):
        path = self.state / 'enrolled.json'
        return json.loads(path.read_text()) if path.exists() else {}

    def current_artifacts(self):
        path = self.state / 'artifacts.json'
        return {Path(k): bytes.fromhex(v) for k, v in json.loads(path.read_text()).items()} if path.exists() else {}


class Transaction:
    def __init__(self, context, key, guard=lambda: None):
        self.context, self.guard = context, guard
        self.directory = context.state / 'operations' / str(time.time_ns())
        self.key, self.records, self.trees = key, [], []
        self.previous_enrollment = context.registry().get(key)

    def save(self, status='pending'):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        atomic(self.directory / 'manifest.json', json_bytes(
            {'key': self.key, 'status': status, 'files': self.records, 'trees': self.trees,
             'app': getattr(self, 'app', None), 'target': getattr(self, 'target', None),
             'previous_enrollment': self.previous_enrollment}))

    def write(self, path, content, kind='file', mode=None):
        path = Path(path)
        if path.is_symlink():
            raise ValueError('Review symlink before enrollment: ' + str(path))
        before = read(path)
        if before == content:
            return False
        self.guard()
        index = str(len(self.records))
        record = dict(path=str(path), before=digest(before), after=digest(content),
                      backup=index, kind=kind, mode=path.stat().st_mode & 0o777 if path.exists() else (mode or 0o600))
        self.save()
        if before is not None:
            atomic(self.directory / (index + '.before'), before)
        if content is not None:
            atomic(self.directory / (index + '.after'), content)
        self.records.append(record)
        self.save()
        self.guard()
        if read(path) != before:
            raise ValueError('Configuration changed during enrollment: ' + str(path))
        atomic(path, content, record['mode'])
        return True

    def tree(self, path):
        """Back up extension-manager storage before invoking unopkg."""
        path = Path(path)
        self.guard()
        if path.is_symlink() or (path.exists() and any(p.is_symlink() for p in path.rglob('*'))):
            raise ValueError('Review extension storage symlinks before enrollment')
        name = 'tree-' + str(len(self.trees))
        self.save()
        exists = path.exists()
        if exists:
            shutil.copytree(path, self.directory / name)
        self.trees.append(dict(path=str(path), backup=name, exists=exists, after=None))
        self.save()

    def external(self, path):
        """Journal a config file an extension manager may modify itself."""
        path = Path(path)
        self.guard()
        if path.is_symlink():
            raise ValueError('Review configuration symlink before extension install')
        before = read(path)
        index = str(len(self.records))
        self.save()
        if before is not None:
            atomic(self.directory / (index + '.before'), before)
            atomic(self.directory / (index + '.after'), before)
        self.records.append(dict(path=str(path), before=digest(before), after=digest(before),
            backup=index, kind='office-scheme', external=True,
            mode=path.stat().st_mode & 0o777 if path.exists() else 0o600))
        self.save()

    def finish(self, status='complete'):
        for record in self.records:
            if record.get('external'):
                value = read(record['path'])
                record['after'] = digest(value)
                if value is not None:
                    atomic(self.directory / (record['backup'] + '.after'), value)
        for tree in self.trees:
            tree['after'] = tree_digest(Path(tree['path']))
        if self.records or self.trees:
            self.save(status)

    def rollback(self):
        self.guard()
        for record in reversed(self.records):
            path = Path(record['path'])
            current = read(path)
            if digest(current) == record['before']:
                continue
            if digest(current) != record['after']:
                raise ValueError('Concurrent edit prevents automatic rollback: ' + str(path))
            atomic(path, read(self.directory / (record['backup'] + '.before')), record['mode'])
        for tree in reversed(self.trees):
            path = Path(tree['path'])
            if path.exists():
                shutil.rmtree(path)
            if tree['exists']:
                shutil.copytree(self.directory / tree['backup'], path)
        if self.directory.exists():
            self.save('rolled back')


def tree_digest(path):
    if not path.exists():
        return None
    h = hashlib.sha256()
    for file in sorted(path.rglob('*')):
        if file.is_symlink():
            raise ValueError('Unexpected symlink in extension storage')
        h.update(str(file.relative_to(path)).encode())
        h.update(str(file.stat().st_mode & 0o7777).encode())
        h.update(b'd' if file.is_dir() else b'f')
        if file.is_file():
            h.update(file.read_bytes())
    return h.hexdigest()


@contextlib.contextmanager
def locked(context):
    context.state.mkdir(parents=True, exist_ok=True, mode=0o700)
    context.state.chmod(0o700)
    with (context.state / 'setup.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def result(app, target, state, detail, **extra):
    assert state in STATES
    return dict(app=app, target=target, state=state, detail=detail, **extra)


def execute(context, action='status', app=None, dry_run=False, artifacts=None, palette=None, enrolled_only=False, skip_apps=()):
    """Shared UI/CLI/apply entry. Status never writes or invokes unopkg."""
    from integration_apps import adapters
    context._flatpak_apps = None
    registry = context.registry()
    if artifacts is None:
        artifacts = context.current_artifacts()
        # Normal palette application publishes canonical files before calling us.
        if action == 'apply':
            artifacts = None
    results = []
    selected = adapters(context, app)
    for adapter in selected:
        if adapter.name in skip_apps:
            continue
        try:
            targets = adapter.discover()
        except Exception as error:
            results.append(result(adapter.name, 'discovery', 'Failed', str(error)))
            continue
        for target in targets:
            tx = Transaction(context, target['key'], lambda: adapter.guard(target))
            try:
                if enrolled_only and target['key'] not in registry:
                    continue
                tx.app, tx.target = adapter.name, target
                outcome = adapter.inspect(target, artifacts, palette)
                previous = registry.get(target['key'], {})
                restarted = (not previous.get('needs_profile') and previous.get('palette') == palette and previous.get('signature') is not None
                    and context.started_after(adapter.names, previous.get('changed_at', 0))
                    and adapter.restart_signature(target) == previous['signature']
                    and adapter.activation_ready(target))
                if action == 'status' and outcome['state'] == 'Close app and retry' and restarted:
                    outcome.update(state='Ready', detail='Owned hooks and current assets verified; a fresh application process was observed after publication.')
                if action == 'apply' and outcome['state'] == 'Close app and retry':
                    # Only already-imported generated CSS is safe to replace while
                    # a client runs. Never touch settings, session or extension data.
                    safe = adapter.running_outputs(target, palette)
                    tx.guard = lambda: None
                    for path, data in safe:
                        tx.write(path, data)
                    tx.finish()
                    outcome['detail'] = 'Current palette assets staged. Close and reopen the app; pending profile/extension work is retried by ordinary palette application.'
                    complete = adapter.running_complete(target, palette)
                    if safe and complete:
                        outcome['state'] = 'Ready' if restarted and not tx.records else 'Restart required'
                    if safe:
                        registry[target['key']] = dict(previous, palette=palette,
                            signature=adapter.restart_signature(target), needs_profile=not complete,
                            changed_at=time.time() if tx.records else previous.get('changed_at', 0),
                            pending_restart=bool(tx.records) or previous.get('pending_restart', False),
                            operation=tx.directory.name if tx.records else previous.get('operation'))
                        atomic(context.state / 'enrolled.json', json_bytes(registry))
                        outcome['operation'] = registry[target['key']].get('operation')
                    results.append(outcome)
                    continue
                if (action != 'status' and not dry_run and outcome['state'] not in (
                        'Not installed', 'Open app once', 'Administrator setup required')
                        and (outcome['state'] != 'Failed' or outcome.get('retryable'))):
                    if action == 'status':
                        raise AssertionError('Status cannot enroll')
                    with adapter.profile_lock(target):
                        adapter.guard(target)
                        adapter.enroll(target, tx, artifacts, palette)
                    tx.finish()
                    previous = registry.get(target['key'], {})
                    changed = bool(tx.records or tx.trees)
                    registry[target['key']] = dict(previous, app=adapter.name, target=target, palette=palette,
                        changed_at=time.time() if changed else previous.get('changed_at', 0),
                        pending_restart=adapter.restart_required and (changed or previous.get('pending_restart', False)),
                        needs_profile=False,
                        signature=adapter.restart_signature(target),
                        operation=tx.directory.name if changed else previous.get('operation'))
                    atomic(context.state / 'enrolled.json', json_bytes(registry))
                    outcome = adapter.inspect(target, artifacts, palette)
                if outcome['state'] == 'Ready':
                    enrolled = registry.get(target['key'], {})
                    if enrolled.get('pending_restart') and not restarted:
                        outcome['state'] = 'Restart required'
                        outcome['detail'] += ' Configuration verified; reopen the application to load it.'
                if registry.get(target['key'], {}).get('operation'):
                    outcome['operation'] = registry[target['key']]['operation']
                if tx.directory.exists():
                    outcome['operation'] = tx.directory.name
                results.append(outcome)
            except Blocked as error:
                if tx.records or tx.trees:
                    # A process may have started mid-operation. Never restore into it.
                    tx.finish('blocked')
                results.append(result(adapter.name, target['key'], error.state, error.detail,
                                      operation=tx.directory.name if tx.directory.exists() else None))
            except Exception as error:
                detail = str(error)
                if getattr(error, 'stderr', None):
                    detail += ': ' + str(error.stderr)[-2000:]
                if tx.records or tx.trees:
                    try:
                        tx.guard()
                        tx.finish('failed')
                        tx.rollback()
                    except Exception as rollback_error:
                        detail += '; recovery retained: ' + str(rollback_error)
                    detail += '; backup operation: ' + tx.directory.name
                results.append(result(adapter.name, target['key'], 'Failed', detail,
                                      operation=tx.directory.name if tx.directory.exists() else None))
    return dict(palette=palette, action=action, dry_run=dry_run, results=results,
                failed=any(r['state'] == 'Failed' for r in results))


def restore(context, operation):
    from integration_apps import adapters, restore_session, restore_office_scheme
    if not operation.isdecimal():
        raise ValueError('Invalid operation identifier')
    directory = context.state / 'operations' / operation
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['status'] == 'restored':
        return
    entry = context.registry().get(manifest['key']) or dict(app=manifest.get('app'), target=manifest.get('target'))
    if not entry.get('target'):
        raise ValueError('Enrollment record missing; review retained backup before restoring')
    adapter = next(a for a in adapters(context) if a.name == entry['app'])
    target = entry['target']
    with adapter.profile_lock(target):
        adapter.guard(target)
        updates = {}
        original_values = {}
        virtual = {}
        for record in reversed(manifest['files']):
            path = Path(record['path'])
            current = virtual[path] if path in virtual else read(path)
            original_values.setdefault(path, current)
            before = read(directory / (record['backup'] + '.before'))
            after = read(directory / (record['backup'] + '.after'))
            if current == before:
                continue
            if current == after:
                value = before
            elif record['kind'] == 'json' and current is not None and after is not None:
                value = json_bytes(merge_restore(json.loads(before or b'{}'), json.loads(after), json.loads(current)))
            elif record['kind'] == 'session':
                value = restore_session(before, after, current)
            elif record['kind'] == 'office-scheme':
                value = restore_office_scheme(before, after, current)
            elif record['kind'] == 'text' and all(v is not None for v in (before, after, current)):
                with tempfile.TemporaryDirectory(prefix='largo-restore-') as temporary:
                    paths = [Path(temporary) / name for name in ('current', 'after', 'before')]
                    for file, content in zip(paths, (current, after, before)):
                        file.write_bytes(content)
                    merged = subprocess.run(['/usr/bin/git', 'merge-file', '-p', *map(str, paths)], capture_output=True)
                    if merged.returncode:
                        raise ValueError('Later text edit conflicts with restoration: ' + str(path))
                    value = merged.stdout
            else:
                raise ValueError('Later edit prevents restoration: ' + str(path))
            virtual[path] = value
            updates[path] = (record, original_values[path], value)
        for tree in manifest['trees']:
            if tree_digest(Path(tree['path'])) != tree['after']:
                raise ValueError('Extension storage changed; preserving ' + tree['path'])
        for record, current, value in updates.values():
            adapter.guard(target)
            if read(record['path']) != current:
                raise ValueError('Concurrent edit during restoration')
            atomic(record['path'], value, record['mode'])
        for tree in reversed(manifest['trees']):
            path = Path(tree['path'])
            if path.exists():
                shutil.rmtree(path)
            if tree['exists']:
                shutil.copytree(directory / tree['backup'], path)
        manifest['status'] = 'restored'
        atomic(directory / 'manifest.json', json_bytes(manifest))
        registry = context.registry()
        if manifest.get('previous_enrollment'):
            registry[manifest['key']] = manifest['previous_enrollment']
        else:
            registry.pop(manifest['key'], None)
        atomic(context.state / 'enrolled.json', json_bytes(registry))


def main(argv, engine):
    import argparse
    parser = argparse.ArgumentParser(prog='project-largo integrations')
    commands = parser.add_subparsers(dest='action', required=True)
    for name in ('status', 'setup', 'repair'):
        command = commands.add_parser(name)
        command.add_argument('--app', choices=('libreoffice', 'zen', 'obsidian', 'zotero', 'gdm'))
        command.add_argument('--json', action='store_true')
        if name != 'status':
            command.add_argument('--dry-run', action='store_true')
    command = commands.add_parser('restore')
    command.add_argument('operation')
    command = commands.add_parser('admin-setup')
    command.add_argument('app', choices=('gdm',))
    command = commands.add_parser('admin-restore')
    command.add_argument('operation')
    args = parser.parse_args(argv)
    context = Context(engine.HOME)
    if args.action == 'status' or getattr(args, 'dry_run', False):
        return dispatch(args, context, engine)
    engine.STATE.mkdir(parents=True, exist_ok=True)
    with (engine.STATE / 'apply.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return dispatch(args, context, engine)


def dispatch(args, context, engine):
    palette = engine.selection()['palette']
    if args.action in ('admin-setup', 'admin-restore'):
        if args.action == 'admin-setup':
            from integration_apps import GDM
            if GDM(context).discover()[0].get('absent'):
                print('Not installed: GDM — optional integration skipped.')
                return 0
            # Queue user-owned DATA before authentication. The publisher never
            # imports this user-side code when running as root.
            from gdm_client import request
            supplied = {}
            if palette not in VANILLA:
                with tempfile.TemporaryDirectory(prefix='largo-gdm-request-') as temporary:
                    _, tokens = engine.stage_integrations(palette, Path(temporary))
                    supplied['tokens'] = tokens
            data, image = request(context, palette, supplied)
            queue = context.home / '.local/state/project-largo/gdm'
            key = 'gdm:system:' + str(context.home)
            tx = Transaction(context, key)
            tx.app, tx.target = 'gdm', dict(key=key, backend='system', profile=str(context.home))
            with locked(context):
                if image:
                    tx.write(queue / (data['wallpaper'] + '.png'), image)
                tx.write(queue / 'request.json', json_bytes(data), 'json')
                tx.finish()
            source = context.root / 'gdm_admin.py'
            expected = digest(source.read_bytes())
            staged = '/usr/local/libexec/project-largo-gdm-admin-' + expected[:16]
            try:
                context.runner(['/usr/bin/pkexec', '/usr/bin/install', '-D', '-o', 'root', '-g', 'root', '-m', '0644', source, staged])
                installed = Path(staged)
                if (installed.is_symlink() or installed.stat().st_uid != 0 or installed.stat().st_mode & 0o022
                        or digest(installed.read_bytes()) != expected):
                    raise ValueError('Authenticated GDM installer copy did not verify')
                output = context.runner(['/usr/bin/pkexec', '/usr/bin/python3', '-I', staged, 'setup', pwd.getpwuid(os.getuid()).pw_name])
                print(output)
            except Exception as error:
                import sys
                if getattr(error, 'stdout', None):
                    print(error.stdout, file=sys.stderr)
                try:
                    tx.rollback()
                except Exception as recovery:
                    print('User queue backup retained at ' + str(tx.directory) + ': ' + str(recovery), file=sys.stderr)
                raise
            # Explicitly enroll GDM only after an authenticated, successful setup.
            with locked(context):
                registry = context.registry()
                match = re.search(r'Restore operation: (\d+)', output)
                registry[key] = dict(app='gdm', palette=palette, operation=tx.directory.name, target=tx.target,
                    admin_operation=match[1] if match else None, previous_enrollment=tx.previous_enrollment)
                atomic(context.state / 'enrolled.json', json_bytes(registry))
            print('User queue backup operation:', tx.directory.name)
        else:
            source = context.root / 'gdm_admin.py'
            staged = Path('/usr/local/libexec/project-largo-gdm-admin-' + digest(source.read_bytes())[:16])
            helper = staged if staged.is_file() else Path('/usr/local/libexec/project-largo-gdm')
            if helper.is_symlink() or not helper.is_file() or helper.stat().st_uid != 0 or helper.stat().st_mode & 0o022:
                raise ValueError('No trusted installed GDM recovery helper found')
            print(context.runner(['/usr/bin/pkexec', '/usr/bin/python3', '-I', helper, 'restore', args.operation]))
            with locked(context):
                key = 'gdm:system:' + str(context.home)
                registry = context.registry()
                entry = registry.get(key, {})
                if entry.get('admin_operation') == args.operation:
                    if entry.get('previous_enrollment'):
                        registry[key] = entry['previous_enrollment']
                    else:
                        registry.pop(key, None)
                    atomic(context.state / 'enrolled.json', json_bytes(registry))
        return 0
    if args.action == 'restore':
        with locked(context):
            restore(context, args.operation)
        print('Restored integration operation ' + args.operation)
        return 0
    dry_run = getattr(args, 'dry_run', False)
    if args.action == 'status' or dry_run:
        report = execute(context, args.action, args.app, dry_run, palette=palette)
    else:
        with locked(context), tempfile.TemporaryDirectory(prefix='largo-setup-') as temporary:
            if palette in VANILLA:
                artifacts = {}
            else:
                artifacts, tokens = engine.stage_integrations(palette, Path(temporary))
                # Snapshot only renderer artifacts, not user/profile configurations.
                keep = ('zen-userChrome.css', 'zen-userContent.css', 'obsidian.css', 'zotero.css',
                        'zotero-pdf-theme.json', 'tokens.json', 'Theme_Colors.xcu', 'gtk.css', 'gtk-dark.css')
                artifacts = {p: value for p, value in artifacts.items() if p.name in keep}
                atomic(context.state / 'artifacts.json', json_bytes({str(p): v.hex() for p, v in artifacts.items()}))
                artifacts['tokens'] = tokens
            report = execute(context, args.action, args.app, artifacts=artifacts, palette=palette)
            atomic(context.state / 'last-results.json', json_bytes(report))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print('Current preset: ' + palette)
        for row in report['results']:
            print(f"{row['state']}: {row['target']} — {row['detail']}")
            if row.get('operation'):
                print('  Restore: project-largo integrations restore ' + row['operation'])
    if report['failed']:
        return 1
    return 2 if any(r['state'] not in ('Ready', 'Not installed', 'Restart required') for r in report['results']) else 0
