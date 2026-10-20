# First-run application integrations

Apply a preset, then use **Set up / Refresh integrations** in the GTK picker.
The current **applied** preset is used, not a different highlighted picker row.
For a completely new installation, apply a preset before application setup.
Close applications before enrolling their profiles. Missing optional applications
are successful skips; they are not installed by Largo.

Every operation discovers installed native/Flatpak applications and registered
profiles/vaults again. Old profile directories alone do not prove an application
is installed. After installing an app or adding a profile, run setup again.
Setup and repair share the same idempotent verification/transaction backend.

## Commands

```bash
project-largo integrations status
project-largo integrations status --json
project-largo integrations setup --dry-run
project-largo integrations setup
project-largo integrations setup --app zen
project-largo integrations repair --app libreoffice --json
project-largo integrations restore OPERATION
project-largo integrations admin-setup gdm
project-largo integrations admin-restore ADMIN_OPERATION
```

`--app` accepts `libreoffice`, `zen`, `obsidian`, `zotero`, or `gdm`. Status does
not write integration state or application profiles and never invokes unopkg.
Dry-run inspects current hooks without changing configuration. Setup/repair
render the current preset using the native Noctalia backend and apply only the
maintained app artifacts; they do not reset GNOME settings, cursor/icon choices
or wallpaper memory. Mutating CLI operations serialize with palette application.

Exit codes: **0** means no failure/blocking setup action (including missing apps
and reopening notices), **1** means failure, **2** means user/administrator action
is required. JSON retains every individual outcome even when another app fails.

## Status meanings

| State | Meaning |
| --- | --- |
| Ready | The adapter verified its owned configuration and generated assets. GDM also requires the queued request to match the root publication. This does not prove visual appearance. |
| Not installed | Optional application/backend is absent; skipped successfully. |
| Setup needed | Missing/outdated hooks, missing generated artifacts, a disabled Zotero bridge, or a queued GDM publication not yet verified. Details identify the next action. |
| Open app once | The app is installed but no usable registered profile/vault/workspace exists. Open it, finish its initial setup, close it, and retry. |
| Restart required | Startup-loaded files changed or Zotero has not activated its installed bridge. Fully quit/reopen the app. |
| Close app and retry | A process/profile lock prevents safe profile or extension work. Close the app and retry setup or ordinary palette application. |
| Administrator setup required | Optional GDM system setup or a required native LibreOffice GTK3 package needs administrator action. |
| Failed | Discovery, parsing, command execution, verification or recovery failed. Other targets continue; details and retained operation IDs identify recovery. |

Process checks are conservative across profiles of the same application. Active
profile locks also block edits. Largo never deletes a lock to force access.
Restart notices are conservative: a fresh process after publication plus unchanged
verified hooks can establish readiness while running; a closed application may
still show a reopening notice when no launch observation is available. Zotero
add-on activation is checked separately. Changes to a shared/symlinked profile
configuration require review instead of writing through that link.

## Maintained adapters

### LibreOffice: native and Flatpak

Native unopkg is discovered on PATH or in supported `/usr/lib*` and TDF `/opt`
layouts. Flatpak discovery queries the actual sandbox, including Fedora's
`/app/bin/unopkg`; it does not assume the upstream `/app/libreoffice` layout.
Sandbox configuration/data locations are queried from its XDG environment.
The extension archive is staged inside the sandbox's own data directory, without
adding permanent filesystem permissions or a global Flatpak environment override.

Initialized versioned profiles under native `~/.config/libreoffice` and Flatpak
`~/.var/app/org.libreoffice.LibreOffice/config/libreoffice` are supported. Arbitrary
custom `UserInstallation` directories are not searched. No initialized profile
is manufactured. Native GTK3 plugin availability and sandbox GTK3 support are
checked; Fedora's native package is `libreoffice-gtk3`.

The color extension is installed while closed. Readiness checks include its
identity, deployed color XML, package mapping and bundle/configuration backend
registration. A zero exit status alone is insufficient. Native and Flatpak
outcomes are independent, and failed/deferred work is retried rather than cached
as success. Extension-manager storage and affected settings are backed up before
commands run; a failed install restores them when safe.

Existing supported desktop IDs, MIME types, actions and original command arguments
are retained in user overrides. A generated launcher selects the GTK3 route,
uses the native color route in Vanilla, and retries deferred extension work before
launching. Existing running LibreOffice instances keep their backend until fully
closed. Direct shell invocations bypass this desktop-launcher environment.

### Zen: native and Flatpak

Only profiles registered in `profiles.ini` under native `~/.zen`,
`~/.config/zen`, or Flatpak `~/.var/app/app.zen_browser.zen/.zen` are enrolled.
Startup preferences, chrome/content imports and profile-local generated CSS are
managed without duplicates. Known legacy shared imports are adopted.

The supported native `zen-sessions.jsonlz4` spaces format is decoded with system
liblz4 while closed and profile-locked. Only each space's gradient type/color
references are changed; native opacity, texture, angle and all non-theme session
data are preserved. The existing approved primary/surface-variant/surface slots
remain in use. Unsupported schemas fail before profile changes. Restoration
matches workspace IDs and preserves later tabs and other session data.

