import { apiGet } from "./api.js";
import { loadConfig } from "./config.js";
import {
  applyTheme,
  ensureEditor,
  focusProfiledRange,
  loadFile,
  renderCode,
} from "./editor.js";
import { ensureTreePathExpanded, renderTree } from "./explorer.js";
import { buildProfiledRanges } from "./ranges.js";
import { renderProfiledList, updateProfileNavUI } from "./profiled-ui.js";
import { app, bindUi, ui } from "./state.js";
import { readUrlState, updateUrlState } from "./url.js";

bindUi({
  metaEl: /** @type {HTMLElement} */ (document.getElementById("meta")),
  treeEl: /** @type {HTMLElement} */ (document.getElementById("tree")),
  fileTitleEl: /** @type {HTMLElement} */ (document.getElementById("fileTitle")),
  monacoEditorEl: /** @type {HTMLElement} */ (document.getElementById("monacoEditor")),
  hoverDetailsEl: /** @type {HTMLElement} */ (document.getElementById("hoverDetails")),
  copyDetailsBtnEl: /** @type {HTMLButtonElement} */ (document.getElementById("copyDetailsBtn")),
  argFilterEl: /** @type {HTMLSelectElement} */ (document.getElementById("argFilter")),
  scaleModeSelectEl: /** @type {HTMLSelectElement} */ (document.getElementById("scaleModeSelect")),
  reloadButtonEl: /** @type {HTMLButtonElement} */ (document.getElementById("reloadButton")),
  reportSelectEl: document.getElementById("reportSelect"),
  themeToggleEl: /** @type {HTMLInputElement} */ (document.getElementById("themeToggle")),
  prevProfiledBtnEl: /** @type {HTMLButtonElement} */ (document.getElementById("prevProfiledBtn")),
  nextProfiledBtnEl: /** @type {HTMLButtonElement} */ (document.getElementById("nextProfiledBtn")),
  profileNavStatusEl: /** @type {HTMLElement} */ (document.getElementById("profileNavStatus")),
  toggleMetaBtnEl: /** @type {HTMLButtonElement} */ (document.getElementById("toggleMetaBtn")),
  toggleDetailsBtnEl: /** @type {HTMLButtonElement} */ (document.getElementById("toggleDetailsBtn")),
  profiledSortSelectEl: /** @type {HTMLSelectElement} */ (document.getElementById("profiledSortSelect")),
  profiledListEl: /** @type {HTMLElement} */ (document.getElementById("profiledList")),
  bpfDisasmPreEl: document.getElementById("bpfDisasmPre"),
  bpfProgramDetailsEl: document.getElementById("bpfProgramDetails"),
});

if (!ui) {
  throw new Error("bindUi failed");
}

async function refreshAfterReportChange() {
  app.treeChildrenCache = {};
  await loadConfig();
  if (app.selectedPath) {
    await ensureTreePathExpanded(app.selectedPath);
    await renderTree();
  } else {
    await renderTree();
  }
  if (app.selectedPath) {
    await loadFile();
  }
  updateUrlState();
}

ui.reloadButtonEl.addEventListener("click", async () => {
  await apiGet("/api/reload");
  await refreshAfterReportChange();
});

if (ui.reportSelectEl) {
  ui.reportSelectEl.addEventListener("change", async () => {
    const id = ui.reportSelectEl.value;
    if (!id) {
      return;
    }
    await apiGet(`/api/reload?report=${encodeURIComponent(id)}`);
    await refreshAfterReportChange();
  });
}

ui.profiledSortSelectEl.addEventListener("change", async (event) => {
  app.profiledSortMode = ["line", "time", "calls"].includes(event.target.value)
    ? event.target.value
    : "line";
  if (!app.currentFileData) {
    renderProfiledList();
    return;
  }
  buildProfiledRanges(app.currentFileData);
  if (!app.profiledRanges.length) {
    if (app.editor) {
      app.focusedRangeDecorationIds = app.editor.deltaDecorations(app.focusedRangeDecorationIds, []);
    }
    updateProfileNavUI();
    return;
  }
  await focusProfiledRange(app.currentProfiledRangeIndex, false);
});

ui.argFilterEl.addEventListener("change", async (ev) => {
  app.selectedArg = ev.target.value;
  updateUrlState();
  if (app.selectedPath) {
    await loadFile();
  }
});

ui.scaleModeSelectEl.addEventListener("change", async (ev) => {
  app.selectedScaleMode = ev.target.value === "absolute" ? "absolute" : "profiled";
  updateUrlState();
  if (app.currentFileData) {
    await renderCode(app.currentFileData);
  }
});

ui.prevProfiledBtnEl.addEventListener("click", async () => {
  await focusProfiledRange(app.currentProfiledRangeIndex - 1, true);
});

ui.nextProfiledBtnEl.addEventListener("click", async () => {
  await focusProfiledRange(app.currentProfiledRangeIndex + 1, true);
});

ui.themeToggleEl.addEventListener("change", () => {
  app.selectedTheme = ui.themeToggleEl.checked ? "light" : "dark";
  applyTheme();
  updateUrlState();
});

ui.toggleMetaBtnEl.addEventListener("click", () => {
  document.body.classList.toggle("show-meta");
});

ui.toggleDetailsBtnEl.addEventListener("click", () => {
  document.body.classList.toggle("show-details");
});

ui.copyDetailsBtnEl.addEventListener("click", async () => {
  const text = ui.hoverDetailsEl.textContent || app.lastDetailsText || "";
  try {
    await navigator.clipboard.writeText(text);
    ui.copyDetailsBtnEl.textContent = "Copied!";
  } catch {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(ui.hoverDetailsEl);
    selection.removeAllRanges();
    selection.addRange(range);
    ui.copyDetailsBtnEl.textContent = "Selected";
  }
  setTimeout(() => {
    ui.copyDetailsBtnEl.textContent = "Copy details";
  }, 1200);
});

async function boot() {
  readUrlState();
  await ensureEditor();
  applyTheme();
  await loadConfig();

  const url = new URL(window.location.href);
  const urlReport = url.searchParams.get("report");
  if (urlReport && ui.reportSelectEl) {
    const ids = new Set([...ui.reportSelectEl.options].map((o) => o.value));
    if (ids.has(urlReport)) {
      ui.reportSelectEl.value = urlReport;
      await apiGet(`/api/reload?report=${encodeURIComponent(urlReport)}`);
      await loadConfig();
    }
  }

  if (app.selectedPath) {
    await ensureTreePathExpanded(app.selectedPath);
  }
  await renderTree();
  updateUrlState(true);
  updateProfileNavUI();
  if (app.selectedPath) {
    await loadFile();
  }
}

boot().catch((err) => {
  if (ui?.metaEl) {
    ui.metaEl.textContent = `Failed to initialize: ${err.message}`;
  }
});
