#!/usr/bin/python3
"""Export explicitly supplied appearance assets; never copy desktop runtime state."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tomllib
import urllib.request
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--memory', type=Path, required=True)
    parser.add_argument('--icons', type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / 'assets/appearance'
    output.mkdir(parents=True, exist_ok=True)
    wallpapers = output / 'wallpapers'
    wallpapers.mkdir(exist_ok=True)
    definitions = {p.stem: json.loads(p.read_text()) for p in (ROOT / 'assets/noctalia/palettes').glob('oma *.json')}
    favorites = tomllib.loads(args.settings.read_text())['wallpaper']['favorite']
    memory = json.loads(args.memory.read_text())['themes']
    manifest = {'version': 1, 'themes': {}, 'files': {}, 'icon_archive': 'icons.tar.xz',
                'cursor': 'Bibata-Modern-Ice', 'icons': 'yet-another-monochrome-icon-set'}
    for name in sorted(definitions):
        paths = [Path(item['path']) for item in favorites if item.get('custom_palette') == name]
        saved = memory.get(name, {}).get('picture-uri-dark', '')
        if saved.startswith('file://'):
            path = Path(unquote(urlparse(saved).path))
            if path.is_file():
                paths = [path] + paths
        paths = list(dict.fromkeys(paths))
        names = []
        for path in paths:
            if not path.is_file():
                raise ValueError('Missing associated wallpaper: ' + path.name)
            target = wallpapers / path.name
            data = path.read_bytes()
            if target.exists() and target.read_bytes() != data:
                raise ValueError('Wallpaper filename collision: ' + path.name)
            target.write_bytes(data)
            relative = 'wallpapers/' + path.name
            manifest['files'][relative] = {'sha256': sha(data), 'kind': 'wallpaper',
                'source': 'Existing user-selected theme association; original artist/license not recorded locally.',
                'palette_source': definitions[name].get('_source', 'User-provided original Largo palette')}
            names.append(relative)
        manifest['themes'][name] = {'default': names[0] if names else None, 'wallpapers': names}
    # Canonical files and aliases are stored as regular files for portable installation.
    # Retain exact bytes and refuse links leaving the selected source theme.
    archive = output / manifest['icon_archive']
    with tarfile.open(archive, 'w:xz', preset=6) as tar:
        for theme in (manifest['cursor'], manifest['icons']):
            source = args.icons / theme
            for path in sorted(source.rglob('*')):
                if '.git' in path.parts or path.name == 'icon-theme.cache' or path.is_dir():
                    continue
                if not path.resolve().is_relative_to(source.resolve()):
                    raise ValueError('External theme alias: ' + str(path))
                data = path.read_bytes()
                member = tarfile.TarInfo(str(Path(theme) / path.relative_to(source)))
                member.size, member.mode, member.mtime = len(data), 0o644, 0
                tar.addfile(member, io.BytesIO(data))
        # The locally installed Bibata tree omits its upstream license.
        license_data = urllib.request.urlopen('https://raw.githubusercontent.com/ful1e5/Bibata_Cursor/v2.0.6/LICENSE', timeout=60).read()
        member = tarfile.TarInfo(manifest['cursor'] + '/LICENSE')
        member.size, member.mode, member.mtime = len(license_data), 0o644, 0
        tar.addfile(member, io.BytesIO(license_data))
    manifest['files'][manifest['icon_archive']] = {'sha256': sha(archive.read_bytes()), 'kind': 'icons',
        'source': 'Bibata v2.0.6 installed XCursors and YAMIS installed upstream SVG source snapshot; see THIRD_PARTY.md'}
    # Include the matching cursor source alongside the distributed XCursors.
    source_name = 'bibata-v2.0.6-source.tar.gz'
    with urllib.request.urlopen('https://codeload.github.com/ful1e5/Bibata_Cursor/tar.gz/refs/tags/v2.0.6', timeout=120) as response:
        (output / source_name).write_bytes(response.read())
    manifest['files'][source_name] = {'sha256': sha((output / source_name).read_bytes()), 'kind': 'source',
        'source': 'https://github.com/ful1e5/Bibata_Cursor/tree/v2.0.6'}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(f'Exported {len(manifest["files"]) - 2} wallpapers; defaults for {sum(bool(x["default"]) for x in manifest["themes"].values())} themes.')


if __name__ == '__main__':
    main()
