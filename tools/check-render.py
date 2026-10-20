#!/usr/bin/python3
"""Render all installed snapshot palettes into a disposable home, never apply."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def worker():
    sys.path.insert(0, str(Path.home() / '.config/oma-theme'))
    import engine
    results = []
    for name in engine.palettes():
        directory = Path.home() / 'validation' / name
        outputs, tokens, contrasts = engine.stage_palette(name, directory)
        engine.validate_css(directory)
        assert f"#panel {{ background-color: {tokens['shadow']}; }}" in (directory / 'gnome-shell.css').read_text()
        ratio = engine.contrast(tokens['on_surface'], tokens['shadow'])
        assert ratio >= 4.5
        results.append({'palette': name, 'outputs': len(outputs), 'top_bar_contrast': ratio,
                        'minimum_checked_contrast': min(contrasts.values())})
        print(name, 'PASS', flush=True)
    print(json.dumps({'rendered_palettes': len(results),
                      'minimum_top_bar_contrast': min(r['top_bar_contrast'] for r in results)}, indent=2))


if __name__ == '__main__':
    if sys.argv[1:] == ['--worker']:
        worker()
    else:
        with tempfile.TemporaryDirectory(prefix='project-largo-check-') as home:
            env = dict(os.environ, HOME=home, GSETTINGS_BACKEND='memory')
            subprocess.run([sys.executable, str(ROOT / 'install.py')], env=env, check=True)
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker'], env=env, check=True)
