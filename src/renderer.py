"""Largo renderer boundary. Noctalia is a backend, not the integration registry."""
import json
from pathlib import Path
import re
import subprocess


class NoctaliaRenderer:
    def render(self, definition, templates, directory):
        """Return (tokens, artifacts keyed by template index); never publish files."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        source = directory / 'input.json'
        source.write_text(json.dumps({'dark': definition['dark'], 'light': definition['dark']}))
        command = ['/usr/bin/noctalia', 'theme', '--theme-json', str(source),
                   '--dark', '--default-mode', 'dark']
        tokens = json.loads(subprocess.run(command, check=True, capture_output=True,
                                           text=True, timeout=120).stdout)
        if not all(isinstance(v, str) and re.fullmatch(r'#[\da-fA-F]{6}', v) for v in tokens.values()):
            raise ValueError('Renderer returned invalid palette tokens')
        for index, template in enumerate(templates):
            command += ['--render', f'{template}:{directory}/{index}-{Path(template).name}']
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
        artifacts = {i: (directory / f'{i}-{Path(t).name}').read_bytes() for i, t in enumerate(templates)}
        if any(b'{{' in value for value in artifacts.values()):
            raise ValueError('Renderer left unresolved template variables')
        return tokens, artifacts
