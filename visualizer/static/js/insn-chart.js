import { formatDurationNs, formatCount, formatPercent } from "./format.js";
import {
  buildChartJsConfig,
  getChartType,
  wrapClassName,
} from "./chart-type.js";
import { mountChartExportButton } from "./chart-export.js";

/** @type {import('chart.js').Chart[]} */
const activeCharts = [];

const SLICE_COLORS = [
  "rgba(167, 139, 250, 0.9)",
  "rgba(34, 211, 238, 0.9)",
  "rgba(251, 191, 36, 0.9)",
  "rgba(244, 114, 182, 0.9)",
  "rgba(52, 211, 153, 0.9)",
  "rgba(96, 165, 250, 0.9)",
  "rgba(251, 146, 60, 0.9)",
  "rgba(192, 132, 252, 0.9)",
  "rgba(45, 212, 191, 0.9)",
  "rgba(248, 113, 113, 0.9)",
  "rgba(163, 230, 53, 0.9)",
  "rgba(129, 140, 248, 0.9)",
  "rgba(253, 224, 71, 0.9)",
];

/**
 * @param {HTMLElement} container
 * @param {{ stats?: Record<string, { score?: number, avg_duration?: number, count?: number }> }} instructionTypes
 * @param {{ ariaLabel?: string }} [options]
 */
export function renderInstructionChart(container, instructionTypes, options = {}) {
  container.replaceChildren();

  const stats = instructionTypes?.stats;
  if (!stats || !Object.keys(stats).length) {
    return;
  }

  const Chart = window.Chart;
  if (!Chart) {
    container.innerHTML =
      '<p class="text-xs text-rose-400">Chart.js failed to load.</p>';
    return;
  }

  const sorted = Object.entries(stats).sort(
    (a, b) => (b[1].score ?? 0) - (a[1].score ?? 0)
  );

  const labels = sorted.map(([name]) => name);
  const data = sorted.map(([, s]) => s.score ?? 0);
  const backgroundColor = labels.map(
    (_, i) => SLICE_COLORS[i % SLICE_COLORS.length]
  );

  const chartType = options.chartType ?? getChartType();

  const wrap = document.createElement("div");
  wrap.className = wrapClassName(chartType);
  const canvas = document.createElement("canvas");
  canvas.setAttribute("role", "img");
  canvas.setAttribute(
    "aria-label",
    options.ariaLabel ?? "Instruction type breakdown by relative score"
  );
  wrap.appendChild(canvas);
  container.appendChild(wrap);

  const chart = new Chart(
    canvas,
    buildChartJsConfig(chartType, {
      labels,
      datasetLabel: "Relative score",
      data,
      backgroundColor,
      tooltipCallbacks: {
        label(context) {
          const insn = context.label ?? "";
          const stat = stats[insn];
          if (!stat) return insn;
          return [
            `${insn}: ${formatPercent(stat.score ?? 0)}`,
            `avg / sample ${formatDurationNs(stat.avg_duration)}`,
            `${formatCount(stat.count)} samples`,
          ];
        },
      },
    })
  );
  activeCharts.push(chart);

  if (options.exportFilename) {
    mountChartExportButton(container, chart, options.exportFilename);
  }
}

export function getProgramInsnChart() {
  return programInsnChart;
}

export function destroyInstructionChart() {
  while (activeCharts.length) {
    activeCharts.pop()?.destroy();
  }
}

/** @type {import('chart.js').Chart | null} */
let programInsnChart = null;

const OTHER_SLICE_COLOR = "rgba(100, 116, 139, 0.45)";
const MAX_PROGRAM_INSN_SLICES = 10;

/**
 * @param {HTMLElement} container
 * @param {Record<string, { count?: number, percent?: number }>} stats
 * @param {{ ariaLabel?: string, maxSlices?: number }} [options]
 */
export function renderProgramInsnChart(container, stats, options = {}) {
  if (programInsnChart) {
    programInsnChart.destroy();
    programInsnChart = null;
  }

  container.replaceChildren();

  if (!stats || !Object.keys(stats).length) {
    container.innerHTML =
      '<p class="text-xs text-slate-500 py-2">No instruction data for chart.</p>';
    return;
  }

  const Chart = window.Chart;
  if (!Chart) {
    container.innerHTML =
      '<p class="text-xs text-rose-400">Chart.js failed to load.</p>';
    return;
  }

  const maxSlices = options.maxSlices ?? MAX_PROGRAM_INSN_SLICES;
  const sorted = Object.entries(stats)
    .map(([name, stat]) => ({
      name,
      count: stat.count ?? 0,
      percent: stat.percent ?? 0,
    }))
    .sort((a, b) => b.percent - a.percent);

  /** @type {typeof sorted} */
  const chartEntries = sorted.slice(0, maxSlices);
  const otherEntries = sorted.slice(maxSlices);
  if (otherEntries.length) {
    chartEntries.push({
      name: "Other",
      count: otherEntries.reduce((sum, e) => sum + e.count, 0),
      percent: otherEntries.reduce((sum, e) => sum + e.percent, 0),
    });
  }

  const labels = chartEntries.map((e) => e.name);
  const data = chartEntries.map((e) => e.percent);
  let colorIdx = 0;
  const backgroundColor = chartEntries.map((e) => {
    if (e.name === "Other") return OTHER_SLICE_COLOR;
    return SLICE_COLORS[colorIdx++ % SLICE_COLORS.length];
  });

  const entryByLabel = Object.fromEntries(
    chartEntries.map((e) => [e.name, e])
  );

  const chartType = options.chartType ?? getChartType();

  const wrap = document.createElement("div");
  wrap.className = wrapClassName(chartType);
  const canvas = document.createElement("canvas");
  canvas.setAttribute("role", "img");
  canvas.setAttribute(
    "aria-label",
    options.ariaLabel ?? "Program instruction mix by share of program length"
  );
  wrap.appendChild(canvas);
  container.appendChild(wrap);

  programInsnChart = new Chart(
    canvas,
    buildChartJsConfig(chartType, {
      labels,
      datasetLabel: "% of program",
      data,
      backgroundColor,
      tooltipCallbacks: {
        label(context) {
          const label = context.label ?? "";
          const entry = entryByLabel[label];
          if (!entry) return label;
          if (entry.name === "Other") {
            return [
              `Other: ${formatPercent(entry.percent)}`,
              `${formatCount(entry.count)} instructions`,
            ];
          }
          return [
            `${label}: ${formatPercent(entry.percent)}`,
            `${formatCount(entry.count)} instructions`,
          ];
        },
      },
    })
  );

  if (options.exportFilename) {
    mountChartExportButton(container, programInsnChart, options.exportFilename);
  }
}

export function destroyProgramInsnChart() {
  if (programInsnChart) {
    programInsnChart.destroy();
    programInsnChart = null;
  }
}
