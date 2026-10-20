# Changelog

## 0.1.0-alpha.1 — 2026-10-20

- Start a separate new-user-focused Alpha repository from the current first-run build, retaining runtime code and assets.
- Add a first-install guide, recovery guide, versioned source kit and Alpha verification notes.

- Add GTK **Set up / Refresh integrations** and matching setup/status/repair/recovery commands with per-profile outcomes and isolated verification.
- Discover installed native/Flatpak apps and registered profiles again on each run; skip missing apps and continue after individual failures.
- Introduce a Largo-owned renderer API and independent integration registry, retaining the native Noctalia backend and optional Niri compatibility.
- Enroll guarded LibreOffice, Zen, registered Obsidian vaults and native Zotero; maintain generated assets during ordinary palette application and reversible Vanilla transitions.
- Discover LibreOffice unopkg inside its actual sandbox; verify registration and exact colors, preserve retryable failures and support GTK3 desktop routes.
- Add separately authenticated, account-bound GDM system setup/restoration based on the existing local implementation, without session/login-manager restart.
- Install and enroll Bibata Modern Ice and YAMIS icons by default, preserving cursor size and previous selections for removal.
- Include 54 currently associated wallpapers, with portable defaults for 17 custom themes; Solarized intentionally keeps the current background.
- Preserve wallpaper memory and later cursor/icon choices on reinstall; provide `wallpaper-default` to explicitly reset the active custom theme's wallpaper.
- Avoid capturing an inferred preset's wallpaper before the first successful application, including listener startup.
- Support fresh GTK settings files in the icon recoloring helper and include cursor source/artwork notices and an integrity manifest.
- Allow GNOME theme application without an existing Noctalia settings file; optional wallpaper pairings leave the current wallpaper intact when absent.
- Keep Noctalia settings optional for Niri selection and historical wallpaper pairings; application template selections are now Largo-owned.
- Seed absent GTK runtime stylesheets before installing their imports, preserving existing generated colors on reinstall.
- Document Fedora's `glib2-devel`/`gresource` dependency and report missing renderer/resource prerequisites before rendering.
- Connect Zen's expanded URL popup, confirmation dialogs, menus, tooltips, site/bookmark/permission panels and shared controls to the selected palette.
- Theme browser-owned settings subdialogs, text-entry prompts and print controls through an explicit `chrome://` document allowlist.
- Preserve native workspace gradients and layout; startup-loaded Zen styles require a full browser quit/reopen after switching palettes.

## Historical baseline — original experimental source snapshot

- Publish the working GNOME palette picker as **Project Largo**.
- Preserve 18 custom dark palettes and native Vanilla Gnome Light/Dark presets.
- Preserve darkest-role GNOME top bars and per-theme wallpaper memory.
- Include existing application integration templates/helpers, source installer, recovery information and isolated checks.
- Retain legacy internal IDs and paths for compatibility with the original installation.

This is an early source version. Automatic theme importing/editing and an in-app wallpaper gallery are not implemented. First-run integration scope and remaining interactive verification are documented in INTEGRATIONS.md.
