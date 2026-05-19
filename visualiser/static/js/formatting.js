import { HEAT_BUCKETS } from "./state.js";
import { sampleExclusiveNs, sampleInclusiveNs } from "./samples.js";

export function formatNs(ns) {
  return `${Number(ns).toLocaleString()} ns`;
}

/** e.g. `L101` when start === end, else `L101-110`. */
export function formatLineRangeLabel(start, end) {
  const s = Number(start);
  const e = Number(end);
  if (s === e) {
    return `L${s}`;
  }
  return `L${s}-${e}`;
}

export function heatAlpha(totalNs, referenceNs) {
  if (!totalNs || !referenceNs) {
    return 0;
  }
  const ratio = Math.min(1, Math.max(0, totalNs / referenceNs));
  return Math.sqrt(ratio);
}

export function heatBucket(alpha) {
  if (!alpha || alpha <= 0) {
    return 0;
  }
  return Math.min(HEAT_BUCKETS, Math.max(1, Math.ceil(alpha * HEAT_BUCKETS)));
}

export function overviewColor(bucket) {
  const palette = [
    "#00000000",
    "#2dae4b40",
    "#3fb44752",
    "#55ba4264",
    "#6cc03d76",
    "#83c63888",
    "#9acc339a",
    "#b2d12fac",
    "#c9d72abe",
    "#e1dd25d0",
    "#f5d621dc",
    "#f8bd1fe4",
    "#faa31dec",
    "#fc8a1bf2",
    "#fd7119f6",
    "#fe5817fa",
    "#ff4815fc",
    "#ff3b13fd",
    "#ff3011fe",
    "#ff260fff",
    "#ff1f0dff",
  ];
  return palette[bucket] || palette[HEAT_BUCKETS];
}

/**
 * @param {unknown[]} samples preview values (may be capped)
 * @param {number} [totalCount] full sample count when `samples` is only a preview
 */
export function formatSampleList(samples, totalCount) {
  if (!samples || samples.length === 0) {
    return "[]";
  }
  const total = totalCount != null && totalCount >= 0 ? totalCount : samples.length;
  const shown = samples.slice(0, 8).map((v) => {
    const inc = sampleInclusiveNs(v);
    const exc = sampleExclusiveNs(v);
    if (exc != null && exc !== inc) {
      return `${Number(inc).toLocaleString()} ex ${Number(exc).toLocaleString()}`;
    }
    return Number(inc).toLocaleString();
  });
  if (total > 8) {
    shown.push(`... +${total - 8}`);
  }
  return `[${shown.join(", ")}]`;
}
