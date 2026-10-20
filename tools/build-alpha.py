#!/usr/bin/python3
"""Build the versioned Alpha source kit from a clean, committed Git tree."""
import argparse
import gzip
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    if git('status', '--porcelain=v1', '-z'):
        raise SystemExit('Commit/review the candidate first; source kits require a clean Git tree.')
    version = (ROOT / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+-alpha\.\d+', version):
        raise SystemExit('VERSION must identify an Alpha, for example 0.1.0-alpha.1')
    commit = git('rev-parse', 'HEAD').decode().strip()
    prefix = f'project-largo-alpha-{version}'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / (prefix + '.tar.gz')
    fd = tempfile.NamedTemporaryFile(prefix='.alpha-', suffix='.tmp', dir=output, delete=False)
    temporary = Path(fd.name)
    try:
        with fd, gzip.GzipFile(fileobj=fd, mode='wb', filename='', mtime=0) as compressed:
            with subprocess.Popen(['git', '-c', 'tar.umask=0022', '-c', 'core.attributesFile=/dev/null',
                                   'archive', '--format=tar', '--prefix=' + prefix + '/', 'HEAD'],
                                  cwd=ROOT, stdout=subprocess.PIPE) as process:
                shutil.copyfileobj(process.stdout, compressed)
                if process.wait():
                    raise SystemExit('git archive failed')
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    h = hashlib.sha256()
    with archive.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    (output / 'SHA256SUMS').write_text(h.hexdigest() + '  ' + archive.name + '\n')
    print('Alpha:', version)
    print('Commit:', commit)
    print('Source kit:', archive)
    print('SHA256:', h.hexdigest())


if __name__ == '__main__':
    main()
