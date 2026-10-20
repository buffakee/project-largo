/* Adapted from the Omarchy handoff; edit this source template. */
@-moz-document url("chrome://zotero/content/zoteroPane.xhtml"),
               url("chrome://zotero/content/standalone/standalone.xhtml"),
               url("chrome://zotero/content/reader.xhtml"),
               url("resource://zotero/reader/reader.html") {
  :root {
    --om-background: {{ background }};
    --om-foreground: {{ foreground }};
    --om-accent: {{ accent }};
    --om-selection-background: {{ selection_background }};
    --om-selection-foreground: {{ selection_foreground }};
    --om-error: {{ error }};
    --om-muted: {{ muted }};
    --fill-primary: var(--om-foreground) !important;
    --fill-secondary: {{ muted }} !important;
    --fill-tertiary: {{ muted }} !important;
    --fill-quarternary: {{ mix background foreground 15% }} !important;
    --fill-quinary: {{ mix background foreground 8% }} !important;
    --fill-senary: {{ mix background foreground 3% }} !important;
    --color-background: var(--om-background) !important;
    --color-background30: var(--om-background) !important;
    --color-background50: var(--om-background) !important;
    --color-background70: var(--om-background) !important;
    --color-button: {{ lighter_background }} !important;
    --color-control: var(--om-background) !important;
    --color-menu: var(--om-background) !important;
    --color-menu-opaque: var(--om-background) !important;
    --color-sidepane: {{ lighter_background }} !important;
    --color-tabbar: var(--om-background) !important;
    --color-toolbar: {{ lighter_background }} !important;
    --color-border: {{ outline }} !important;
    --color-border50: {{ outline_variant }} !important;
    --color-panedivider: {{ outline_variant }} !important;
    --color-stripe: {{ mix background foreground 3% }} !important;
    --color-stripe-on-background: {{ mix background foreground 3% }} !important;
    --color-quinary-on-background: {{ hover }} !important;
    --color-quarternary-on-background: {{ hover }} !important;
    --color-quinary-on-sidepane: {{ hover }} !important;
    --color-quarternary-on-sidepane: var(--om-selection-background) !important;
    --color-accent: var(--om-accent) !important;
    --color-accent-text: {{ on_accent }} !important;
    --accent-blue: var(--om-accent) !important;
    --accent-blue10: rgba({{ accent_rgb }}, .1) !important;
    --accent-blue30: rgba({{ accent_rgb }}, .3) !important;
    --accent-blue50: rgba({{ accent_rgb }}, .5) !important;
    --color-scrollbar: var(--om-muted) !important;
    --color-scrollbar-hover: var(--om-accent) !important;
    --color-scrollbar-background: var(--om-background) !important;
    --color-invalid: var(--om-error) !important;
    --color-invalid-background: {{ mix background error 12% }} !important;
    --material-background: var(--color-background) !important;
    --material-background50: var(--color-background50) !important;
    --material-background70: var(--color-background70) !important;
    --material-button: var(--color-button) !important;
    --material-control: var(--color-control) !important;
    --material-menu: var(--color-menu) !important;
    --material-sidepane: var(--color-sidepane) !important;
    --material-tabbar: var(--color-tabbar) !important;
    --material-toolbar: var(--color-toolbar) !important;
    --material-stripe: var(--color-stripe-on-background) !important;
    --material-border: 1px solid var(--color-border) !important;
    --material-border50: 1px solid var(--color-border50) !important;
    --material-panedivider: 1px solid var(--color-panedivider) !important;
    --material-mix-quinary: var(--color-quinary-on-background) !important;
    --material-mix-quarternary: var(--color-quarternary-on-background) !important;
    color: var(--om-foreground) !important;
    background-color: var(--om-background) !important;
  }
  #zotero-pane, #zotero-items-tree, #zotero-item-pane,
  #zotero-item-pane-content, #zotero-tag-selector {
    background-color: var(--om-background) !important;
    color: var(--om-foreground) !important;
  }
  #zotero-collections-pane, #zotero-collections-tree, #zotero-context-pane {
    background-color: var(--color-sidepane) !important;
    color: var(--om-foreground) !important;
  }
  #titlebar, #tab-bar-container, #tabs-bar, #zotero-toolbar, toolbar, menubar,
  .virtualized-table-header {
    background-color: var(--color-toolbar) !important;
    color: var(--om-foreground) !important;
    border-color: var(--color-border) !important;
  }
  .tab { color: var(--om-foreground) !important; }
  .tab.selected, .tab[aria-selected="true"] {
    background: {{ soft_selection }} !important;
    color: {{ on_soft_selection }} !important;
    box-shadow: inset 0 -2px var(--om-accent) !important;
  }
  :is(#zotero-items-tree, #zotero-collections-tree) .row:not(.selected) {
    color: var(--om-foreground) !important;
  }
  :is(#zotero-items-tree, #zotero-collections-tree) .row:not(.selected):hover,
  toolbarbutton:not([disabled="true"]):hover {
    background-color: var(--color-quinary-on-background) !important;
  }
  .virtualized-table .row.selected,
  .virtualized-table:not(:focus-within) .row.selected,
  #zotero-tabs-menu-list .row.selected {
    background-color: var(--om-selection-background) !important;
    color: var(--om-selection-foreground) !important;
  }
  .virtualized-table:focus-within .row.selected {
    box-shadow: inset 2px 0 var(--om-accent) !important;
  }
  .virtualized-table .row.selected .cell,
  .virtualized-table .row.selected .twisty {
    color: var(--om-selection-foreground) !important;
    fill: var(--om-selection-foreground) !important;
  }
  splitter { background-color: var(--color-panedivider) !important; border-color: var(--color-border) !important; }
  menupopup, panel {
    --panel-background: var(--om-background) !important;
    --panel-color: var(--om-foreground) !important;
    --panel-border-color: var(--color-border) !important;
    background-color: var(--om-background) !important;
    color: var(--om-foreground) !important;
  }
  menuitem[_moz-menuactive="true"], menu[_moz-menuactive="true"] {
    background-color: var(--om-selection-background) !important;
    color: var(--om-selection-foreground) !important;
  }
  #zotero-pane :is(input, textarea, textbox, menulist) {
    background-color: var(--om-background) !important;
    color: var(--om-foreground) !important;
    border-color: var(--color-border) !important;
    accent-color: var(--om-accent);
  }
  #zotero-pane :is(input, textarea, textbox):focus-visible {
    outline-color: var(--om-accent) !important;
  }
}

