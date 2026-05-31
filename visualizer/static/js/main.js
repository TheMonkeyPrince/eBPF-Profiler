import { fetchReportCatalog, fetchReport, parseReportFile } from "./api.js";
import {
  formatDurationNs,
  formatCount,
  parseSiteKey,
  collectSiteLocations,
  collectSiteLineIndex,
  pickSiteAtLine,
} from "./format.js";
import { renderSiteTree, renderSiteDetail } from "./tree.js";
import { renderInsnTable } from "./insn-table.js";
import { renderProgramInsnChart } from "./insn-chart.js";
import { createSourceEditor } from "./editor.js";
import { renderChildrenChart } from "./children-chart.js";

const PERCENT_SCALE_KEY = "visualizer-percent-scale";

const els = {
  reportSelect: document.getElementById("report-select"),
  fileInput: document.getElementById("file-input"),
  reloadBtn: document.getElementById("reload-btn"),
  clearSelectionBtn: document.getElementById("clear-selection-btn"),
  percentScale: document.getElementById("percent-scale"),
  status: document.getElementById("status"),
  programName: document.getElementById("program-name"),
  overviewStats: document.getElementById("overview-stats"),
  siteTree: document.getElementById("site-tree"),
  childrenChart: document.getElementById("children-chart"),
  childrenChartTitle: document.getElementById("children-chart-title"),
  siteDetail: document.getElementById("site-detail"),
  insnGroup: document.getElementById("insn-group"),
  insnChart: document.getElementById("insn-chart"),
  insnTable: document.getElementById("insn-table"),
  monacoContainer: document.getElementById("monaco-container"),
  sourcePath: document.getElementById("source-path"),
  sourceStatus: document.getElementById("source-status"),
};

let currentReport = null;
/** @type {{ setPercentScale: (scale: 'total' | 'parent') => void, selectSite: (key: string, opts?: object) => void, clearSelection: () => void } | null} */
let siteTreeController = null;
/** @type {Map<string, Map<number, { key: string, node: object, depth: number }[]>> | null} */
let siteLineIndex = null;
/** @type {{ key: string, node: object } | null} */
let selectedSite = null;
/** @type {{ openAt: (file: string, line: string|number, symbol?: string, endLine?: string|number) => Promise<void>, setSiteIndex: (m: Map<string, Set<number>>) => void, highlightSelection: (file: string, lineNumber: number, symbol?: string, endLineNumber?: number) => void, clearSelection: () => void } | null} */
let sourceEditor = null;
/** @type {Map<string, Set<number>> | null} */
let pendingSiteIndex = null;

function applySiteIndexToEditor() {
  if (!pendingSiteIndex) return;
  sourceEditor?.setSiteIndex(pendingSiteIndex);
}

function syncClearSelectionButton() {
  if (els.clearSelectionBtn) {
    els.clearSelectionBtn.disabled = !selectedSite;
  }
}

function clearSiteSelection() {
  selectedSite = null;
  siteTreeController?.clearSelection();
  renderSiteDetail(els.siteDetail, "", null);
  updateChildrenChart();
  sourceEditor?.clearSelection();
  syncClearSelectionButton();
}

function updateChildrenChart() {
  const scale = getPercentScale();
  const scaleLabel = scale === "parent" ? "% of parent" : "% of total";
  const siteTree = currentReport?.stats?.site_tree ?? {};

  const chartOptions = {
    onSelect: (key, node) =>
      handleSiteSelect(key, node, { scrollTree: false }),
  };

  if (selectedSite) {
    const { symbol } = parseSiteKey(selectedSite.key);
    els.childrenChartTitle.textContent = `Children of ${symbol || selectedSite.key} (${scaleLabel})`;
    renderChildrenChart(
      els.childrenChart,
      selectedSite.key,
      selectedSite.node,
      scale,
      chartOptions
    );
    return;
  }

  els.childrenChartTitle.textContent = `Root sites (${scaleLabel})`;
  renderChildrenChart(
    els.childrenChart,
    "",
    { children: siteTree },
    scale,
    chartOptions
  );
}

