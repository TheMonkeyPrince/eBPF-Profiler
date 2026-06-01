/** @typedef {import('chart.js').Chart} ChartJsChart */

const EXPORT_LEGEND_COLOR = "#334155";
const EXPORT_TICK_COLOR = "#475569";
const EXPORT_GRID_COLOR = "rgba(148, 163, 184, 0.4)";
const EXPORT_BORDER_COLOR = "#e2e8f0";
const EXPORT_BG = "#ffffff";

/**
 * @param {string} name
 */
export function sanitizeFilename(name) {
  const base = String(name)
    .trim()
    .replace(/[^\w.-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return base || "chart";
}

/**
 * @param {ChartJsChart} chart
 */
function saveChartTheme(chart) {
  const opts = chart.options;
  const ds = chart.data.datasets[0];
  /** @type {Record<string, { tickColor?: unknown, gridColor?: unknown, gridDisplay?: boolean }>} */
  const scales = {};

  if (opts.scales) {
    for (const key of Object.keys(opts.scales)) {
      const scale = opts.scales[key];
      scales[key] = {
        tickColor: scale.ticks?.color,
        gridColor: scale.grid?.color,
        gridDisplay: scale.grid?.display,
      };
    }
  }

  return {
    legendColor: opts.plugins?.legend?.labels?.color,
    borderColor: ds?.borderColor,
    scales,
  };
}

/**
 * @param {ChartJsChart} chart
 */
function applyExportTheme(chart) {
  const opts = chart.options;
  if (opts.plugins?.legend?.labels) {
    opts.plugins.legend.labels.color = EXPORT_LEGEND_COLOR;
  }

  const ds = chart.data.datasets[0];
  if (ds) ds.borderColor = EXPORT_BORDER_COLOR;

  if (opts.scales) {
    for (const key of Object.keys(opts.scales)) {
      const scale = opts.scales[key];
      if (scale.ticks) scale.ticks.color = EXPORT_TICK_COLOR;
      if (scale.grid) scale.grid.color = EXPORT_GRID_COLOR;
    }
  }
}

/**
 * @param {ChartJsChart} chart
 * @param {ReturnType<typeof saveChartTheme>} saved
 */
function restoreChartTheme(chart, saved) {
  const opts = chart.options;
  if (opts.plugins?.legend?.labels && saved.legendColor !== undefined) {
    opts.plugins.legend.labels.color = saved.legendColor;
  }

  const ds = chart.data.datasets[0];
  if (ds && saved.borderColor !== undefined) {
    ds.borderColor = saved.borderColor;
  }

  if (opts.scales) {
    for (const key of Object.keys(saved.scales)) {
      const scale = opts.scales[key];
      const prev = saved.scales[key];
      if (!scale || !prev) continue;
      if (scale.ticks && prev.tickColor !== undefined) {
        scale.ticks.color = prev.tickColor;
      }
      if (scale.grid) {
        if (prev.gridColor !== undefined) scale.grid.color = prev.gridColor;
        if (prev.gridDisplay !== undefined) scale.grid.display = prev.gridDisplay;
      }
    }
  }
}

/**
 * Composite chart image onto a white canvas (for print / reports).
 * @param {ChartJsChart} chart
 */
function chartToPngDataUrl(chart) {
  const sourceUrl = chart.toBase64Image("image/png", 1);
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth || img.width;
      canvas.height = img.naturalHeight || img.height;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        reject(new Error("Could not create export canvas"));
        return;
      }
      ctx.fillStyle = EXPORT_BG;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
      resolve(canvas.toDataURL("image/png"));
    };
    img.onerror = () => reject(new Error("Failed to render chart image"));
    img.src = sourceUrl;
  });
}

function triggerDownload(dataUrl, filename) {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = filename.endsWith(".png") ? filename : `${filename}.png`;
  a.click();
}

/**
 * Export a Chart.js chart to PNG with a white background and print-friendly colors.
 * Uses `chart.toBase64Image()` per Chart.js / QuickChart browser export guidance.
 *
 * @param {ChartJsChart | null | undefined} chart
 * @param {string} filename
 */
export async function downloadChartPng(chart, filename) {
  if (!chart?.canvas) return;

  const savedTheme = saveChartTheme(chart);
  const savedAnimation = chart.options.animation;
  chart.options.animation = false;
  applyExportTheme(chart);
  chart.update("none");

  await new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  });

  try {
    const dataUrl = await chartToPngDataUrl(chart);
    triggerDownload(dataUrl, sanitizeFilename(filename));
  } finally {
    restoreChartTheme(chart, savedTheme);
    chart.options.animation = savedAnimation;
    chart.update("none");
  }
}

const EXPORT_BTN_CLASS =
  "rounded-md border border-slate-700 bg-slate-800 px-2 py-0.5 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors shrink-0";

/**
 * @param {() => ChartJsChart | null | undefined} getChart
 * @param {() => string} getFilename
 * @param {{ label?: string }} [options]
 */
export function createChartExportButton(getChart, getFilename, options = {}) {
  const { label = "Save PNG" } = options;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = EXPORT_BTN_CLASS;
  btn.textContent = label;
  btn.addEventListener("click", () => {
    const chart = getChart();
    if (!chart) return;
    void downloadChartPng(chart, getFilename());
  });
  return btn;
}

/**
 * @param {HTMLElement} container
 * @param {ChartJsChart} chart
 * @param {string} filename
 */
export function mountChartExportButton(container, chart, filename) {
  const header = document.createElement("div");
  header.className = "flex justify-end mb-1";
  header.appendChild(
    createChartExportButton(() => chart, () => filename, { label: "Save PNG" })
  );
  container.insertBefore(header, container.firstChild);
}
