# Project Largo — advanced reference

For a first installation, start with [Getting started](GETTING_STARTED.md).
This reference retains the detailed behavior and manual integrations of the
current build. Release: **0.1.0-alpha.1**.

**A coordinated color system for GNOME and the applications you use.**

Project Largo applies a shared palette to GNOME Shell, GTK and existing application integrations from a native GTK4/libadwaita picker. It grew out of a working personal Fedora desktop setup and is being shared as an **experimental source release** for people to explore and improve.

This is the existing application, packaged for iterative development. It currently includes **18 custom dark palettes**, native **Vanilla Gnome** light and dark presets, and **per-theme wallpaper memory**.

![GNOME desktop overview using the Project Largo palette](assets/project-largo-desktop.png)

## What works today

- Native theme picker with color swatches, Apply and Previous palette.
- Coordinated background, text, selection, hover, accent and status roles.
- Each custom theme uses its darkest background shade for GNOME's normal top bar.
- Stock GNOME light and dark presets that reversibly suspend custom overrides.
- Remembered wallpapers for each GNOME preset, including separate light/dark image URIs and placement.
- GNOME and Niri remember separate theme selections when Noctalia is used in Niri.
- Template sources and helpers for the existing GTK, terminal, Zen/Firefox, Obsidian, LibreOffice, Zotero, Spotify, icon and developer-tool integrations.
- Rescannable application setup/repair with per-profile results and private restoration journals.
- Transaction snapshots and installer file backups.
- Default complete appearance setup: Bibata Modern Ice cursor, palette-colored YAMIS icons and 54 associated wallpaper images (17 initial theme defaults; Solarized keeps the current background).

Theme importing, a color editor and an in-app wallpaper gallery are **future work**.

## Initial compatibility

The original setup is Fedora 44 Workstation with:

| Component | Tested version |
| --- | --- |
| GNOME Shell | 50.6 |
| GTK4 / libadwaita | 4.22.5 / 1.9.4 |
| Noctalia | 5.3.0 |
| GNOME User Themes | extension 79, GNOME 50 build |
| Python | 3.14; code requires Python 3.11+ |

**GNOME Shell 50 is required by the current Shell adapter.** It recolors the installed GNOME 50 stylesheet and preserves its layout. The adapter deliberately refuses other Shell major versions until reviewed.