function handleSiteSelect(key, node, { syncEditor = true, scrollTree = true } = {}) {
  selectedSite = { key, node };
  siteTreeController?.selectSite(key, { scroll: scrollTree });
  renderSiteDetail(els.siteDetail, key, node, getPercentScale());
  updateChildrenChart();
  syncClearSelectionButton();
  const { file, line, endLine, symbol } = parseSiteKey(key);
  const lineNum = Math.max(1, parseInt(String(line), 10) || 1);
  const endLineNum = Math.max(1, parseInt(String(endLine), 10) || lineNum);
  if (syncEditor) {
    sourceEditor?.openAt(file, line, symbol, endLine || line);
  } else {
    sourceEditor?.highlightSelection(file, lineNum, symbol, endLineNum);
  }
}

function onEditorCursorLine(file, line) {
  if (!siteLineIndex) return;
  const pick = pickSiteAtLine(siteLineIndex, file, line);
  if (!pick) return;
  if (selectedSite?.key === pick.key) {
    const { symbol, line: startLine, endLine } = parseSiteKey(pick.key);
    const start = Math.max(1, parseInt(String(startLine), 10) || line);
    const end = Math.max(1, parseInt(String(endLine), 10) || start);
    sourceEditor?.highlightSelection(file, start, symbol, end);
    return;
  }
  handleSiteSelect(pick.key, pick.node, { syncEditor: false, scrollTree: false });
}

createSourceEditor(els.monacoContainer, {
  pathLabel: els.sourcePath,
  statusLabel: els.sourceStatus,
  onCursorLine: onEditorCursorLine,
}).then((editor) => {
  sourceEditor = editor;
  applySiteIndexToEditor();
  if (selectedSite) {
    const { file, line, endLine, symbol } = parseSiteKey(selectedSite.key);
    editor.openAt(file, line, symbol, endLine || line);
  }
});

function loadPercentScale() {
  const stored = sessionStorage.getItem(PERCENT_SCALE_KEY);
  if (stored === "parent" || stored === "total") return stored;
  return "total";
}

function savePercentScale(scale) {
  sessionStorage.setItem(PERCENT_SCALE_KEY, scale);
}

function getPercentScale() {
  return /** @type {'total' | 'parent'} */ (els.percentScale?.value ?? "total");
}

els.percentScale.value = loadPercentScale();

els.percentScale.addEventListener("change", () => {
  const scale = getPercentScale();
  savePercentScale(scale);
  siteTreeController?.setPercentScale(scale);
  if (selectedSite) {
    renderSiteDetail(
      els.siteDetail,
      selectedSite.key,
      selectedSite.node,
      scale
    );
    updateChildrenChart();
  }
});

function setStatus(message, isError = false) {
  els.status.textContent = message;
  els.status.className = isError
    ? "text-sm text-rose-400"
    : "text-sm text-slate-500";
}

async function loadCatalog() {
  try {
    const catalog = await fetchReportCatalog();
    els.reportSelect.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent =
      catalog.length === 0
        ? "(no reports in analysis dir)"
        : "Select a report…";
    els.reportSelect.appendChild(placeholder);

    for (const entry of catalog) {
      const opt = document.createElement("option");
      opt.value = entry.id;
      let label = entry.label;
      if (entry.program_name) label += ` — ${entry.program_name}`;
      if (entry.verification_time) {
        label += ` (${formatDurationNs(entry.verification_time)})`;
      }
      opt.textContent = label;
      els.reportSelect.appendChild(opt);
    }
    setStatus(
      catalog.length
        ? `${catalog.length} report(s) in analysis directory`
        : "No server reports — load a JSON file locally"
    );
  } catch (err) {
    setStatus(`Catalog unavailable (open via file upload): ${err.message}`, true);
  }
}

const VERIFIER_STAT_LABELS = {
  subprog_cnt: "Subprogs",
  insn_processed: "Insns",
  complexity_limit_insns: "Limit",
  max_states_per_insn: "Max/insn",
  total_states: "States",
  peak_states: "Peak",
  longest_mark_read_walk: "Mark read",
};

