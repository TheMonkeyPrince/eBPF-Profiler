import { apiGet } from "./api.js";
import { formatNs, heatAlpha, heatBucket } from "./formatting.js";
import { app, ui } from "./state.js";

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function basename(path) {
  const parts = String(path).split("/");
  return parts[parts.length - 1] || path;
}

export function getActiveInsnTiming() {
  if (app.bpfInsnFileFilter === "all") {
    return app.insnTiming;
  }
  return app.insnTimingByFile[app.bpfInsnFileFilter] || {};
}

function bpfInsnScopeLabel() {
  if (app.bpfInsnFileFilter === "all") {
    return "all files";
  }
  return basename(app.bpfInsnFileFilter);
}

function computeInsnMaxNs(insnTiming) {
  let maxNs = 0;
  for (const value of Object.values(insnTiming || {})) {
    maxNs = Math.max(maxNs, Number(value) || 0);
  }
  return maxNs;
}

/** Color scale reference: hottest insn in scope maps to max heat. */
function computeInsnReferenceNs(insnTiming) {
  return Math.max(1, computeInsnMaxNs(insnTiming));
}

export function buildBpfInsnFileOptions(files) {
  const bpfInsnFileFilterEl = ui?.bpfInsnFileFilterEl;
  if (!bpfInsnFileFilterEl) {
    return;
  }
  const selected = app.bpfInsnFileFilter;
  bpfInsnFileFilterEl.innerHTML = "";
  const allOpt = document.createElement("option");
  allOpt.value = "all";
  allOpt.textContent = "all files";
  bpfInsnFileFilterEl.appendChild(allOpt);
  for (const path of files || []) {
    const opt = document.createElement("option");
    opt.value = path;
    opt.textContent = basename(path);
    opt.title = path;
    bpfInsnFileFilterEl.appendChild(opt);
  }
  const known = new Set(["all", ...(files || [])]);
  if (!known.has(selected)) {
    app.bpfInsnFileFilter =
      app.selectedPath && known.has(app.selectedPath) ? app.selectedPath : "all";
  }
  bpfInsnFileFilterEl.value = app.bpfInsnFileFilter;
}

function disasmLinesForInsns(insns) {
  if (typeof window.disasmBpfProgramLines === "function") {
    return window.disasmBpfProgramLines(insns);
  }
  if (typeof window.disasmBpfProgram === "function") {
    return window.disasmBpfProgram(insns).split("\n").map((text, pc) => ({ pc, text }));
  }
  return [];
}

function selectedInsnFilterValue() {
  const arg = app.selectedArg;
  if (arg === "all" || arg === "__no_arg__") {
    return null;
  }
  return String(arg);
}

