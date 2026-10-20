#!/usr/bin/python3
"""Noctalia compatibility entry: share LibreOffice safety and truthful results."""
import json
import os
from pathlib import Path
import sys

import integrations


def main():
    context = integrations.Context()
    state = context.home / '.local/state/oma-theme/gnome.json'
    palette = json.loads(state.read_text()).get('palette') if state.exists() else 'oma Gruvbox'
    if 'niri' in os.environ.get('XDG_CURRENT_DESKTOP', '').lower():
        # Read selection only; integration configuration remains Largo-owned.
        import tomllib
        native = context.home / '.local/state/noctalia/settings.toml'
        selection = tomllib.loads(native.read_text()).get('theme', {}) if native.exists() else {}
        palette = selection.get('custom_palette', palette)
    with integrations.locked(context):
        report = integrations.execute(context, 'apply', app='libreoffice', palette=palette)
    print(json.dumps(report, indent=2))
    return 1 if report['failed'] else 2 if any(r['state'] not in ('Ready', 'Not installed', 'Restart required') for r in report['results']) else 0


if __name__ == '__main__':
    sys.exit(main())
