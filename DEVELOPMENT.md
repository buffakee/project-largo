# Developing Project Largo

## Source layout

- `src/engine.py`: rendering, GNOME settings, application refresh hooks, transactions and CLI.
- `src/picker.py`: GTK4/libadwaita theme picker.
- `src/vanilla.py`: stock Light/Dark and reversible suspension of custom overrides.
- `src/wallpaper.py`: per-preset memory and event-driven GNOME listener.
- `src/appearance.py`: bundled asset validation, one-time cursor/icon enrollment, selective restoration and default wallpapers.
- `src/renderer.py`: Largo-owned renderer API; the native Noctalia backend returns tokens/artifacts without profile publication.
- `src/integrations.py`: shared setup/status/repair CLI, enrollment, private journals, conflict-aware restoration and serialization.
- `src/integration_apps.py`: guarded LibreOffice, Zen, Obsidian, native Zotero and optional GDM adapters.
- `src/gdm_{client,admin}.py`: user data publisher and standalone root-owned GDM installer/publisher/recovery tool.
- `src/validate-css.py`: native GTK/Shell stylesheet parser checks.
- `assets/noctalia/`: existing palette sources, templates and integration helpers.
- `assets/community/`: existing Noctalia LibreOffice helper/static extension files and Steam template.
- `assets/appearance/`: associated wallpapers, portable manifest, compressed icon/cursor sources and matching Bibata build source.
- `extras/spotify/`: existing Spicetify/Ziro color overlay, installed separately.
- `desktop/`: desktop/service templates; the installer fills the user's home path.
- `tests/`: isolated packaging, recovery and color-role tests.
- `SOURCE_ORIGINS.json`: allowlisted source origins and hashes at preservation time, before packaging edits.

All Markdown files here are project documentation. Machine-specific preservation reports and private snapshots stay outside the repository.

## Checks

```bash
python3 -m unittest discover -s tests -v
```

The default tests use temporary homes and the in-memory GSettings backend. They do not apply colors to the real desktop. With the native Noctalia renderer and GTK/Shell dependencies installed, run the render checks too:

```bash
python3 tools/check-render.py
python3 tools/check-appearance.py
```

This installs into a temporary home, renders every palette and runs the native CSS parsers. It does not apply the output. The Shell parser currently uses the Fedora GNOME 50 / Mutter 18 library paths.

`check-appearance.py` uses a temporary home and in-memory GSettings. It exercises native rendering/publication, initial cursor/icon setup, every supplied wallpaper default, two palette-colored icon slots, personal wallpaper memory, Vanilla Light/Dark/custom recovery, reinstall preservation and uninstall restoration. Shell status and unrelated app refreshes are isolated; the icon helper's GSettings CLI is bridged to the same in-process memory backend. It does not establish live compositor visuals or login behavior.

On a configured GNOME test desktop, use `project-largo verify --output /tmp/project-largo-validation` to check that installation's integrations. Live switching, actual login/logout and application visuals are separate checks; passing an isolated render does not establish their behavior.

## Packaging changes from the preserved baseline

- Renamed the visible picker and launcher to Project Largo.
- Replaced the original dated `~/Work` runtime-backup dependency with a state-directory baseline.
- Allowed absent Niri/Steam configuration and absent Codex/LibreOffice client profiles.
- Look up User Themes schemas in user/system extension locations.
- Added a user-local source installer, installer file backups and documentation.
- Removed the author-specific absolute wallpaper source path from the Largo palette metadata.
- Treat an absent Noctalia settings file as empty optional compatibility input for both wallpaper pairings and integration selections; read template selections from their top-level table.
- Seed missing generated GTK CSS with comment-only runtime placeholders before adding imports, without overwriting existing colors or tracking mutable output as installer-owned source.
- Check required renderer/resource prerequisites before rendering and document Fedora's `glib2-devel` package for `gresource`.

The palette roles, stock presets, top-bar behavior and wallpaper memory remain the existing implementation. First-run setup now adds a Largo-owned renderer boundary and guarded adapters; see [INTEGRATIONS.md](INTEGRATIONS.md). No theme editor, import UI or wallpaper gallery has been added.

## Historical support evidence

