# Getting started with Alpha 1

This guide targets **Fedora 44 Workstation with GNOME Shell 50**. You need a normal
desktop account; the installer itself runs **without sudo**. The Alpha is a
source build, and clean-machine interactive verification is still pending.

## 1. Install the prerequisites

```bash
sudo dnf install python3 python3-gobject gtk3 gtk4 libadwaita \
  gnome-shell gnome-extensions-app glib2-devel adw-gtk3-theme git zip noctalia
```

The required Noctalia is the **native `noctalia-dev/noctalia` renderer** providing
`noctalia theme --theme-json ... --render ...` and installed template assets.
Neither Niri nor a running Noctalia desktop shell nor existing Noctalia settings
are needed. `glib2-devel` supplies `gresource`.

Install and enable a **GNOME 50-compatible User Themes** extension from
[GNOME Extensions](https://extensions.gnome.org/extension/19/user-themes/).

Optional adapter dependencies:

- Native LibreOffice: its `unopkg` extension manager and `libreoffice-gtk3`.
- Zen workspace enrollment: system liblz4 (`lz4-libs` on Fedora).
- Optional GDM wallpaper setup: `python3-pillow` and Polkit/pkexec.

Install only applications you want to use. Largo skips missing optional apps.

## 2. Get the Alpha

Download `project-largo-alpha-0.1.0-alpha.1.tar.gz` and `SHA256SUMS` from
[the Alpha 1 release](https://github.com/buffakee/project-largo-alpha/releases/tag/v0.1.0-alpha.1).
In the download directory:

```bash
sha256sum --check SHA256SUMS
tar -xzf project-largo-alpha-0.1.0-alpha.1.tar.gz
cd project-largo-alpha-0.1.0-alpha.1
```

Or, with access to the private repository:

```bash
git clone --branch v0.1.0-alpha.1 https://github.com/buffakee/project-largo-alpha.git
cd project-largo-alpha
```

Both contain the source, templates, cursor/icons and all 54 associated wallpapers.
The installer does not download appearance assets or third-party applications.
Keep the extracted directory or checkout for recovery/removal.

## 3. Inspect and install

```bash
python3 install.py --dry-run
python3 install.py
```

Installation adds the user-local launcher, GTK imports, source files, GNOME
autostart entry and bundled assets. On initial appearance enrollment it selects
Bibata Modern Ice and YAMIS, preserving cursor size and backing up prior choices.
It does **not** apply a palette, install GNOME extensions or start services.
Later reinstallations retain your appearance selections and wallpaper memory.

## 4. Apply your first palette

Launch **Project Largo** from the applications menu, or run:

```bash
~/.local/bin/project-largo pick
```

Choose a preset and press **Apply palette**. Vanilla Gnome and Vanilla Gnome Dark
provide stock GNOME appearance; the 18 custom presets coordinate palette colors.
If the Shell theme does not change, check that User Themes is enabled and
compatible with GNOME 50.

## 5. Set up your applications

1. Open a newly installed supported app once so it creates its own profile.
   For Obsidian, register/open the vault you want themed.
2. Fully close apps whose profile/settings/extension hooks need enrollment.
3. In Largo, press **Set up / Refresh integrations**.
4. Read the individual results. Missing apps are skipped. Follow any **Open app
   once**, **Close app and retry**, **Restart required** or administrator message.
5. Reopen startup-styled apps to load the new palette. Zotero may need its PDF
   bridge enabled in the plugin manager after installation.

Setup uses the currently **applied** preset, not another highlighted picker row.
You do not need to rerun setup on every palette change. Use it again after adding
an application/profile/vault or when status reports a hook needing repair.

CLI equivalents:

```bash
~/.local/bin/project-largo integrations status --json
~/.local/bin/project-largo integrations setup
~/.local/bin/project-largo integrations repair --app libreoffice
```

GDM is optional. Its **Set up GDM (Administrator…)** control is a separate action;
normal app setup does not silently install system services. Read the
[GDM setup and recovery details](INTEGRATIONS.md#gdm-separate-administrator-setup)
before using that option. It never restarts the current session or GDM.

## 6. Wallpaper memory

After applying a preset, choose a wallpaper normally in GNOME. Largo remembers
that preset's choice when you switch/reapply through Largo. To save external
wallpaper edits immediately, enable the supplied GNOME-session listener:

```bash
systemctl --user daemon-reload
systemctl --user enable --now oma-wallpaper-memory.service
```

Light/Dark Vanilla presets have separate memories. Seventeen custom themes have
supplied defaults; Solarized keeps the current wallpaper. To explicitly restore
the active custom theme's supplied default:

```bash
~/.local/bin/project-largo wallpaper-default
```

For troubleshooting, start with [the status meanings](INTEGRATIONS.md#status-meanings),
[recovery](RECOVERY.md) and [Alpha verification notes](ALPHA_NOTES.md).
