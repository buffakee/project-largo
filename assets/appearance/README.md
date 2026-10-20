# Complete appearance assets

These assets reproduce the selected setup's cursor, monochrome icons and existing wallpaper associations. They are separate from Largo's original Python code.

- `manifest.json`: portable filenames, SHA-256 hashes, 18 custom-theme entries and their wallpaper associations. Seventeen entries have defaults; Solarized deliberately has none.
- `wallpapers/`: 54 unmodified images from the user's explicitly selected associations. The three existing GNOME wallpaper memories determine defaults for Largo, Kanagawa and Retro 82; other themes use their first association.
- `icons.tar.xz`: Bibata Modern Ice v2.0.6 XCursors and the installed YAMIS SVG source snapshot. Aliases are materialized as regular files containing identical bytes, avoiding platform-specific archive link extraction. Licenses and existing authorship files are retained.
- `bibata-v2.0.6-source.tar.gz`: matching upstream cursor source, including SVGs, build scripts and license, from <https://github.com/ful1e5/Bibata_Cursor/tree/v2.0.6>.

YAMIS source: <https://bitbucket.org/dirn-typo/yet-another-monochrome-icon-set/>, installed checkout base `227359bea788d55d202d9aad5f2daf63fe644cc3`. This export reflects the installed tree, including its absence of the HyprMod icon; no Git metadata or generated icon caches are included.

The original artists and per-image licensing of the user-provided wallpaper collection are not recorded in the local associations. The manifest identifies that fact rather than attributing the images to the palette author or applying the code license to them. The palette source links are context, not proof of image authorship. This is the existing private experimental collection; public-release provenance review remains tracked in `THIRD_PARTY.md`.

## Rebuilding the export

`tools/prepare-appearance.py` takes explicitly supplied Noctalia settings, GNOME wallpaper-memory JSON and icon source directory. It writes only this asset export, never the user's configuration. No absolute source filenames or private runtime settings are copied into the manifest. It downloads the tagged Bibata license and source while preparing the export; ordinary installation is offline for these assets.

## Installed behavior

Images and the portable manifest install to `~/.local/share/project-largo/`. Theme source files install to `~/.local/share/icons/`. All bundled asset hashes are checked before installation writes begin. Generated YAMIS A/B slots remain runtime outputs and use the current palette's foreground color.

`project-largo wallpaper-default` explicitly restores the active custom theme's bundled default. Normal palette switching and reinstalling preserve personal wallpaper memories. The installer captures previous cursor/icon selections once and never changes cursor size.
