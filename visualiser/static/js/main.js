import { apiGet } from "./api.js";
import { loadConfig, refreshBpfDisasmHeatmap } from "./config.js";
import { initLoading, withLoading } from "./loading.js";
import {
  applyTheme,
  ensureEditor,
  focusProfiledRange,
  loadFile,
  renderCode,
} from "./editor.js";
import { ensureTreePathExpanded, renderTree } from "./explorer.js";
import { initResizableLayout } from "./layout.js";
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
  profiledDisplaySelectEl: /** @type {HTMLSelectElement} */ (document.getElementById("profiledDisplaySelect")),
  profiledListEl: /** @type {HTMLElement} */ (document.getElementById("profiledList")),
  bpfDisasmPreEl: document.getElementById("bpfDisasmPre"),
  bpfProgramDetailsEl: document.getElementById("bpfProgramDetails"),
  bpfInsnFileFilterEl: document.getElementById("bpfInsnFileFilter"),
  bpfInsnScaleSelectEl: document.getElementById("bpfInsnScaleSelect"),
});

if (!ui) {
  throw new Error("bindUi failed");
}

initLoading();
initResizableLayout();

async function refreshAfterReportChange(reportLabel) {
  const label = reportLabel || "Reloading report…";
  await withLoading("global", label, async () => {
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
  });
}

ui.reloadButtonEl.addEventListener("click", async () => {
  await apiGet("/api/reload");
  await refreshAfterReportChange("Reloading report…");
});

if (ui.reportSelectEl) {
  ui.reportSelectEl.addEventListener("change", async () => {
    const id = ui.reportSelectEl.value;
    if (!id) {
      return;
    }
    await apiGet(`/api/reload?report=${encodeURIComponent(id)}`);
    await refreshAfterReportChange(`Loading report ${id}…`);
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

ui.profiledDisplaySelectEl.addEventListener("change", async (event) => {
  app.profiledListDisplayMode = event.target.value === "tree" ? "tree" : "flat";
  updateUrlState();
  app.profiledTreeExpanded = {};
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
  refreshBpfDisasmHeatmap();
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

if (ui.bpfInsnFileFilterEl) {
  ui.bpfInsnFileFilterEl.addEventListener("change", (ev) => {
    app.bpfInsnFileFilter = ev.target.value || "all";
    updateUrlState();
    refreshBpfDisasmHeatmap();
  });
}

if (ui.bpfInsnScaleSelectEl) {
  ui.bpfInsnScaleSelectEl.addEventListener("change", (ev) => {
    app.bpfInsnScaleMode = ev.target.value === "absolute" ? "absolute" : "profiled";
    updateUrlState();
    refreshBpfDisasmHeatmap();
  });
}

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
  await withLoading("global", "Loading editor…", () => ensureEditor());
  applyTheme();

  await withLoading("global", "Loading report…", async () => {
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
    if (ui.profiledDisplaySelectEl) {
      ui.profiledDisplaySelectEl.value = app.profiledListDisplayMode;
    }
  });
}

boot().catch((err) => {
  if (ui?.metaEl) {
    ui.metaEl.textContent = `Failed to initialize: ${err.message}`;
  }
});
