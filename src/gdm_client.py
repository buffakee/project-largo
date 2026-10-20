"""Data-only GDM requests; optional Niri ownership stays outside this module."""
import hashlib
import io
import json
from pathlib import Path
import time
from urllib.parse import unquote, urlparse

from integrations import Blocked, VANILLA, read


def request(context, palette, artifacts):
    data = dict(version=1, palette=palette, desktop='gnome', time=time.time_ns(), vanilla=palette in VANILLA,
                light=palette == VANILLA[0])
    image = None
    if palette not in VANILLA:
        # Consume renderer artifacts; adapters never invoke a rendering backend.
        tokens = artifacts.get('tokens')
        if tokens is None:
            path = context.home / '.local/state/project-largo/rendered/tokens.json'
            raw = artifacts.get(path) or read(path)
            if raw is None:
                raise Blocked('Setup needed', 'Renderer tokens are missing; apply the current preset or run setup.')
            tokens = json.loads(raw)
        data['tokens'] = tokens
        from gi.repository import Gio
        background = Gio.Settings.new('org.gnome.desktop.background')
        uri = background.get_string('picture-uri-dark') or background.get_string('picture-uri')
        if urlparse(uri).scheme == 'file' and urlparse(uri).netloc in ('', 'localhost'):
            wallpaper = Path(unquote(urlparse(uri).path))
            if wallpaper.is_file():
                try:
                    from PIL import Image, ImageEnhance
                except ImportError as error:
                    raise Blocked('Administrator setup required', 'GDM wallpaper generation needs python3-pillow (Fedora: sudo dnf install python3-pillow).') from error
                with Image.open(wallpaper) as source:
                    source = source.convert('RGB')
                    source.thumbnail((3840, 2560))
                    stream = io.BytesIO()
                    ImageEnhance.Brightness(source).enhance(0.45).save(stream, format='PNG')
                image = stream.getvalue()
                data['wallpaper'] = hashlib.sha256(image).hexdigest()
    return data, image
