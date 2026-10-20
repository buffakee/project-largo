/* PDF-only Omarchy palette bridge. No synced settings or global reader prefs. */
var { classes: Cc, interfaces: Ci, utils: Cu } = Components;
var timer, stopped = true, busy = false;
var originals = new Map();
var themeID = 'custom-omarchy-local';
function restoreOriginals() {
  for (let [internal, saved] of originals) {
    try {
      internal.setLightTheme(saved.light);
      internal.setDarkTheme(saved.dark);
      internal.setCustomThemes(internal._state.customThemes.filter(x => x.id !== themeID));
    } catch (_) {}
  }
  originals.clear();
}
async function refresh() {
  if (stopped || busy) return;
  busy = true;
  try {
    let home = Services.dirsvc.get('Home', Ci.nsIFile).path;
    let text = await Zotero.File.getContentsAsync(home + '/.local/state/omarchy/current/theme/zotero-pdf-theme.json');
    let theme = JSON.parse(text);
    if (theme.enabled === false) {
      restoreOriginals();
      return;
    }
    if (!/^#[0-9a-f]{6}$/i.test(theme.background) || !/^#[0-9a-f]{6}$/i.test(theme.foreground)) return;
    theme = { id: themeID, label: 'Omarchy (automatic)', background: theme.background, foreground: theme.foreground, invertImages: false };
    if (stopped) return;
    const live = new Set();
    for (let reader of Zotero.Reader._readers) {
      if (reader.type !== 'pdf') continue;
      let internal = reader._internalReader;
      if (!internal?._state || !internal.setCustomThemes) continue;
      live.add(internal);
      try {
        let saved = originals.get(internal);
        if (!saved) {
          saved = { light: internal._state.lightTheme?.id, dark: internal._state.darkTheme?.id, signature: '' };
          originals.set(internal, saved);
        }
        let signature = JSON.stringify(theme);
        if (saved.signature === signature && internal._state.lightTheme?.id === themeID && internal._state.darkTheme?.id === themeID) continue;
        let themes = Array.from(internal._state.customThemes || []).filter(x => x.id !== themeID);
        themes.push(theme);
        internal.setCustomThemes(Cu.cloneInto(themes, reader._iframeWindow));
        internal.setLightTheme(themeID);
        internal.setDarkTheme(themeID);
        saved.signature = signature;
      } catch (e) { Zotero.logError(e); }
    }
    for (let internal of originals.keys()) if (!live.has(internal)) originals.delete(internal);
  } catch (e) {
    Zotero.debug('Omarchy PDF theme: ' + e);
  } finally { busy = false; }
}
function install() {}
function uninstall() {}
function startup() {
  stopped = false;
  timer = Cc['@mozilla.org/timer;1'].createInstance(Ci.nsITimer);
  timer.initWithCallback(() => { void refresh(); }, 2000, Ci.nsITimer.TYPE_REPEATING_SLACK);
  void refresh();
}
function shutdown() {
  stopped = true;
  timer?.cancel();
  timer = null;
  restoreOriginals();
}