/* Reader UI lives in its own document: share the semantic controls above,
   then give its toolbar/sidebar the same surface as the PDF surround. */
@-moz-document url("resource://zotero/reader/reader.html") {
  :root {
    --color-toolbar: {{ lighter_background }} !important;
    --color-sidepane: {{ lighter_background }} !important;
    --color-menu: {{ lighter_background }} !important;
    --color-button50: {{ lighter_background }} !important;
    --color-focus-border: {{ accent }} !important;
  }
  body { color: var(--fill-primary) !important; }
  #reader-ui :is(input, textarea, select) {
    accent-color: var(--accent-blue);
  }
  #reader-ui :is(input, textarea)::selection {
    background-color: {{ selection_background }};
    color: {{ selection_foreground }};
  }
}

/* The PDF.js viewport is a second embedded document. Only theme the surround:
   the PDF plugin owns page/canvas colors (surface), with images preserved.
   Noctalia surface-container provides subtle separation in both palette modes. */
@-moz-document url("resource://zotero/reader/pdf/web/viewer.html") {
  @media screen {
    :root, body, #viewerContainer {
      background-color: {{ lighter_background }} !important;
      scrollbar-color: {{ outline }} {{ lighter_background }};
    }
    .pdfViewer .page {
      box-shadow: 0 0 0 1px {{ outline_variant }},
                  0 2px 5px rgba(0, 0, 0, .18) !important;
    }
  }
}