New spaces/profiles are discovered on later setup; ordinary application also
rechecks enrolled closed profiles. CSS loaded at startup requires reopening.

### Obsidian: registered native/Flatpak vaults

Only the native/Flatpak `obsidian.json` registries and each registered vault's
`.obsidian/appearance.json` and `.obsidian/snippets/noctalia.css` are accessed.
Vault contents and personal notes are never traversed, read or modified.
Other snippet entries, themes and settings are retained. Vanilla suspends the
snippet and stock-appearance overrides reversibly, preserving unrelated later
JSON edits. When running, only the already-enrolled generated CSS is updated;
appearance settings wait until closed.

### Native Zotero

Registered profiles under `~/.zotero/zotero` or `~/.zotero` receive UI imports,
the stylesheet-loading preference and the existing local PDF bridge as an XPI.
The package retains the existing `omarchy-pdf-theme@local` ID and is versioned
1.0.4. It targets Zotero 7–9 and uses the existing private reader API bridge;
future Zotero versions require compatibility review. A newer bridge is preserved
for review rather than downgraded. Other add-ons are untouched. Zotero-owned
extension-manager records are inspected for activation, not edited to force it.

Reopen Zotero and enable the bridge in its plugin manager if reported disabled.
The bridge reads generated palette data and does not alter synced reader
preferences, attachments or document content. Vanilla disables its override.
**Zotero Flatpak is explicitly outside maintained scope** and is never enrolled.

### GDM: separate administrator setup

The GTK **Set up GDM (Administrator…)** control and `admin-setup gdm` invoke
Polkit authentication. The reviewed installer is first copied to a root-owned,
hash-verified location; root runtime code never imports code from a user's home.
The publisher consumes bounded, owner-checked, data-only requests and images.
Wallpaper preparation uses the user-side `python3-pillow` package; Polkit/pkexec
is needed for the separate administrator action.

Setup installs an account binding, root-owned publisher, system path/service and
an `org.gnome.Shell@gdm.service`-only resource override. The existing local
implementation can be migrated: original units/overrides and resource pointer
are backed up. The GDM user manager is daemon-reloaded if present; **neither GDM
nor the current desktop session is restarted**. New resources take effect when
a new greeter Shell actually starts. A currently running greeter can retain its
old resources. Custom styling targets GNOME Shell 50; a future major falls back
to stock resources. Both Vanilla presets use exact stock stylesheets.

Once enrolled, successful explicit GNOME palette application queues GDM data.
Automatic GNOME/Niri startup restoration does not overwrite the last explicit
choice. A native Noctalia/Niri greeter watcher is not installed automatically;
existing separately installed compatibility watchers remain separately owned.

GDM status checks system-file contents/ownership, account binding, units and the
exact request fingerprint of the published generation. Publication is asynchronous
after a palette switch; refresh status after the system job finishes. Authentication
can require separate prompts for the trusted copy and installation commands.

Administrator operation IDs are printed by setup. Restore with
`project-largo integrations admin-restore ADMIN_OPERATION`. The root-owned
recovery helper also works independently:

```bash
sudo /usr/bin/python3 -I /usr/local/libexec/project-largo-gdm restore ADMIN_OPERATION
```

Failed administrator setup prints the retained root-owned recovery command.
Root backups are under `/var/lib/project-largo-gdm-backup/`. Recovery copies and
resource generations are retained rather than pruning a potentially needed
baseline. System restoration preserves later user palette/queue choices; the
separate user queue operation can be restored explicitly if appropriate.

## Backups and restoration

Enrollment and results live under `~/.local/state/project-largo/integrations/`,
independently of Noctalia settings. Per-operation directories are private and
contain the before/after data and manifest. No credentials or notes are copied.
Browser session backups can contain private session state, so keep these private.

Every changed target reports an operation ID. Restore operations newest-first;
restoring one update returns the previous enrollment record, whose operation can
then be restored. Shared JSON/scheme fields and Zen workspace themes are restored
semantically so unrelated later settings/tabs survive. Text imports use a
three-way merge. Conflicts in owned fields, CSS, extensions or manager storage
stop restoration and retain backups rather than discarding later changes.

If an app starts during a transaction, automatic rollback also defers rather than
writing into a live profile. Close it and use the retained recovery operation.
Review interrupted operations' manifests before recovery. Source uninstall is
not a profile-data purge or an automatic reversal of the adapter journal; keep
the checkout and restore desired integration operations before removing sources.

## Renderer boundary and verification scope

`Palette → Renderer → generated artifacts → application adapters` is the Largo
boundary. `NoctaliaRenderer` remains the implementation for this milestone.
Integration enrollment does not depend on Noctalia user settings. Optional legacy
template selection is Largo-owned in
`~/.config/project-largo/integrations.json` (`templates` is a list of existing
optional built-in template IDs); Niri selection and historical wallpaper pairings
remain optional compatibility inputs.

The unit suite uses synthetic native/Flatpak profiles and command fixtures for
enrollment and recovery. `tools/check-picker.py` exercises GTK on a disposable
Broadway display. `tools/check-gdm.py` parses all palette resources without
installing system files. These checks do not establish real sandbox extension
activation, clean-VM interactive application visuals, or actual GDM login behavior.
