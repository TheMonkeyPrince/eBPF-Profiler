import { formatDurationNs, formatPercent, parseSiteKey } from "./format.js";
import { getSitePercent } from "./tree.js";

/** @type {import('chart.js').Chart | null} */
let activeChart = null;

const SLICE_COLORS = [
  "rgba(251, 191, 36, 0.9)",
  "rgba(34, 211, 238, 0.9)",
  "rgba(167, 139, 250, 0.9)",
  "rgba(244, 114, 182, 0.9)",
  "rgba(52, 211, 153, 0.9)",
  "rgba(96, 165, 250, 0.9)",
  "rgba(251, 146, 60, 0.9)",
  "rgba(192, 132, 252, 0.9)",
  "rgba(45, 212, 191, 0.9)",
  "rgba(248, 113, 113, 0.9)",
  "rgba(163, 230, 53, 0.9)",
  "rgba(129, 140, 248, 0.9)",
];

const OTHER_COLOR = "rgba(100, 116, 139, 0.45)";
/** Minimum gap (percentage points) before an "Other" slice is shown */
const REMAINDER_EPS = 0.05;

/** @typedef {'total' | 'parent'} PercentScale */

/**
 * @param {HTMLElement} container
 * @param {string} parentKey
 * @param {object} parentNode
 * @param {PercentScale} scale
 * @param {{ onSelect?: (key: string, node: object) => void }} [options]
 */
export function renderChildrenChart(
  container,
  parentKey,
  parentNode,
  scale,
  options = {}
) {
  const { onSelect } = options;
  if (activeChart) {
    activeChart.destroy();
    activeChart = null;
  }

  container.replaceChildren();

  const children = parentNode?.children ?? {};
  const entries = Object.entries(children);
  if (!entries.length) {
    container.innerHTML =
      '<p class="text-xs text-slate-500 py-2">No child sites for this function.</p>';
    return;
  }

  const Chart = window.Chart;
  if (!Chart) {
    container.innerHTML =
      '<p class="text-xs text-rose-400">Chart.js failed to load.</p>';
    return;
  }

  const scaleLabel = scale === "parent" ? "% of parent" : "% of total";
  const { symbol: parentSymbol } = parseSiteKey(parentKey);

  const sorted = entries
    .map(([key, node]) => ({
      key,
      node,
      pct: getSitePercent(node, scale),
      symbol: parseSiteKey(key).symbol,
      isOther: false,
    }))
    .sort((a, b) => b.pct - a.pct);

  /** @type {typeof sorted} */
  const chartEntries = [...sorted];
  const sum = chartEntries.reduce((total, c) => total + c.pct, 0);
  const remainder = 100 - sum;
  if (remainder > REMAINDER_EPS) {
    chartEntries.push({
      key: "",
      node: /** @type {object} */ ({}),
      pct: remainder,
      symbol: "Other",
      isOther: true,
    });
  }

  let colorIdx = 0;
  const labels = chartEntries.map((c) =>
    c.isOther ? "Other" : c.symbol || c.key
  );
  const data = chartEntries.map((c) => c.pct);
  const backgroundColor = chartEntries.map((c) => {
    if (c.isOther) return OTHER_COLOR;
    return SLICE_COLORS[colorIdx++ % SLICE_COLORS.length];
  });

  const wrap = document.createElement("div");
  wrap.className =
    "relative w-full max-w-[220px] sm:max-w-[260px] mx-auto aspect-[2/1] sm:aspect-square";
  const canvas = document.createElement("canvas");
  canvas.setAttribute("role", "img");
  canvas.setAttribute(
    "aria-label",
    `Child sites of ${parentSymbol} by ${scaleLabel}`
  );
  wrap.appendChild(canvas);
  container.appendChild(wrap);

  const entryByLabel = Object.fromEntries(
    chartEntries.map((c) => [c.isOther ? "Other" : c.symbol || c.key, c])
  );

  activeChart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          label: scaleLabel,
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
      cutout: "55%",
      onClick(_event, elements) {
        if (!onSelect || !elements.length) return;
        const entry = chartEntries[elements[0].index];
        if (!entry || entry.isOther) return;
        onSelect(entry.key, entry.node);
      },
      onHover(event, elements) {
        const target = event.native?.target;
        if (!target) return;
        const entry =
          elements.length > 0 ? chartEntries[elements[0].index] : null;
        target.style.cursor =
          onSelect && entry && !entry.isOther ? "pointer" : "default";
      },
      plugins: {
        legend: {
          position: "right",
          onClick(_event, legendItem) {
            if (!onSelect || legendItem.index === undefined) return;
            const entry = chartEntries[legendItem.index];
            if (!entry || entry.isOther) return;
            onSelect(entry.key, entry.node);
          },
          labels: {
            color: "#94a3b8",
            font: {
              family: "'IBM Plex Mono', ui-monospace, monospace",
              size: 10,
            },
            boxWidth: 10,
            padding: 6,
          },
        },
        tooltip: {
          callbacks: {
            label(context) {
              const label = context.label ?? "";
              const entry = entryByLabel[label];
              if (!entry) return label;
              if (entry.isOther) {
                return [
                  `Other: ${formatPercent(entry.pct)} ${scaleLabel}`,
                  "unattributed in child breakdown",
                ];
              }
              return [
                `${label}: ${formatPercent(entry.pct)} ${scaleLabel}`,
                `inclusive ${formatDurationNs(entry.node.inclusive_duration)}`,
                `exclusive ${formatDurationNs(entry.node.exclusive_duration)}`,
              ];
            },
          },
        },
      },
    },
  });
}
