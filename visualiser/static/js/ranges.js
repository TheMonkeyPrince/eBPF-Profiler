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
