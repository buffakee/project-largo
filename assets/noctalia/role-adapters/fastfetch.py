#!/usr/bin/python3
"""Merge theme colors into Fastfetch's JSONC without altering its modules."""
import json
from pathlib import Path
import re

HOME=Path.home()
START='// BEGIN NOCTALIA ROLE COLORS'
END='// END NOCTALIA ROLE COLORS'


def plain(text):
    text=re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/',
                lambda m:m[0] if m[0].startswith('"') else '',text)
    return json.loads(text)


def merge(text,colors):
    before=plain(text)
    # The original source has no logo/display objects; own a bounded inserted block.
    cleaned=re.sub(r'\s*'+re.escape(START)+r'[\s\S]*?'+re.escape(END)+r'\n?', '\n',text)
    base=plain(cleaned)
    for key in colors:
        if key in base:
            raise ValueError(f'Unmanaged {key} object found; merge it deliberately before applying')
    content=json.dumps(colors,indent=2)[2:-2].rstrip()+',\n'
    index=cleaned.index('{')+1
    result=cleaned[:index]+'\n  '+START+'\n'+content+'  '+END+'\n'+cleaned[index:].lstrip('\n')
    expected=dict(base); expected.update(colors)
    assert plain(result)==expected
    assert plain(result)['modules']==before['modules']
    return result


def main():
    path=HOME/'.config/fastfetch/config.jsonc'
    colors=json.loads((HOME/'.config/fastfetch/themes/noctalia.jsonc').read_text())
    text=path.read_text(); result=merge(text,colors)
    if result!=text:path.write_text(result)


if __name__=='__main__':main()
