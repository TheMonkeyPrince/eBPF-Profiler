import { apiGet } from "./api.js";
import { formatNs } from "./formatting.js";
import { app, ui } from "./state.js";

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
    bpfDisasmPreEl.textContent =
      "(No BPF instruction dump in this report — re-run analysis after profiling, or program was below the save threshold.)";
    bpfProgramDetailsEl.open = false;
    return;
  }
  bpfDisasmPreEl.textContent =
    typeof window.disasmBpfProgram === "function"
      ? window.disasmBpfProgram(insns)
      : JSON.stringify(insns, null, 2);
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