Before packaging, the working desktop passed native Light/Dark/custom switching, separate wallpaper memories, custom same-theme reapply, startup restore command, listener restart, cursor preservation and Niri isolation checks. All 18 custom Shell stylesheets parsed; tested top-bar text contrast was at least 8.72:1.

These checks describe the original configured machine. The package's independent checks are documented above. A clean-machine interactive installation, other GNOME major versions and full application-profile enrollment remain unverified.

### Clean-install regression checks (2026-10-20)

The nine isolated tests cover absent Noctalia user settings, GNOME appearance changes with in-memory settings and a mocked Shell theme selection, unchanged wallpaper without optional pairings, existing favorite/memory precedence, actionable missing-`gresource` errors, first-run GTK placeholders and preservation of generated colors through reinstall/removal, alongside the existing recovery checks. All 18 palettes also rendered in a fresh temporary home and passed native GTK/Shell CSS parsing. These checks do not establish full interactive VM or login behavior.

### Complete appearance setup checks (2026-10-20)

The suite now has 11 tests, including one-time appearance enrollment/selective recovery and comment-preserving GTK setting edits. Native isolated appearance switching additionally passed cursor file magic/size preservation, image-header loading for all 54 wallpapers, all 17 default associations, exact Largo/Nord foreground colors in generated icon files and markers, Light/Dark/custom recovery, user wallpaper-memory precedence, reinstall preservation and previous-selection restoration on removal. All 18 palettes passed native CSS parsing again with the bundled assets installed. Interactive VM visuals and login remain separate checks.

### Zen UI palette coverage (2026-10-20)

The bundled Zen chrome/content templates now include the subsequent native UI coverage work: expanded URL popup, shared confirmation and input prompts, menus/tooltips, site/bookmark/permission panels, settings subdialogs and print controls. The content template explicitly selects browser-owned `chrome://` documents rather than arbitrary content pages.

The configured Fedora machine passed 18 paired palette renders, 36 native Zen CSS parses, five text/background contrast pairs per palette (minimum 4.97:1), representative isolated native popup/dialog/input/print checks and an unrelated-content isolation check. Earlier URL-popup, confirmation-control, native-radius and gradient-role checks also passed. Individual uncommon dialogs have not each been visually checked. Machine-specific test profiles, evidence and selective rollback snapshots remain outside this repository.

The templates continue to use the existing engine deployment path. Fully quit and reopen Zen after changing palettes; the browser loads these styles at startup.

## Contributing

### First-run enrollment checks

The expanded suite covers fresh/later installation, stale uninstalled profiles,
native/Flatpak command discovery, verified registration rather than exit-code
trust, per-target failures, profile locks/concurrent edits, note-access guards,
repeat setup, ordinary updates and conflict-aware restoration. The GDM system
transaction test substitutes a synthetic system root and mocked service commands.
It does not install root files on the development machine.
On 2026-10-20, all **50 unit tests**, all 18 native palette/CSS checks, isolated
appearance switching/recovery and the three optional checks below passed locally.

Additional optional checks on the documented Fedora dependencies:

```bash
python3 tools/check-picker.py
python3 tools/check-gdm.py
python3 tools/check-office.py
```

The picker check uses a private GTK4 Broadway display and non-unique app identity,
with fixture backend results. The GDM check parses 36 real stylesheets and checks
Vanilla stock equality without root installation. The office check uses real
native unopkg with both HOME/XDG paths and UserInstallation isolated in a temporary
directory, verifies deployed colors/registration/idempotence and restores the
profile/launchers; it never opens the regular suite or touches its default profile.
Its process guard is scoped to the exclusively owned disposable profile, so live
instances using different profiles do not prevent this isolated check.
It also verifies that setup artifacts match ordinary application artifacts and
that malformed unrelated Fastfetch/Starship settings do not block setup rendering.

Flatpak extension installation/activation and clean-VM interactive application
visuals remain separate from fixture and native tests. Status readiness is a
configuration/registration claim, not proof of every application's live pixels.

Keep patches focused, preserve unrelated user configuration, and describe which environment you tested. Application integration changes should identify their owned configuration fields and how to undo them. Add tests for meaningful recovery, input-validation or cross-theme behavior changes.

Potential next iterations: theme import, per-theme wallpaper galleries, a theme editor, and further individually verified adapters. These are ideas, not release promises.
