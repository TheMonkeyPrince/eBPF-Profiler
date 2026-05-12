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
  argFilterEl.appendChild(allOption);

  const noArgOption = document.createElement("option");
  noArgOption.value = "__no_arg__";
  noArgOption.textContent = "no arg";
  argFilterEl.appendChild(noArgOption);

  for (const arg of globalArgs) {
    const option = document.createElement("option");
    option.value = arg;
    option.textContent = arg;
    argFilterEl.appendChild(option);
  }
  const knownValues = new Set(["all", "__no_arg__", ...globalArgs.map(String)]);
  if (!knownValues.has(app.selectedArg)) {
    app.selectedArg = "all";
  }
  argFilterEl.value = app.selectedArg;
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
  for (const r of reports) {
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
  parts.push(`KERNEL_PATH: ${config.kernel_path}`, `ANALYSIS_DIR: ${config.analysis_dir || "—"}`);
  if (metaEl) {
    metaEl.textContent = parts.join(" | ") + warnings;
  }
  renderBpfDisasm(config);
  buildReportSelect(config.reports || [], config.current_report);
  buildArgOptions(config.global_args || []);
  if (scaleModeSelectEl) {
    scaleModeSelectEl.value = app.selectedScaleMode;
  }
}
