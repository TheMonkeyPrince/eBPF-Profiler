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
  const score = Math.log1p(totalNs) / Math.log1p(referenceNs);
  return Math.min(0.85, Math.max(0.05, score));
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
    "#ff500030",
    "#ff500045",
    "#ff500058",
    "#ff50006b",
    "#ff500080",
    "#ff500095",
    "#ff5000ad",
    "#ff5000c2",
    "#ff5000d6",
    "#ff5000eb",
    "#ff5000f2",
    "#ff5000f4",
    "#ff5000f6",
    "#ff5000f8",
    "#ff5000fa",
    "#ff5000fc",
    "#ff5000fd",
    "#ff5000fe",
    "#ff5000ff",
    "#ff3b00ff",
  ];
  return palette[bucket] || palette[HEAT_BUCKETS];
}

export function formatSampleList(samples) {
  if (!samples || samples.length === 0) {
    return "[]";
  }
  const shown = samples.slice(0, 8).map((v) => {
    const inc = sampleInclusiveNs(v);
    const exc = sampleExclusiveNs(v);
    if (exc != null && exc !== inc) {
      return `${Number(inc).toLocaleString()} ex ${Number(exc).toLocaleString()}`;
    }
    return Number(inc).toLocaleString();
  });
  if (samples.length > 8) {
    shown.push(`... +${samples.length - 8}`);
  }
  return `[${shown.join(", ")}]`;
}