function appendStat(container, label, value, { muted = false } = {}) {
  const item = document.createElement("span");
  item.className = `inline-flex items-baseline gap-1 shrink-0${
    muted ? " text-slate-400" : ""
  }`;
  const lab = document.createElement("span");
  lab.className = "text-xs text-slate-500";
  lab.textContent = label;
  const val = document.createElement("span");
  val.className = "font-medium tabular-nums text-slate-200";
  val.textContent = value;
  item.append(lab, val);
  container.appendChild(item);
}

function renderOverview(report) {
  const stats = report.stats || {};
  const verStats = report.verification_stats || {};

  els.programName.textContent = report.program_name || "—";

  els.overviewStats.replaceChildren();

  appendStat(
    els.overviewStats,
    "Verify",
    formatDurationNs(stats.verification_time)
  );
  appendStat(
    els.overviewStats,
    "Program",
    `${formatCount(stats.program_length)} insns`
  );
  appendStat(els.overviewStats, "Trace", formatCount(stats.num_records));
  appendStat(els.overviewStats, "Sites", formatCount(stats.num_sites));
  appendStat(els.overviewStats, "Analysis", stats.analysis_time || "—");

  const verEntries = Object.entries(verStats);
  if (verEntries.length) {
    const divider = document.createElement("span");
    divider.className = "text-slate-600 select-none";
    divider.setAttribute("aria-hidden", "true");
    divider.textContent = "|";
    els.overviewStats.appendChild(divider);
  }
  for (const [key, value] of verEntries) {
    const label = VERIFIER_STAT_LABELS[key] || key.replace(/_/g, " ");
    const formatted =
      typeof value === "number" ? formatCount(value) : String(value);
    appendStat(els.overviewStats, label, formatted, { muted: true });
  }
}

function getInsnGroup() {
  return /** @type {'types' | 'class'} */ (els.insnGroup?.value ?? "types");
}

function renderInsnSection() {
  const group = getInsnGroup();
  const stats =
    group === "class"
      ? currentReport?.stats?.insn_classes
      : currentReport?.stats?.insn_types;
  const groupLabel =
    group === "class" ? "instruction class" : "instruction type";
  renderProgramInsnChart(els.insnChart, stats ?? {}, {
    ariaLabel: `Program ${groupLabel} mix by share of program length`,
  });
  renderInsnTable(els.insnTable, stats ?? {}, {
    emptyMessage:
      group === "class"
        ? "No instruction class data."
        : "No instruction type data.",
  });
}

function renderReport(report) {
  currentReport = report;
  const siteTree = report.stats?.site_tree ?? {};
  pendingSiteIndex = collectSiteLocations(siteTree);
  siteLineIndex = collectSiteLineIndex(siteTree);
  applySiteIndexToEditor();
  renderOverview(report);
  siteTreeController = renderSiteTree(
    els.siteTree,
    siteTree,
    (key, node) => handleSiteSelect(key, node),
    { percentScale: getPercentScale() }
  );
  renderInsnSection();
  selectedSite = null;
  renderSiteDetail(els.siteDetail, "", null);
  updateChildrenChart();
  syncClearSelectionButton();
  setStatus("Report loaded");
}

els.insnGroup?.addEventListener("change", () => {
  renderInsnSection();
});

els.clearSelectionBtn.addEventListener("click", clearSiteSelection);

async function loadReportById(id) {
  if (!id) return;
  setStatus("Loading…");
  try {
    const report = await fetchReport(id);
    renderReport(report);
  } catch (err) {
    setStatus(err.message, true);
  }
}

els.reportSelect.addEventListener("change", () => {
  loadReportById(els.reportSelect.value);
});

els.fileInput.addEventListener("change", async () => {
  const file = els.fileInput.files?.[0];
  if (!file) return;
  setStatus("Parsing file…");
  try {
    const report = await parseReportFile(file);
    els.reportSelect.value = "";
    renderReport(report);
    setStatus(`Loaded ${file.name}`);
  } catch (err) {
    setStatus(`Invalid JSON: ${err.message}`, true);
  }
});

els.reloadBtn.addEventListener("click", async () => {
  await loadCatalog();
  if (els.reportSelect.value) {
    await loadReportById(els.reportSelect.value);
  }
});

loadCatalog().then(() => {
  const first = els.reportSelect.querySelector('option[value]:not([value=""])');
  if (first) {
    els.reportSelect.value = first.value;
    loadReportById(first.value);
  }
});
