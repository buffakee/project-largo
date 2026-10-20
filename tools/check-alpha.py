#!/usr/bin/python3
"""Extract and test a source kit in disposable directories; no live install."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    archive = args.archive.resolve()
    with tempfile.TemporaryDirectory(prefix='largo-alpha-kit-') as temporary:
        directory = Path(temporary)
        with tarfile.open(archive, 'r:gz') as source:
            members = source.getmembers()
            roots, names = set(), set()
            for member in members:
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or not path.parts or member.name in names:
                    raise ValueError('Invalid or duplicate source-kit member: ' + member.name)
                if not (member.isdir() or member.isfile()):
                    raise ValueError('Source kit contains an unexpected link/special file: ' + member.name)
                if any(p in ('.git', '__pycache__', '.env') for p in path.parts) or path.suffix in ('.pyc', '.pyo'):
                    raise ValueError('Git/cache/private environment data is present in source kit')
                roots.add(path.parts[0])
                names.add(member.name)
            if len(roots) != 1:
                raise ValueError('Source kit must have exactly one top-level directory')
            prefix = roots.pop()
            if not re.fullmatch(r'project-largo-alpha-\d+\.\d+\.\d+-alpha\.\d+', prefix):
                raise ValueError('Unexpected source-kit version directory')
            for member in members:
                target = directory / member.name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(member) as incoming, target.open('wb') as outgoing:
                        shutil.copyfileobj(incoming, outgoing)
                    target.chmod(member.mode & 0o755)
        root = directory / prefix
        required = ('VERSION', 'install.py', 'README.md', 'GETTING_STARTED.md', 'RECOVERY.md',
                    'INTEGRATIONS.md', 'ALPHA_NOTES.md', 'LICENSE', 'THIRD_PARTY.md',
                    'UPSTREAM_SNAPSHOT.json', 'src/engine.py', 'src/renderer.py',
                    'src/integrations.py', 'src/integration_apps.py', 'tests/test_integrations.py',
                    'assets/appearance/manifest.json', 'assets/appearance/icons.tar.xz',
                    'assets/appearance/bibata-v2.0.6-source.tar.gz')
        if any(not (root / name).is_file() for name in required):
            raise ValueError('Source kit is missing a required source, guide or appearance asset')
        version = (root / 'VERSION').read_text().strip()
        if prefix != 'project-largo-alpha-' + version:
            raise ValueError('VERSION and archive directory disagree')
        snapshot = json.loads((root / 'UPSTREAM_SNAPSHOT.json').read_text())
        unchanged_roots = {'src', 'assets', 'bin', 'desktop', 'extras', 'tests', 'tools', 'LICENSES'}
        unchanged_files = {'install.py', 'LICENSE', 'THIRD_PARTY.md', 'SOURCE_ORIGINS.json', '.gitignore'}
        verified = 0
        for relative, expected in snapshot['source_files_sha256'].items():
            if PurePosixPath(relative).parts[0] in unchanged_roots or relative in unchanged_files:
                path = root / relative
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise ValueError('Current runtime/source snapshot was changed: ' + relative)
                verified += 1
        home = directory / 'test-home'
        home.mkdir()
        env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
                   XDG_DATA_HOME=str(home / '.local/share'), XDG_STATE_HOME=str(home / '.local/state'),
                   XDG_CACHE_HOME=str(home / '.cache'), GSETTINGS_BACKEND='memory',
                   STARSHIP_CONFIG=str(home / '.config/starship.toml'))
        subprocess.run([sys.executable, str(root / 'install.py'), '--dry-run'], env=env,
                       cwd=root, check=True, timeout=120)
        if list(home.iterdir()):
            raise ValueError('Installer dry-run changed the disposable home')
        subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                       env=env, cwd=root, check=True, timeout=180)
        print(f'PASS: Alpha {version}, {verified} preserved source/assets, safe extraction, installer dry-run and extracted unit suite')


if __name__ == '__main__':
    main()
