#!/usr/bin/python3
"""Theme registered Obsidian vaults; never traverse or access their notes."""
import json
import os
from pathlib import Path
import sys
import tempfile


def vaults():
    home=Path.home(); found=set()
    for registry in (home/'.config/obsidian/obsidian.json',home/'.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json'):
        if registry.is_file():
            for value in json.loads(registry.read_text()).get('vaults',{}).values():
                directory=Path(value['path'])/'.obsidian'
                if directory.is_dir():found.add(directory)
    return sorted(found)


def main():
    action=sys.argv[1]
    if action not in ('output','apply'):raise SystemExit('Expected output or apply')
    for directory in vaults():
        if action=='output':
            (directory/'snippets').mkdir(exist_ok=True)
            print(directory/'snippets/noctalia.css')
        else:
            path=directory/'appearance.json'
            original=path.read_text() if path.exists() else '{}'
            data=json.loads(original); snippets=data.setdefault('enabledCssSnippets',[])
            if 'noctalia' in snippets:continue
            snippets.append('noctalia')
            fd,temp=tempfile.mkstemp(prefix='.appearance-',dir=directory)
            try:
                with os.fdopen(fd,'w') as stream:stream.write(json.dumps(data,indent=2)+'\n')
                os.replace(temp,path)
            finally:
                if os.path.exists(temp):os.unlink(temp)


if __name__=='__main__':main()
