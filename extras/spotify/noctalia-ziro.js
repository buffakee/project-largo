// User-owned colour overlay. Marketplace continues to own Ziro's layout/schemes.
// The matching Noctalia template publishes this asset via `spicetify refresh`.
(() => {
  if (window.__noctaliaZiro) return;
  const state = window.__noctaliaZiro = { lastError: null, updates: 0 };
  const keys = ["text", "subtext", "main", "sidebar", "player", "card", "shadow",
    "selected-row", "button", "button-active", "button-disabled", "tab-active",
    "notification", "notification-error", "misc"];
  const style = document.createElement("style");
  style.id = "noctalia-ziro-colors";
  let previous = "";

  async function update() {
    try {
      // Marketplace sets this runtime name after loading its selected theme.
      // The on-disk current_theme remains "marketplace".
      if (window.Spicetify?.Config?.current_theme?.toLowerCase() !== "ziro") {
        style.remove();
        return;
      }
      const response = await fetch(`noctalia-ziro.json?t=${Date.now()}`, {
        cache: "no-store", signal: AbortSignal.timeout(5000)
      });
      if (!response.ok) throw new Error(`Palette HTTP ${response.status}`);
      const colors = await response.json();
      if (!keys.every(key => /^#[0-9a-f]{6}$/i.test(colors[key]))) {
        throw new Error("Invalid Noctalia palette; retaining last valid colours");
      }
      const css = ":root {\n" + keys.map(key => {
        const hex = colors[key];
        const rgb = hex.slice(1).match(/../g).map(part => parseInt(part, 16)).join(", ");
        return `--spice-${key}: ${hex} !important;\n--spice-rgb-${key}: ${rgb} !important;`;
      }).join("\n") + "\n}";
      if (css !== previous) {
        style.textContent = css;
        previous = css;
        state.updates++;
      }
      if (!style.isConnected) document.head.appendChild(style);
      state.lastError = null;
    } catch (error) {
      const message = String(error);
      if (state.lastError !== message) console.warn("Noctalia Ziro:", message);
      state.lastError = message;
    } finally {
      setTimeout(update, 2000);
    }
  }
  update();
})();
