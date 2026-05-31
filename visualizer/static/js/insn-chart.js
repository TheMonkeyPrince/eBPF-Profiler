import { formatDurationNs, formatCount, formatPercent } from "./format.js";

/** @type {import('chart.js').Chart | null} */
let activeChart = null;

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
 */
export function renderInstructionChart(container, instructionTypes) {
  if (activeChart) {
    activeChart.destroy();
    activeChart = null;
  }

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

  const wrap = document.createElement("div");
  wrap.className = "relative w-full max-w-[280px] mx-auto aspect-square";
  const canvas = document.createElement("canvas");
  canvas.setAttribute("role", "img");
  canvas.setAttribute(
    "aria-label",
    "Instruction type breakdown by relative score"
  );
  wrap.appendChild(canvas);
  container.appendChild(wrap);

  activeChart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          label: "Relative score",
          data,
          backgroundColor,
          borderColor: "rgb(15, 23, 42)",
          borderWidth: 2,
          hoverOffset: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: "58%",
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: "#94a3b8",
            font: { family: "'IBM Plex Mono', ui-monospace, monospace", size: 11 },
            boxWidth: 12,
            padding: 10,
          },
        },
        tooltip: {
          callbacks: {
            label(context) {
              const insn = context.label ?? "";
              const stat = stats[insn];
              if (!stat) return insn;
              return [
                `${insn}: ${formatPercent(stat.score ?? 0)}`,
                `avg ${formatDurationNs(stat.avg_duration)}`,
                `${formatCount(stat.count)} samples`,
              ];
            },
          },
        },
      },
    },
  });
}

export function destroyInstructionChart() {
  if (activeChart) {
    activeChart.destroy();
    activeChart = null;
  }
}
