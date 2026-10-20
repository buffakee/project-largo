/* Adapted from the Omarchy handoff; edit this source template. */
:root {
  --om-bg: {{ background }};
  --om-fg: {{ foreground }};
  --om-accent: {{ accent }};
  --om-hover: {{ hover }};
  --om-border: {{ outline_variant }};
  --om-selected: {{ soft_selection }};
  --om-selected-fg: {{ on_soft_selection }};
  --om-on-accent: {{ on_accent }};
  --lwt-accent-color: var(--om-bg) !important;
  --lwt-text-color: var(--om-fg) !important;
  --lwt-header-image: none !important;
  --lwt-additional-images: none !important;
  --toolbar-bgcolor: var(--om-bg) !important;
  --toolbar-color: var(--om-fg) !important;
  --toolbar-field-background-color: var(--om-hover) !important;
  --toolbar-field-color: var(--om-fg) !important;
  --toolbar-field-border-color: var(--om-border) !important;
  --toolbar-field-focus-background-color: var(--om-bg) !important;
  --toolbar-field-focus-color: var(--om-fg) !important;
  --toolbar-field-focus-border-color: var(--om-accent) !important;
  --toolbarbutton-icon-fill: var(--om-fg) !important;
  --toolbarbutton-hover-background: var(--om-hover) !important;
  --toolbarbutton-active-background: var(--om-selected) !important;
  --toolbarseparator-color: var(--om-border) !important;
  --tab-selected-bgcolor: var(--om-selected) !important;
  --tab-selected-textcolor: var(--om-selected-fg) !important;
  --tab-loading-fill: var(--om-accent) !important;
  --lwt-tab-line-color: var(--om-accent) !important;
  --lwt-tab-text: var(--om-fg) !important;
  --lwt-tabs-border-color: var(--om-border) !important;
  --arrowpanel-background: var(--om-bg) !important;
  --arrowpanel-color: var(--om-fg) !important;
  --arrowpanel-border-color: var(--om-border) !important;
  --arrowpanel-dimmed: var(--om-hover) !important;
  --arrowpanel-dimmed-further: var(--om-selected) !important;
  --sidebar-background-color: var(--om-bg) !important;
  --sidebar-text-color: var(--om-fg) !important;
  --sidebar-border-color: var(--om-border) !important;
  --sidebar-hover-background-color: var(--om-hover) !important;
  --sidebar-selected-background-color: var(--om-selected) !important;
  --lwt-sidebar-background-color: var(--om-bg) !important;
  --lwt-sidebar-text-color: var(--om-fg) !important;
  --lwt-sidebar-border-color: var(--om-border) !important;
  --urlbarView-highlight-background: var(--om-selected) !important;
  --urlbarView-highlight-color: var(--om-selected-fg) !important;
  --urlbarView-hover-background: var(--om-hover) !important;
  --urlbarView-action-color: var(--om-accent) !important;
  --urlbarView-url-color: var(--om-accent) !important;
  --focus-outline-color: var(--om-accent) !important;
  --color-accent-primary: var(--om-accent) !important;
  --color-accent-primary-hover: var(--om-accent) !important;
  --color-accent-primary-active: var(--om-accent) !important;
  --color-accent-primary-contrast: var(--om-on-accent) !important;
  --background-color-canvas: var(--om-bg) !important;
  --background-color-box: var(--om-bg) !important;
  --background-color-menu: var(--om-bg) !important;
  --background-color-button: var(--om-hover) !important;
  --background-color-button-hover: var(--om-selected) !important;
  --text-color: var(--om-fg) !important;
  --text-color-deemphasized: {{ muted }} !important;
  --border-color: var(--om-border) !important;
}
#main-window, #navigator-toolbox, #TabsToolbar, #nav-bar,
#PersonalToolbar, #toolbar-menubar, #sidebar-box, #sidebar-main,
#sidebar-header, #sidebar, #browser, #statuspanel-label, .browserContainer > findbar {
  background-color: var(--om-bg) !important;
  color: var(--om-fg) !important;
  border-color: var(--om-border) !important;
}
#navigator-toolbox { background-image: none !important; }
.tabbrowser-tab { color: var(--om-fg) !important; }
.tab-background[selected], .tab-background[multiselected] {
  background: var(--om-selected) !important;
  box-shadow: inset 0 2px var(--om-accent) !important;
}
.tabbrowser-tab:hover:not([selected]) .tab-background {
  background-color: var(--om-hover) !important;
}
#urlbar-background, #searchbar {
  background: var(--om-hover) !important;
  border-color: var(--om-border) !important;
}
/* Focused URL bar and selected URL text use the active Omarchy palette. */
#urlbar[focused] > #urlbar-background {
  background: var(--om-bg) !important;
  border-color: var(--om-accent) !important;
}
#urlbar-input {
  caret-color: var(--om-accent) !important;
}
#urlbar-input::selection {
  background-color: var(--om-accent) !important;
  color: var(--om-on-accent) !important;
}
#urlbar-input, #searchbar { color: var(--om-fg) !important; }
menupopup, panel {
  --panel-background: var(--om-bg) !important;
  --panel-color: var(--om-fg) !important;
  --panel-border-color: var(--om-border) !important;
  --panel-separator-color: var(--om-border) !important;
  --menu-background-color: var(--om-bg) !important;
  --menu-color: var(--om-fg) !important;
  --menu-border-color: var(--om-border) !important;
  --menuitem-hover-background-color: var(--om-hover) !important;
  --menuitem-disabled-hover-background-color: var(--om-hover) !important;
  --menuitem-hover-color: var(--om-fg) !important;
}
menupopup, tooltip {
  appearance: none !important;
  background-color: var(--om-bg) !important;
  color: var(--om-fg) !important;
  border-color: var(--om-border) !important;
}
menu[_moz-menuactive="true"], menuitem[_moz-menuactive="true"] {
  background-color: var(--om-hover) !important;
  color: {{ on_hover }} !important;
}
/* Built-in bookmark/history sidebar documents are chrome, not webpages. */
@-moz-document url("chrome://browser/content/places/bookmarksSidebar.xhtml"),
                url("chrome://browser/content/places/historySidebar.xhtml"),
                url("chrome://browser/content/sidebar/sidebar-history.html") {
  :root, body, tree {
    background-color: var(--om-bg) !important;
    color: var(--om-fg) !important;
  }
  treechildren::-moz-tree-row(selected) { background-color: var(--om-selected) !important; }
  treechildren::-moz-tree-cell-text(selected) { color: var(--om-selected-fg) !important; }
}
