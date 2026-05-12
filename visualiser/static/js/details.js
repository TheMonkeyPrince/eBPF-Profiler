import { formatLineRangeLabel, formatNs, formatSampleList } from "./formatting.js";
import {
  computeReferenceNs,
  lineSampleStats,
  rangeExclusiveSamplesForCurrentArg,
  rangeSamplesForCurrentArg,
} from "./ranges.js";
import { computeSampleStats } from "./samples.js";
import { app, ui } from "./state.js";

export function updateHoverDetails(lineNo) {
  const hoverDetailsEl = ui?.hoverDetailsEl;
  if (!hoverDetailsEl) {
    return;
  }
  if (!app.currentFileData || !lineNo) {
    app.lastDetailsText = "Hover a line to see detailed profiling data.";
    hoverDetailsEl.textContent = app.lastDetailsText;
    return;
  }

  const stat = app.currentFileData.line_stats[lineNo] || {
    total_ns: 0,
    count: 0,
    avg_ns: 0,
    max_ns: 0,
  };
  const touching = app.lineRangesIndex[lineNo] || [];
  const referenceNs = computeReferenceNs(app.currentFileData);
  const ratio = referenceNs ? (stat.total_ns / referenceNs) * 100 : 0;

  const lineStats = lineSampleStats(lineNo);
  const fnSet = new Set();
  for (const r of touching) {
    if (r.function && String(r.function).trim()) {
      fnSet.add(String(r.function).trim());
    }
  }
  const fnList = [...fnSet];
  const fnSuffix = fnList.length ? ` — ${fnList.join(", ")}` : "";

  const header = [
    `Line ${lineNo}${fnSuffix} (${app.selectedArg === "all" ? "all args" : `arg=${app.selectedArg}`})`,
    `total=${formatNs(stat.total_ns)} (${ratio.toFixed(2)}%) | ref=${formatNs(referenceNs)} (${app.selectedScaleMode})`,
    `samples=${lineStats.count} | min=${formatNs(lineStats.min)} | max=${formatNs(lineStats.max)} | avg=${formatNs(lineStats.avg)} | med=${formatNs(lineStats.med)}`,
  ];

  if (!touching.length) {
    app.lastDetailsText = `${header.join("\n")}\nNo profiling ranges touch this line.`;
    hoverDetailsEl.textContent = app.lastDetailsText;
    return;
  }

  const rangeLines = touching.slice(0, 6).map((range) => {
    const samples = rangeSamplesForCurrentArg(range);
    const stats = computeSampleStats(samples);
    const share = referenceNs ? (stats.total / referenceNs) * 100 : 0;
    const exSamples = rangeExclusiveSamplesForCurrentArg(range);
    let exclusiveChunk = "";
    if (exSamples.length && exSamples.length === samples.length) {
      const ex = computeSampleStats(exSamples);
      exclusiveChunk = ` | excl total=${formatNs(ex.total)} ex avg=${formatNs(ex.avg)}`;
    }
    return (
      `range ${formatLineRangeLabel(range.start, range.end)}${range.function ? ` ${range.function}` : ""} ` +
      `| total=${formatNs(stats.total)} (${share.toFixed(2)}%) | count=${stats.count} ` +
      `| min=${formatNs(stats.min)} | max=${formatNs(stats.max)} ` +
      `| avg=${formatNs(stats.avg)} | med=${formatNs(stats.med)}${exclusiveChunk} ` +
      `| samples=${formatSampleList(samples)}`
    );
  });

  const hidden = touching.length > 6 ? `\n... ${touching.length - 6} more touching ranges` : "";
  app.lastDetailsText = `${header.join("\n")}\n${rangeLines.join("\n")}${hidden}`;
  hoverDetailsEl.textContent = app.lastDetailsText;
}
