export function isAggregatedSampleBlock(block) {
  return (
    block &&
    typeof block === "object" &&
    !Array.isArray(block) &&
    block.count != null &&
    block.total_ns != null
  );
}

export function sampleInclusiveNs(value) {
  if (typeof value === "number") {
    return value;
  }
  if (value && typeof value === "object" && value.inclusive_ns != null) {
    return Number(value.inclusive_ns);
  }
  return Number(value);
}

/** Total inclusive ns for a per-arg block (aggregated stats or legacy sample array). */
export function sampleBlockTotalNs(block) {
  if (isAggregatedSampleBlock(block)) {
    return Number(block.total_ns) || 0;
  }
  if (!Array.isArray(block)) {
    return 0;
  }
  return block.reduce((acc, value) => acc + sampleInclusiveNs(value), 0);
}

/** Preview values for hover (aggregated `preview` or legacy array, capped). */
export function sampleBlockPreview(block, limit = 8) {
  if (isAggregatedSampleBlock(block)) {
    return (block.preview || []).slice(0, limit);
  }
  if (!Array.isArray(block)) {
    return [];
  }
  return block.slice(0, limit);
}

export function sampleBlockCount(block) {
  if (isAggregatedSampleBlock(block)) {
    return Number(block.count) || 0;
  }
  return Array.isArray(block) ? block.length : 0;
}

export function computeSampleStatsFromBlock(block) {
  if (isAggregatedSampleBlock(block)) {
    return {
      count: Number(block.count) || 0,
      total: Number(block.total_ns) || 0,
      min: Number(block.min_ns) || 0,
      max: Number(block.max_ns) || 0,
      avg: block.count ? Number(block.total_ns) / Number(block.count) : 0,
      med: Number(block.med_ns) || 0,
    };
  }
  return computeSampleStats(block);
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
