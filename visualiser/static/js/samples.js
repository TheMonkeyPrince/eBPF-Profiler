export function sampleInclusiveNs(value) {
  if (typeof value === "number") {
    return value;
  }
  if (value && typeof value === "object" && value.inclusive_ns != null) {
    return Number(value.inclusive_ns);
  }
  return Number(value);
}

export function sampleExclusiveNs(value) {
  if (value && typeof value === "object" && value.exclusive_ns != null) {
    return Number(value.exclusive_ns);
  }
  if (typeof value === "number") {
    return Number(value);
  }
  return null;
}

export function computeSampleStats(samples) {
  if (!samples || samples.length === 0) {
    return { count: 0, total: 0, min: 0, max: 0, avg: 0, med: 0 };
  }
  const numeric = samples.map((s) => sampleInclusiveNs(s));
  const sorted = [...numeric].sort((a, b) => a - b);
  const count = sorted.length;
  const total = sorted.reduce((acc, value) => acc + value, 0);
  const min = sorted[0];
  const max = sorted[count - 1];
  const avg = total / count;
  const mid = Math.floor(count / 2);
  const med = count % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  return { count, total, min, max, avg, med };
}