The renderer dependency is [noctalia-dev/noctalia](https://github.com/noctalia-dev/noctalia), the native executable providing `noctalia theme --theme-json ... --render ...` and `/usr/share/noctalia/assets/templates`. The similarly named QML/Quickshell shell is not interchangeable with this renderer. A running Noctalia shell is not required in GNOME.

Other distributions, non-default XDG directory layouts, other GNOME major versions and clean-machine end-to-end installation have not yet been verified. This is not a Flatpak, RPM or distro-independent installer.

## Install

Use your regular desktop account. Install the system prerequisites with Fedora's package manager:

```bash
sudo dnf install python3 python3-gobject gtk3 gtk4 libadwaita \
  gnome-shell gnome-extensions-app glib2-devel adw-gtk3-theme git zip noctalia
```

The Fedora `noctalia` package supplies the native renderer and template assets; neither Niri nor a running Noctalia shell or existing Noctalia user settings are required. `glib2-devel` supplies `gresource`, used to read GNOME's packaged stylesheet. Install and enable the **User Themes** extension version compatible with GNOME 50 through [GNOME Extensions](https://extensions.gnome.org/extension/19/user-themes/).

Then clone and inspect the installation plan:

```bash
git clone https://github.com/buffakee/project-largo-alpha.git
cd project-largo-alpha
python3 install.py --dry-run
python3 install.py
```

The user-local installer copies the current sources, palettes, templates and bundled appearance assets; creates the launcher and GNOME autostart entry; and adds imports for the generated GTK3/4 CSS. Missing generated GTK files receive harmless comment-only placeholders until the first custom theme is applied; existing generated colors are preserved. On first appearance enrollment it selects **Bibata Modern Ice** and **YAMIS**, preserving cursor size and backing up the previous selections. Reinstallation preserves later appearance selections and wallpaper memories. It does not apply a color palette, install third-party applications, install/enable extensions, or start services.

The appearance assets are included in the checkout (about 99 MiB); installation does not download them. They install under `~/.local/share/icons/` and `~/.local/share/project-largo/`. The installed cursor remains selected in Vanilla presets, which restore stock Adwaita icons. See [appearance asset notes](assets/appearance/README.md) for provenance and layout.

Launch **Project Largo** from your applications menu, or run:

```bash
~/.local/bin/project-largo pick
```

Apply a preset, close applications whose profiles need setup, then press
**Set up / Refresh integrations**. The operation detects installed applications
and initialized profiles again every time; missing optional apps are normal.
After installing another application or creating another profile/vault, use the
button again. GDM has a separate administrator-authenticated action. See
[INTEGRATIONS.md](INTEGRATIONS.md) for scope, statuses and restoration.

For immediate wallpaper saving, enable the GNOME-session listener:

```bash
systemctl --user daemon-reload
systemctl --user enable --now oma-wallpaper-memory.service
```

The listener is tied to the GNOME session. Without it, switching/reapplying through the app still captures the outgoing wallpaper, but external wallpaper edits are not immediately written to Project Largo's memory.

## Wallpaper behavior

Apply a theme, then change its wallpaper normally in GNOME. That wallpaper is restored the next time the theme is applied, until you choose another image while the theme is active. Wallpaper placement and separate GNOME light/dark URI slots are retained. Vanilla Light and Dark have independent memories.

The installer includes all 54 images associated with the existing custom themes. Seventeen themes have an initial bundled default, preferring the original setup's remembered GNOME wallpaper where available and otherwise its first association. **Solarized has no supplied default and keeps the current background.** Existing local Noctalia favorite pairings remain optional compatibility inputs. Saved GNOME wallpaper memory takes precedence over all defaults. Other associated images are installed under `~/.local/share/project-largo/wallpapers/` and can be selected through GNOME normally; there is no in-app gallery.

When upgrading an earlier installation, a previously remembered background is intentionally retained. To explicitly replace the active custom theme's remembered wallpaper with its bundled default:

```bash
~/.local/bin/project-largo wallpaper-default
```

This updates both URI slots and the active preset's memory. It reports when the active preset has no bundled default (Solarized and Vanilla). Wallpaper images you select elsewhere must remain at their saved locations.

## Application integrations

The setup button maintains the prioritized LibreOffice, Zen, Obsidian and native
Zotero integrations. GDM setup is optional and separate. Other existing template
integrations retain the setup requirements listed below. Enrollment is a one-time
step per supported profile; ordinary palette changes subsequently update enrolled
applications. Running clients may require reopening or closing before profile work.

| Integration | Current behavior / setup |
| --- | --- |
| GNOME Shell | Requires enabled User Themes; normal top bar follows each custom palette's shadow role. |
| GTK3 / GTK4 | Generated CSS is imported into the user GTK configuration. Client/toolkit support determines the exact result; not every libadwaita app accepts full recoloring. |
| Kitty | Add `include themes/noctalia.conf` to your Kitty configuration. Applying a theme signals running Kitty processes to reload. |
| Other terminals | Existing enabled Noctalia built-in templates are reused for supported installed configurations. |
| YAMIS icons | Installed and enrolled by default. The helper produces alternating themes colored with the palette's text/foreground role. Vanilla uses stock Adwaita; custom themes restore YAMIS. Other deliberately selected third-party icon sets are left selected. |
| Bibata cursor | Bibata Modern Ice is installed and selected once. Cursor size is preserved; subsequent theme changes and reinstallations preserve cursor selection. |
| Zen | Setup enrolls registered native/Flatpak profiles, CSS imports, stylesheet loading and native workspace gradient references. Existing browser-owned geometry and non-theme session data are preserved. Fully quit/reopen after changing startup-loaded CSS. Unknown session formats are reported without edits. |
| Firefox | CSS is generated; profile stylesheet imports and startup stylesheet loading remain manual. |
| Obsidian | Setup enables the generated snippet in registered native/Flatpak vaults. Only `.obsidian` configuration/snippets are accessed; personal notes are never read or modified. |
| LibreOffice | Setup discovers native/sandbox unopkg, verifies registration and exact extension colors, selects the scheme and enrolls supported GTK3 desktop launch routes. Profiles and extensions are changed only while the suite is closed. The generated launcher retries deferred work before the suite starts. |
| Native Zotero | Setup enrolls UI imports/loading and installs the local PDF bridge package; Zotero must activate it after reopening. Zotero Flatpak is outside maintained scope. |
| GDM | Separate authenticated setup installs an account-bound root-owned publisher, system units and a GDM-only resource overlay for GNOME 50. No session/login-manager restart. |
| Spotify | Requires an existing Spicetify Marketplace/Ziro setup. The color-overlay source is in `extras/spotify/`; it must be installed/enabled in Spicetify. |
| Codex / OpenCode / Fastfetch / Omawrite | Existing templates/configuration helpers are included. Existing clients must select/import their generated theme; missing client configurations are not enrolled automatically. |

Generated colors and an active application theme are separate things. Applications that load styles at startup need reopening. Flatpak clients may need appropriate access to the generated assets. See [DEVELOPMENT.md](DEVELOPMENT.md) for the source layout.

## Commands and recovery

```bash
project-largo list
project-largo status
project-largo apply "oma Largo"
project-largo apply "Vanilla Gnome"
project-largo apply "Vanilla Gnome Dark"
project-largo rollback
project-largo verify --output /tmp/project-largo-validation
project-largo integrations status --json
project-largo integrations setup
project-largo integrations repair --app libreoffice
project-largo integrations restore OPERATION
```

`rollback` applies the previously selected preset. It is not a complete restoration of every historical configuration edit. File/settings snapshots are kept separately under `~/.local/state/oma-theme/`.

To remove the installed source/configuration files:

```bash
~/.local/bin/project-largo apply "Vanilla Gnome"
systemctl --user disable --now oma-wallpaper-memory.service
python3 install.py --uninstall
systemctl --user daemon-reload
```

The uninstaller restores files captured by the installer, refusing to discard later edits to those files. It removes installer-owned appearance assets and restores previous cursor/icon selections when the current selections still belong to this setup; later third-party selections are preserved. Initial selection backups are under `~/.local/state/oma-theme/appearance-install.json`. It retains generated application state (including colored icon slots), wallpaper memories and recovery snapshots; it is not an application-data purge. Keep a checkout available for removal. This initial installer is not a general migration/update manager.

## Development and contributions

See [DEVELOPMENT.md](DEVELOPMENT.md). Issues describing the GNOME version, application/backend and reproducible steps are useful. Small, focused pull requests are welcome.

Internal `oma-theme`, `Oma-GNOME-*`, `noctalia` and `omarchy` identifiers are retained for compatibility with existing generated files and integrations. The application is now named **Project Largo**.

## License and credits

Project Largo's original code is **GPL-3.0-only**, copyright © 2026 [buffakee](https://github.com/buffakee). See [LICENSE](LICENSE).

Theme palettes, inherited templates, cursor/icon artwork and wallpapers retain their applicable notices. See [THIRD_PARTY.md](THIRD_PARTY.md), `LICENSES/` and the appearance asset manifest. Noctalia, GNOME, User Themes, Omarchy, Bibata, YAMIS and the original palette/artwork authors made this work possible. Asset inclusion does not relicense third-party artwork as Largo's original code.
