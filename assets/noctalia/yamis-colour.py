#!/usr/bin/python3
"""Build a palette-coloured YAMIS theme from the unmodified upstream source."""
import fcntl
import configparser
import json
import re
import shutil
import subprocess
from pathlib import Path

HOME = Path.home()
ICONS = HOME / ".local/share/icons"
SOURCE = "yet-another-monochrome-icon-set"
SLOTS = ("yamis-noctalia-a", "yamis-noctalia-b")
STATE = HOME / ".local/state/noctalia"
GSETTINGS = ["/usr/bin/gsettings"]
SCHEMA = "org.gnome.desktop.interface"


def render(source, destination, accent):
    """Retain geometry, transparency, relative aliases and explicit status colours."""
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        raise ValueError("Expected a six-digit accent colour")
    shutil.copytree(source, destination, symlinks=True,
                    ignore=shutil.ignore_patterns(".git", "icon-theme.cache"))
    count = 0
    for icon in destination.rglob("*.svg"):
        if icon.is_symlink():
            # Upstream aliases must resolve inside the generated theme.
            if not icon.resolve().is_relative_to(destination.resolve()):
                raise ValueError(f"External icon alias: {icon}")
            continue
        text = icon.read_text()
        # Resolve currentColor explicitly: GTK and Qt otherwise handle the
        # pack's KDE ColorScheme-Text classes differently.
        coloured = re.sub(r"\bcurrentColor\b", accent, text, flags=re.I)
        coloured = re.sub(r"#d8dee9\b", accent, coloured, flags=re.I)
        if coloured != text:
            icon.write_text(coloured)
            count += 1
    index = destination / "index.theme"
    text = index.read_text()
    text = re.sub(r"(?m)^Name=.*$", "Name=YAMIS — Project Largo", text)
    text = text.replace("FollowsColorScheme=true", "FollowsColorScheme=false")
    index.write_text(text)
    (destination / ".noctalia-accent").write_text(accent + "\n")
    subprocess.run(["/usr/bin/gtk-update-icon-cache", "-f", "-t", str(destination)],
                   check=True)
    return count


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "yamis-colour.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        accent = json.loads((STATE / "yamis-colour.json").read_text())["accent"]
        current = subprocess.check_output(
            GSETTINGS + ["get", SCHEMA, "icon-theme"], text=True).strip().strip("'")
        if current not in (SOURCE, *SLOTS):
            print("YAMIS: another icon theme is selected; leaving it selected")
            return
        marker = ICONS / current / ".noctalia-accent"
        if marker.exists() and marker.read_text().strip() == accent:
            print(f"YAMIS: already using {accent}")
            return
        # Alternate two bounded output directories so applications see a real
        # theme-name change and invalidate their in-memory icon caches.
        name = SLOTS[1] if current == SLOTS[0] else SLOTS[0]
        destination = ICONS / name
        if destination.exists():
            if not (destination / ".noctalia-accent").exists():
                raise RuntimeError(f"Refusing to replace an unowned directory: {destination}")
            shutil.rmtree(destination)
        count = render(ICONS / SOURCE, destination, accent)
        for version in (3, 4):
            settings = HOME / f".config/gtk-{version}.0/settings.ini"
            parser = configparser.ConfigParser(interpolation=None)
            if settings.exists():
                parser.read_string(settings.read_text())
            if not parser.has_section('Settings'):
                text = settings.read_text() if settings.exists() else ''
                text = text.rstrip() + '\n[Settings]\ngtk-icon-theme-name=' + name + '\n'
            else:
                text = settings.read_text()
                section = re.search(r'(?m)^\[Settings\][^\n]*\n?', text)
                following = re.search(r'(?m)^\[', text[section.end():])
                stop = section.end() + following.start() if following else len(text)
                body = text[section.end():stop]
                body, matches = re.subn(r'(?m)^gtk-icon-theme-name\s*=.*(?:\n|$)',
                                      lambda _: 'gtk-icon-theme-name=' + name + '\n', body)
                if matches == 0:
                    body = 'gtk-icon-theme-name=' + name + '\n' + body
                text = text[:section.end()].rstrip('\n') + '\n' + body + text[stop:]
            settings.parent.mkdir(parents=True, exist_ok=True)
            settings.write_text(text)
        subprocess.run(GSETTINGS + ["set", SCHEMA, "icon-theme", name], check=True)
        print(f"YAMIS: applied {accent} to {count} SVGs ({name})")


if __name__ == "__main__":
    main()
