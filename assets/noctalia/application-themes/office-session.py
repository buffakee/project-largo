#!/usr/bin/python3
"""Choose native/default or existing Noctalia appearance before LibreOffice starts."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

NAMESPACE = 'http://openoffice.org/2001/registry'
CONFIG_PATH = '/org.openoffice.Office.UI/ColorScheme'


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('kde', 'default', 'noctalia'):
        raise SystemExit('Expected default or noctalia')
    # LibreOffice persists this file on exit. Never edit a live profile.
    running = subprocess.run(['/usr/bin/pgrep', '-u', str(os.getuid()), '-x', 'soffice.bin'],
                             stdout=subprocess.DEVNULL, check=False)
    if running.returncode == 0:
        print('LibreOffice is running; color scheme selection deferred until reopen')
        return
    if running.returncode != 1:
        raise SystemExit('Could not check whether LibreOffice is running')
    path = Path.home()/'.config/libreoffice/4/user/registrymodifications.xcu'
    if not path.is_file():
        # A first-ever profile should use LibreOffice's own defaults.
        return
    scheme = 'Noctalia' if sys.argv[1] == 'noctalia' else 'COLOR_SCHEME_LIBREOFFICE_AUTOMATIC'
    original = path.read_text()
    root = ET.fromstring(original)
    matches = [item for item in root if item.get(f'{{{NAMESPACE}}}path') == CONFIG_PATH]
    properties = [prop for item in matches for prop in item
                  if prop.get(f'{{{NAMESPACE}}}name') == 'CurrentColorScheme']
    if len(properties) == 1 and properties[0].findtext('value') == scheme:
        return
    assert len(properties) <= 1, 'Ambiguous CurrentColorScheme overrides'
    # Keep the original file byte-for-byte outside the one selected-scheme value.
    # In particular, do not rewrite unrelated settings or recent-file records.
    item_pattern = r'<item\b[^>]*\boor:path=["\']' + re.escape(CONFIG_PATH) + r'["\'][^>]*>.*?</item>'
    prop_pattern = r'(<prop\b[^>]*\boor:name=["\']CurrentColorScheme["\'][^>]*>\s*<value>)[^<]*(</value>)'
    if properties:
        count = 0
        def replace_item(match):
            nonlocal count
            item, changed = re.subn(prop_pattern, lambda m: m[1]+scheme+m[2], match[0], flags=re.S)
            count += changed
            return item
        updated = re.sub(item_pattern, replace_item, original, flags=re.S)
        assert count == 1, 'Unrecognized CurrentColorScheme serialization'
    else:
        entry = (f'<item oor:path="{CONFIG_PATH}"><prop oor:name="CurrentColorScheme" '
                 f'oor:op="fuse"><value>{scheme}</value></prop></item>\n')
        assert original.count('</oor:items>') == 1
        updated = original.replace('</oor:items>', entry+'</oor:items>')
    ET.fromstring(updated)
    fd, temporary = tempfile.mkstemp(prefix='.office-session-', dir=path.parent)
    try:
        os.fchmod(fd, path.stat().st_mode & 0o777)
        with os.fdopen(fd, 'w') as stream:
            stream.write(updated)
        # Detect a simultaneous profile change rather than overwriting it.
        assert path.read_text() == original, 'LibreOffice profile changed during update'
        assert subprocess.run(['/usr/bin/pgrep','-u',str(os.getuid()),'-x','soffice.bin'],
                              stdout=subprocess.DEVNULL).returncode == 1, 'LibreOffice started during update'
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    main()
