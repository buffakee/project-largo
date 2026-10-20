# Project Largo Alpha 1

**Version:** 0.1.0-alpha.1 · **Date:** 2026-10-20 · **Status:** prerelease

This is the first Alpha in the new-user-focused
[`buffakee/project-largo-alpha`](https://github.com/buffakee/project-largo-alpha)
repository. It packages the current first-run build of Project Largo, with clear
installation, app enrollment, diagnostics and recovery documentation.

## Included

- 18 custom dark palettes and native GNOME Light/Dark presets.
- Palette-colored YAMIS icons and Bibata Modern Ice, preserving cursor size.
- 54 associated wallpapers, 17 supplied defaults and per-preset wallpaper memory.
  Solarized keeps the current background; `wallpaper-default` explicitly resets
  a theme with a supplied default.
- GTK **Set up / Refresh integrations**, eight explicit statuses and CLI
  setup/status/repair/restoration.
- Guarded native/Flatpak LibreOffice and Zen setup, registered native/Flatpak
  Obsidian vault enrollment and native Zotero UI/PDF bridge setup.
- Optional, separately authenticated GDM setup/restoration for GNOME 50.
- Noctalia-backed Largo renderer interface and independent integration state.
- Source-kit verification with isolated test homes; the appearance test fixture
  uses bundled palettes instead of relying on an existing local installation.

Runtime code and assets are byte-preserved from the current build. The source
snapshot is recorded in `UPSTREAM_SNAPSHOT.json`, including the earlier published
baseline commit `c1958f2` and hashes for the subsequent first-run implementation.
The original repository and live desktop installation are separate from this
Alpha repository.

## Verification

The current runtime build passed:

| Check | Result |
| --- | --- |
| Unit suite | 50 tests passed. |
| Native palette/CSS checks | All 18 palettes passed. |
| Isolated appearance switching/recovery | Passed, including wallpaper/cursor/icon behavior and reinstall preservation. |
| GTK controls | Headless Broadway setup flow, eight statuses and separate admin control passed. |
| GDM rendering | 36 native stylesheet parses and exact stock Vanilla resources passed. |
| Native LibreOffice | Real unopkg enrollment, registration/color verification, idempotent repair, desktop validation and restoration passed in a disposable profile. |

The source kit is additionally extracted and checked before publication, including
an installer dry-run and the unit suite from the extracted archive. The release
asset checksum is provided in `SHA256SUMS`.

## Known verification limits

- Targeted environment: Fedora 44 / GNOME Shell 50. Other Shell majors,
  distributions and non-default XDG layouts remain unverified.
- Noctalia remains a required **native renderer**, not a running desktop shell.
- Real Flatpak LibreOffice enrollment is fixture-tested; that Flatpak was absent
  on the development machine. Native success does not establish sandbox behavior.
- Fresh interactive browser/vault startup, Zotero extension activation/visuals,
  complete clean-VM installation and actual GDM login behavior remain pending.
- Status readiness verifies configuration/registration, not every live pixel.
- Startup-loaded app CSS needs reopening. Profile/extension work is deferred while
  the owning app is running; restart observations are intentionally conservative.
- Zotero Flatpak is outside maintained scope. Other inherited template integrations
  retain the manual prerequisites in [the advanced reference](REFERENCE.md).
- Theme importing/editing and an in-app wallpaper gallery are not included.

## Installation and feedback

Start with [GETTING_STARTED.md](GETTING_STARTED.md). For a report, include Alpha
version, Fedora/GNOME version, app/backend, reproduction steps and the relevant
integration status/error. Recovery instructions are in [RECOVERY.md](RECOVERY.md).

The Alpha remains private with its existing third-party notices and asset
provenance documentation intact. See [THIRD_PARTY.md](THIRD_PARTY.md).
