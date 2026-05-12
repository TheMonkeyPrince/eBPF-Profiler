import { computeSampleStats, sampleInclusiveNs } from "./samples.js";
import { app } from "./state.js";

export function rangeSamplesForCurrentArg(range) {
  if (app.selectedArg === "all") {
    const combined = [...(range.no_arg || [])];
    for (const argSamples of Object.values(range.by_arg || {})) {
      combined.push(...argSamples);
    }
    return combined;
  }
  if (app.selectedArg === "__no_arg__") {
    return [...(range.no_arg || [])];
  }
  return [...((range.by_arg && range.by_arg[app.selectedArg]) || [])];
}

export function rangeExclusiveSamplesForCurrentArg(range) {
  if (!range) {
    return [];
  }
  if (app.selectedArg === "all") {
    const combined = [...(range.no_arg_exclusive || [])];
    for (const xs of Object.values(range.by_arg_exclusive || {})) {
      combined.push(...xs);
    }
    return combined;
  }
  if (app.selectedArg === "__no_arg__") {
    return [...(range.no_arg_exclusive || [])];
  }
  return [...((range.by_arg_exclusive && range.by_arg_exclusive[app.selectedArg]) || [])];
}

export function rangeTotalForCurrentArg(range) {
  return rangeSamplesForCurrentArg(range).reduce((acc, value) => acc + sampleInclusiveNs(value), 0);
}

export function rangeCallCountForCurrentArg(range) {
  return rangeSamplesForCurrentArg(range).length;
}

export function lineSampleStats(lineNo) {
  const touching = app.lineRangesIndex[lineNo] || [];
  const samples = [];
  for (const range of touching) {
    samples.push(...rangeSamplesForCurrentArg(range));
  }
  return computeSampleStats(samples);
}

export function buildLineRangesIndex(data) {
  app.lineRangesIndex = {};
  const ranges = data.ranges || [];
  for (const range of ranges) {
    for (let line = range.start; line <= range.end; line += 1) {
      if (!app.lineRangesIndex[line]) {
        app.lineRangesIndex[line] = [];
      }
      app.lineRangesIndex[line].push(range);
    }
  }
}

export function computeReferenceNs(data) {
  if (app.selectedScaleMode === "absolute") {
    return Math.max(1, app.totalDurationNs || 0);
  }
  const ranges = data.ranges || [];
  let profiledTotal = 0;
  for (const range of ranges) {
    profiledTotal += rangeTotalForCurrentArg(range);
  }
  return Math.max(1, profiledTotal);
}

export function buildProfiledRanges(data) {
  const currentRange = app.profiledRanges[app.currentProfiledRangeIndex] || null;
  const ranges = (data.ranges || [])
    .filter((range) => rangeSamplesForCurrentArg(range).length > 0)
    .sort((a, b) => {
      if (app.profiledSortMode === "time") {
        const diff = rangeTotalForCurrentArg(b) - rangeTotalForCurrentArg(a);
        if (diff !== 0) {
          return diff;
        }
      } else if (app.profiledSortMode === "calls") {
        const diff = rangeCallCountForCurrentArg(b) - rangeCallCountForCurrentArg(a);
        if (diff !== 0) {
          return diff;
        }
      }
      if (a.start !== b.start) {
        return a.start - b.start;
      }
      return a.end - b.end;
    });
  app.profiledRanges = ranges;
  if (!app.profiledRanges.length) {
    app.currentProfiledRangeIndex = -1;
  } else if (currentRange) {
    const idx = app.profiledRanges.findIndex(
      (item) => item.start === currentRange.start && item.end === currentRange.end,
    );
    app.currentProfiledRangeIndex = idx >= 0 ? idx : 0;
  } else if (app.currentProfiledRangeIndex < 0 || app.currentProfiledRangeIndex >= app.profiledRanges.length) {
    app.currentProfiledRangeIndex = 0;
  }
}

export function rangeSpan(range) {
  return range.end - range.start;
}

export function rangeStrictlyContains(outer, inner) {
  return (
    outer.start <= inner.start &&
    inner.end <= outer.end &&
    (outer.start < inner.start || inner.end < outer.end)
  );
}

/**
 * @returns {{ roots: number[], children: number[][], parentIdx: number[] }}
 */
export function buildProfiledContainmentTree(ranges) {
  const n = ranges.length;
  const parentIdx = Array(n).fill(-1);
  for (let i = 0; i < n; i += 1) {
    const child = ranges[i];
    let best = -1;
    let bestSpan = Infinity;
    for (let j = 0; j < n; j += 1) {
      if (j === i) {
        continue;
      }
      const cand = ranges[j];
      if (!rangeStrictlyContains(cand, child)) {
        continue;
      }
      const span = rangeSpan(cand);
      if (span < bestSpan || (span === bestSpan && (best < 0 || j < best))) {
        bestSpan = span;
        best = j;
      }
    }
    parentIdx[i] = best;
  }
  const children = Array.from({ length: n }, () => []);
  const roots = [];
  for (let i = 0; i < n; i += 1) {
    const p = parentIdx[i];
    if (p < 0) {
      roots.push(i);
    } else {
      children[p].push(i);
    }
  }
  const cmpIdx = (a, b) => {
    const ra = ranges[a];
    const rb = ranges[b];
    if (app.profiledSortMode === "time") {
      const diff = rangeTotalForCurrentArg(rb) - rangeTotalForCurrentArg(ra);
      if (diff !== 0) {
        return diff;
      }
    } else if (app.profiledSortMode === "calls") {
      const diff = rangeCallCountForCurrentArg(rb) - rangeCallCountForCurrentArg(ra);
      if (diff !== 0) {
        return diff;
      }
    }
    if (ra.start !== rb.start) {
      return ra.start - rb.start;
    }
    return ra.end - rb.end;
  };
  const sortRecursive = (indices) => {
    indices.sort(cmpIdx);
    for (const ix of indices) {
      sortRecursive(children[ix]);
    }
  };
  sortRecursive(roots);
  return { roots, children, parentIdx };
}