/** @param {HTMLElement} preEl */
function bindBpfDisasmClicks(preEl) {
  if (preEl.dataset.clickBound === "1") {
    return;
  }
  preEl.dataset.clickBound = "1";
  preEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const line = target.closest(".bpf-disasm-line");
    if (!line || !line.classList.contains("bpf-disasm-has-timing")) {
      return;
    }
    const insn = line.dataset.insn;
    if (!insn) {
      return;
    }
    const argFilterEl = ui?.argFilterEl;
    if (!argFilterEl) {
      return;
    }
    const known = new Set([...argFilterEl.options].map((opt) => opt.value));
    if (!known.has(insn)) {
      return;
    }
    argFilterEl.value = insn;
    app.selectedArg = insn;
    argFilterEl.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function buildBpfDisasmHtml(insns, insnTiming) {
  const lines = disasmLinesForInsns(insns);
  if (!lines.length) {
    return "";
  }
  const maxInsnNs = computeInsnMaxNs(insnTiming);
  const referenceNs = computeInsnReferenceNs(insnTiming);
  const profiledInsnTotal = Object.values(insnTiming).reduce((acc, v) => acc + Number(v || 0), 0);
  const selectedInsn = selectedInsnFilterValue();
  const scope = bpfInsnScopeLabel();
  const parts = [];
  for (const { pc, text } of lines) {
    const key = String(pc);
    const totalNs = Number(insnTiming[key] || 0);
    const alpha = heatAlpha(totalNs, referenceNs);
    const bucket = heatBucket(alpha);
    const classes = ["bpf-disasm-line"];
    if (bucket) {
      classes.push(`heat-line-${bucket}`);
    }
    if (totalNs > 0) {
      classes.push("bpf-disasm-has-timing");
    }
    if (selectedInsn !== null && key === selectedInsn) {
      classes.push("bpf-disasm-selected");
    }
    const shareOfHottest = maxInsnNs ? (100 * totalNs) / maxInsnNs : 0;
    const shareOfInsnTotal = profiledInsnTotal ? (100 * totalNs) / profiledInsnTotal : 0;
    const title =
      totalNs > 0
        ? `insn ${pc} | ${scope} | total: ${formatNs(totalNs)} | ${shareOfHottest.toFixed(1)}% of hottest insn (${formatNs(maxInsnNs)}) | ${shareOfInsnTotal.toFixed(1)}% of insn time in scope`
        : `insn ${pc} | ${scope} | (no insn-indexed samples)`;
    parts.push(
      `<span class="${classes.join(" ")}" data-insn="${escapeHtml(key)}" title="${escapeHtml(title)}">${escapeHtml(text)}</span>`,
    );
  }
  return parts.join("");
}

export function refreshBpfDisasmHeatmap() {
  const bpfDisasmPreEl = ui?.bpfDisasmPreEl;
  if (!bpfDisasmPreEl || !Array.isArray(app.bpfDisasmInsns) || !app.bpfDisasmInsns.length) {
    return;
  }
  const insnTiming = getActiveInsnTiming();
  bpfDisasmPreEl.innerHTML = buildBpfDisasmHtml(app.bpfDisasmInsns, insnTiming);
  bindBpfDisasmClicks(bpfDisasmPreEl);
  scrollSelectedInsnIntoView(bpfDisasmPreEl);
}

function scrollSelectedInsnIntoView(preEl) {
  const selectedInsn = selectedInsnFilterValue();
  if (!selectedInsn) {
    return;
  }
  const line = preEl.querySelector(`.bpf-disasm-line[data-insn="${CSS.escape(selectedInsn)}"]`);
  line?.scrollIntoView({ block: "nearest" });
}

export function buildArgOptions(globalArgs) {
  const argFilterEl = ui?.argFilterEl;
  if (!argFilterEl) {
    return;
  }
  argFilterEl.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = "all";
  allOption.dataset.baseLabel = "all";
  argFilterEl.appendChild(allOption);

  const noArgOption = document.createElement("option");
  noArgOption.value = "__no_arg__";
  noArgOption.textContent = "no arg";
  noArgOption.dataset.baseLabel = "no arg";
  argFilterEl.appendChild(noArgOption);

  for (const arg of globalArgs) {
    const option = document.createElement("option");
    option.value = arg;
    option.textContent = `insn ${arg}`;
    option.dataset.baseLabel = `insn ${arg}`;
    argFilterEl.appendChild(option);
  }
  const knownValues = new Set(["all", "__no_arg__", ...globalArgs.map(String)]);
  if (!knownValues.has(app.selectedArg)) {
    app.selectedArg = "all";
  }
  argFilterEl.value = app.selectedArg;
}

function sumSamples(samples) {
  if (!Array.isArray(samples) || !samples.length) {
    return 0;
  }
  return samples.reduce((acc, value) => acc + Number(value || 0), 0);
}

function computeArgTotalsByValue(ranges) {
  const totals = new Map();
  let grandTotal = 0;
  for (const range of ranges || []) {
    const noArgTotal = sumSamples(range?.no_arg);
    if (noArgTotal > 0) {
      totals.set("__no_arg__", (totals.get("__no_arg__") || 0) + noArgTotal);
      grandTotal += noArgTotal;
    }
    const byArg = range?.by_arg || {};
    for (const [argKey, samples] of Object.entries(byArg)) {
      const argTotal = sumSamples(samples);
      if (argTotal <= 0) {
        continue;
      }
      totals.set(String(argKey), (totals.get(String(argKey)) || 0) + argTotal);
      grandTotal += argTotal;
    }
  }
  return { totals, grandTotal };
}

export function applyArgTimingToOptions(data) {
  const argFilterEl = ui?.argFilterEl;
  if (!argFilterEl) {
    return;
  }

  const options = [...argFilterEl.options];
  if (!options.length) {
    return;
  }

  const selected = argFilterEl.value;
  const { totals, grandTotal } = computeArgTotalsByValue(data?.ranges || []);
  const rankedValues = options
    .map((opt) => opt.value)
    .filter((value) => value !== "all")
    .sort((a, b) => {
      const diff = (totals.get(b) || 0) - (totals.get(a) || 0);
      if (diff !== 0) {
        return diff;
      }
      if (a === "__no_arg__") {
        return -1;
      }
      if (b === "__no_arg__") {
        return 1;
      }
      return Number(a) - Number(b);
    });
  const rankByValue = new Map(rankedValues.map((value, idx) => [value, idx + 1]));

  for (const option of options) {
    const baseLabel = option.dataset.baseLabel || option.value;
    if (option.value === "all") {
      option.textContent = baseLabel;
      continue;
    }
    const total = totals.get(option.value) || 0;
    const pct = grandTotal > 0 ? (100 * total) / grandTotal : 0;
    const rank = rankByValue.get(option.value) || 0;
    if (total <= 0) {
      option.textContent = `${baseLabel} (0%)`;
      continue;
    }
    const rankTag = rank > 0 && rank <= 3 ? ` #${rank}` : "";
    option.textContent = `${baseLabel}${rankTag} (${pct.toFixed(1)}%, ${formatNs(total)})`;
  }

  const allOption = options.find((option) => option.value === "all");
  const noArgOption = options.find((option) => option.value === "__no_arg__");
  const argOptions = options
    .filter((option) => option.value !== "all" && option.value !== "__no_arg__")
    .sort((a, b) => {
      const diff = (totals.get(b.value) || 0) - (totals.get(a.value) || 0);
      if (diff !== 0) {
        return diff;
      }
      return Number(a.value) - Number(b.value);
    });

  argFilterEl.innerHTML = "";
  if (allOption) {
    argFilterEl.appendChild(allOption);
  }
  if (noArgOption) {
    argFilterEl.appendChild(noArgOption);
  }
  for (const option of argOptions) {
    argFilterEl.appendChild(option);
  }
  argFilterEl.value = selected;
}

export function buildReportSelect(reports, currentId) {
  const reportSelectEl = ui?.reportSelectEl;
  if (!reportSelectEl) {
    return;
  }
  reportSelectEl.innerHTML = "";
  if (!reports.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "(no reports)";
    opt.disabled = true;
    reportSelectEl.appendChild(opt);
    return;
  }
  const sortedReports = [...reports].sort((a, b) => {
    const aDuration = Number(a?.total_duration_ns ?? a?.total_duration ?? 0);
    const bDuration = Number(b?.total_duration_ns ?? b?.total_duration ?? 0);
    if (bDuration !== aDuration) {
      return bDuration - aDuration;
    }
    const aId = String(a?.id ?? a ?? "");
    const bId = String(b?.id ?? b ?? "");
    return aId.localeCompare(bId);
  });
  for (const r of sortedReports) {
    const id = r.id ?? r;
    const label = r.label ?? id;
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = label;
    reportSelectEl.appendChild(opt);
  }
  const ids = new Set([...reportSelectEl.options].map((o) => o.value));
  if (currentId && ids.has(currentId)) {
    reportSelectEl.value = currentId;
  } else {
    reportSelectEl.selectedIndex = 0;
  }
}

export function renderBpfDisasm(config) {
  const bpfDisasmPreEl = ui?.bpfDisasmPreEl;
  const bpfProgramDetailsEl = ui?.bpfProgramDetailsEl;
  if (!bpfDisasmPreEl || !bpfProgramDetailsEl) {
    return;
  }
  const insns = config.bpf_insns;
  if (!Array.isArray(insns) || insns.length === 0) {
    app.bpfDisasmInsns = null;
    app.insnTiming = {};
    app.insnTimingByFile = {};
    app.bpfProfiledFiles = [];
    bpfDisasmPreEl.textContent =
      "(No BPF instruction dump in this report — re-run analysis after profiling, or program was below the save threshold.)";
    bpfProgramDetailsEl.open = false;
    return;
  }
  app.bpfDisasmInsns = insns;
  app.insnTiming = config.insn_timing && typeof config.insn_timing === "object" ? config.insn_timing : {};
  app.insnTimingByFile =
    config.insn_timing_by_file && typeof config.insn_timing_by_file === "object"
      ? config.insn_timing_by_file
      : {};
  app.bpfProfiledFiles = Array.isArray(config.profiled_files) ? config.profiled_files : [];
  buildBpfInsnFileOptions(app.bpfProfiledFiles);
  const bpfInsnScaleSelectEl = ui?.bpfInsnScaleSelectEl;
  if (bpfInsnScaleSelectEl) {
    bpfInsnScaleSelectEl.value = app.bpfInsnScaleMode;
  }
  refreshBpfDisasmHeatmap();
}

/** @param {Record<string, unknown>} config */
export function renderVerifierProfileStats(config) {
  const detailsEl = document.getElementById("verifierProfileStats");
  const preEl = document.getElementById("verifierProfileStatsPre");
  if (!detailsEl || !preEl) {
    return;
  }
  const ps = config.profile_stats;
  if (!ps || typeof ps !== "object") {
    preEl.textContent =
      "(No verifier profile stats in this report — re-save analysis from a profile .bin that includes ProfileStats.)";
    detailsEl.open = false;
    return;
  }
  const lines = [
    `subprog_cnt: ${ps.subprog_cnt}`,
    `insn_processed: ${ps.insn_processed}`,
    `complexity_limit_insns: ${ps.complexity_limit_insns}`,
    `max_states_per_insn: ${ps.max_states_per_insn}`,
    `total_states: ${ps.total_states}`,
    `peak_states: ${ps.peak_states}`,
    `longest_mark_read_walk: ${ps.longest_mark_read_walk}`,
  ];
  preEl.textContent = lines.join("\n");
}

/** @param {Record<string, unknown> | null | undefined} ps */
export function formatProfileStatsSummary(ps) {
  if (!ps || typeof ps !== "object") {
    return "";
  }
  const ip = ps.insn_processed;
  const ts = ps.total_states;
  const pk = ps.peak_states;
  if (ip == null && ts == null && pk == null) {
    return "";
  }
  return `verify stats: insn_processed=${ip} total_states=${ts} peak_states=${pk}`;
}

export async function loadConfig() {
  const metaEl = ui?.metaEl;
  const scaleModeSelectEl = ui?.scaleModeSelectEl;
  const config = await apiGet("/api/config");
  app.totalDurationNs = Number(config.total_duration_ns ?? config.total_duration ?? 0);
  const warnings = config.load_error ? ` | warning: ${config.load_error}` : "";
  const insnCount =
    config.bpf_insn_count != null
      ? config.bpf_insn_count
      : Array.isArray(config.bpf_insns)
        ? config.bpf_insns.length
        : null;
  const parts = [
    `report: ${config.current_report || "—"}`,
    `program: ${config.program_name || "n/a"}`,
    `duration: ${formatNs(config.total_duration || 0)}`,
    `profiled files: ${config.profiled_files_count}`,
  ];
  if (insnCount != null) {
    parts.push(`bpf insns: ${insnCount}`);
  }
  const traceRecords = config.trace_record_count;
  if (typeof traceRecords === "number" && traceRecords >= 0) {
    parts.push(`records: ${traceRecords}`);
  }
  if (config.kernel_compiler) {
    parts.push(`compiler: ${config.kernel_compiler}`);
  }
  const statsSummary = formatProfileStatsSummary(config.profile_stats);
  if (statsSummary) {
    parts.push(statsSummary);
  }
  parts.push(`KERNEL_PATH: ${config.kernel_path}`, `ANALYSIS_DIR: ${config.analysis_dir || "—"}`);
  if (metaEl) {
    metaEl.textContent = parts.join(" | ") + warnings;
  }
  renderBpfDisasm(config);
  renderVerifierProfileStats(config);
  buildReportSelect(config.reports || [], config.current_report);
  buildArgOptions(config.global_args || []);
  if (scaleModeSelectEl) {
    scaleModeSelectEl.value = app.selectedScaleMode;
  }
}
