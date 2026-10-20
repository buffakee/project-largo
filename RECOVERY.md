# Recovery and removal

Largo keeps appearance snapshots and integration journals. A previous-palette
switch, restoring an integration operation and uninstalling source files are
different actions.

## Return to stock GNOME appearance

Use the picker to apply **Vanilla Gnome** or **Vanilla Gnome Dark**, or run:

```bash
~/.local/bin/project-largo apply "Vanilla Gnome"
```

Close apps whose profile changes are deferred and retry application if needed.
Vanilla reversibly suspends custom overrides and keeps your cursor selection.
Returning to a custom palette restores the coordinated appearance.

## Return to the previous preset

```bash
~/.local/bin/project-largo rollback
```

This reapplies the previous preset. It is not a complete restoration of all
historical configuration edits.

## Diagnose or restore an application integration

```bash
~/.local/bin/project-largo integrations status --json
~/.local/bin/project-largo integrations repair --app libreoffice
~/.local/bin/project-largo integrations restore OPERATION
```

Use the actual operation ID printed by setup/status. Fully close the relevant
application before restoration. Restore operations **newest-first**; a restored
update returns the previous enrollment record. The private journals live under
`~/.local/state/project-largo/integrations/operations/`.

Restoration preserves unrelated later settings and browser tabs where a selective
merge is possible. Conflicting owned edits or changed extension-manager storage
are preserved for review instead of overwritten. A retained backup after a
blocked/failed operation remains available when the app is closed.

Full details: [integration backups and restoration](INTEGRATIONS.md#backups-and-restoration).

## Restore optional GDM system setup

Use the separate administrator operation ID printed by GDM setup:

```bash
~/.local/bin/project-largo integrations admin-restore ADMIN_OPERATION
```

Root backups are under `/var/lib/project-largo-gdm-backup/`. Setup failures print
the retained root-owned recovery helper command. This restores Largo's system
configuration without restarting the desktop session or login manager. Existing
greeter processes can retain already-loaded resources until a later startup.

## Remove the user-local installation

Restore any desired app integration operations and optional GDM system setup
before removing the installed sources. Then, from the retained Alpha directory:

```bash
~/.local/bin/project-largo apply "Vanilla Gnome"
systemctl --user disable --now oma-wallpaper-memory.service
python3 install.py --uninstall
systemctl --user daemon-reload
```

The installer restores its backed-up files and previous appearance selections
when they still belong to this installation, preserving later third-party
choices. It refuses to discard later edits to installed source files. Generated
application state, wallpaper memory and journals are retained; removal is not
an application/profile data purge.

Installer records: `~/.local/state/oma-theme/project-largo-install/`.
Initial cursor/icon choices: `~/.local/state/oma-theme/appearance-install.json`.
