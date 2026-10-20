# Third-party notices and provenance

Project Largo's original Python application and locally authored adapters are offered under GPL-3.0-only. Existing permissively licensed material keeps its original notices; distributing it with this project does not erase those licenses.

## Omarchy and palette sources

- Upstream: <https://github.com/omacom/omarchy>
- Palette source revision recorded by the original setup: `1a161eb5192ac555b99458c52f5fa80344cb3556`.
- License: MIT; reproduced in `LICENSES/Omarchy-MIT.txt`.
- `assets/noctalia/palettes/oma *.json` retain their upstream `_source` URLs where available. They are adapted semantic-role palettes rather than unmodified upstream theme packages. Largo is an original local palette.
- Browser/application templates grew out of the same Omarchy-inspired desktop integration work; the MIT notice is retained for inherited portions.

Palette names credit their respective upstream themes/authors. This project does not claim authorship of Nord, Catppuccin, Gruvbox, Kanagawa or other upstream color schemes, and does not bundle their wallpaper collections.

## Noctalia

- Renderer: <https://github.com/noctalia-dev/noctalia>, tested native package 5.3.0.
- Template ecosystem: <https://github.com/noctalia-dev/community-templates>.
- MIT notice from the installed Noctalia package: `LICENSES/Noctalia-MIT.txt`.
- GTK role templates and existing community LibreOffice/Steam sources retain their upstream structure, with local role mapping/application changes. The source allowlist is recorded in `SOURCE_ORIGINS.json`.
- The Noctalia executable and packaged built-in templates are runtime dependencies, not vendored binaries.

The community-templates repository did not expose a top-level license in the upstream metadata checked for this snapshot. Its LibreOffice/Steam files are preserved here with their source attribution; the installed renderer's MIT license should not be taken as proof of a separate community contribution's license. They are not being claimed as newly authored GPL code by Project Largo. Resolve that upstream licensing question before redistributing those portions as a standalone theme/integration bundle.

## GNOME and User Themes

- GNOME Shell: <https://gitlab.gnome.org/GNOME/gnome-shell>, GPL-2.0-or-later.
- User Themes: <https://gitlab.gnome.org/GNOME/gnome-shell-extensions>, GPL-2.0-or-later.
- The current adapter reads GNOME's installed stylesheet at runtime; this repository does not contain stock/generated GNOME Shell CSS or the extension archive.

## Other external applications and assets

GTK, libadwaita, PyGObject, LibreOffice, Zotero, Zen, Firefox, Obsidian, Spicetify, Spotify and other supported clients remain separate projects under their own licenses. Those applications are not redistributed by this source package. The bundled Spotify file is the locally authored color overlay, not Marketplace or Ziro's implementation.

### Complete appearance assets

- **Bibata Modern Ice v2.0.6**, by Abdulkaiz Khatri and contributors: <https://github.com/ful1e5/Bibata_Cursor/tree/v2.0.6>, GPL-3.0-or-later per upstream license. Installed XCursors and license are included in `assets/appearance/icons.tar.xz`; corresponding tagged SVG/build source and full license are included in `bibata-v2.0.6-source.tar.gz` alongside it.
- **Yet Another Monochrome Icon Set**, dirn-typo and credited contributors: <https://bitbucket.org/dirn-typo/yet-another-monochrome-icon-set/>, installed source checkout base `227359bea788d55d202d9aad5f2daf63fe644cc3`. GPL version 3 license, `Authors`, readme and original SVGs are included in the icon archive. The installed tree lacks the HyprMod icon. Original artwork is retained; runtime recoloring is performed on generated copies.
- **Wallpapers:** 54 unmodified images explicitly selected from the existing user's theme associations, with hashes and associations in `assets/appearance/manifest.json`. Per-image original artist/license metadata is not available in those local associations and is not inferred from a palette's `_source` URL. These files are not claimed as original GPL Largo artwork. Resolve this provenance for public redistribution of the collection; the repository remains the private experimental snapshot.

Browser profiles, personal application settings, personal vaults, runtime backups and authentication material are not part of this repository.
