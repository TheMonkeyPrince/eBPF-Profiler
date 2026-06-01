export const CHART_TYPE_KEY = "visualizer-chart-type";

/** @typedef {'doughnut' | 'bar'} ChartType */

const MONO_FONT = "'IBM Plex Mono', ui-monospace, monospace";

/** @type {ChartType} */
let chartType = loadChartType();

export function loadChartType() {
  const stored = sessionStorage.getItem(CHART_TYPE_KEY);
  if (stored === "bar" || stored === "doughnut") return stored;
  return "doughnut";
}

export function saveChartType(type) {
  sessionStorage.setItem(CHART_TYPE_KEY, type);
}

export function getChartType() {
  return chartType;
}

/** @param {ChartType} type */
export function setChartType(type) {
  if (type !== "doughnut" && type !== "bar") return;
  chartType = type;
  saveChartType(type);
}

/**
 * @param {ChartType} type
 * @param {'square' | 'children'} [variant]
 */
export function wrapClassName(type, variant = "square") {
  if (type === "bar") {
    if (variant === "children") {
      return "relative w-full mx-auto min-h-[220px] h-[min(300px,42vh)]";
    }
    return "relative w-full mx-auto min-h-[200px] h-[240px]";
  }
  if (variant === "children") {
    return "relative w-full max-w-[220px] sm:max-w-[260px] mx-auto aspect-[2/1] sm:aspect-square";
  }
  return "relative w-full max-w-[280px] mx-auto aspect-square";
}

/**
 * @param {ChartType} chartType
 * @param {{
 *   labels: string[],
 *   datasetLabel: string,
 *   data: number[],
 *   backgroundColor: string[],
 *   cutout?: string,
 *   legendPosition?: 'bottom' | 'right',
 *   legendOnClick?: (event: object, legendItem: object) => void,
 *   tooltipCallbacks?: object,
 *   onClick?: (event: object, elements: object[]) => void,
 *   onHover?: (event: object, elements: object[]) => void,
 * }} params
 */
export function buildChartJsConfig(chartType, params) {
  const {
    labels,
    datasetLabel,
    data,
    backgroundColor,
    cutout = "58%",
    legendPosition = "bottom",
    legendOnClick,
    tooltipCallbacks,
    onClick,
    onHover,
  } = params;

  const dataset = {
    label: datasetLabel,
    data,
    backgroundColor,
    borderColor: "rgb(15, 23, 42)",
    borderWidth: chartType === "bar" ? 1 : 2,
    ...(chartType === "doughnut"
      ? { hoverOffset: 6 }
      : { borderRadius: 3 }),
  };

  const legendSize = legendPosition === "right" ? 10 : 11;

  /** @type {import('chart.js').ChartConfiguration} */
  const config = {
    type: chartType === "bar" ? "bar" : "doughnut",
    data: { labels, datasets: [dataset] },
    options: {
      responsive: true,
      maintainAspectRatio: chartType === "doughnut",
      plugins: {
        legend: {
          display: chartType === "doughnut",
          position: legendPosition,
          onClick: legendOnClick,
          labels: {
            color: "#94a3b8",
            font: { family: MONO_FONT, size: legendSize },
            boxWidth: legendPosition === "right" ? 10 : 12,
            padding: legendPosition === "right" ? 6 : 10,
          },
        },
        tooltip: { callbacks: tooltipCallbacks },
      },
      onClick,
      onHover,
    },
  };

  if (chartType === "doughnut") {
    config.options.cutout = cutout;
  } else {
    config.options.indexAxis = "y";
    config.options.scales = {
      x: {
        ticks: { color: "#64748b", font: { size: 10 } },
        grid: { color: "rgba(51, 65, 85, 0.45)" },
      },
      y: {
        ticks: { color: "#94a3b8", font: { family: MONO_FONT, size: 10 } },
        grid: { display: false },
      },
    };
  }

  return config;
}

/**
 * @param {NodeListOf<HTMLSelectElement> | HTMLSelectElement[]} selects
 * @param {(type: ChartType) => void} onChange
 */
export function initChartTypeSelects(selects, onChange) {
  for (const select of selects) {
    if (!select) continue;
    select.value = chartType;
    select.addEventListener("change", () => {
      const type = /** @type {ChartType} */ (select.value);
      setChartType(type);
      for (const other of selects) {
        if (other && other !== select) other.value = type;
      }
      onChange(type);
    });
  }
}
