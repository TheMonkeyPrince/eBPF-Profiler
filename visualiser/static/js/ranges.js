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

/** `argKey === null` → `no_arg` samples only; else `by_arg` key (numeric string). */
export function rangeSamplesForArgKey(range, argKey) {
  if (!range) {
    return [];
  }
  if (argKey === null || argKey === undefined) {
    return [...(range.no_arg || [])];
  }
  const k =
    typeof argKey === "number" && Number.isFinite(argKey) ? String(argKey) : String(argKey);
  return [...((range.by_arg && range.by_arg[k]) || [])];
}

export function rangeTotalForArgKey(range, argKey) {
  return rangeSamplesForArgKey(range, argKey).reduce((acc, v) => acc + sampleInclusiveNs(v), 0);
}

export function rangeCallCountForArgKey(range, argKey) {
  return rangeSamplesForArgKey(range, argKey).length;
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

/** Stable key matching server-side merged ranges (start, end, optional function). */
export function profiledRangeMergeKey(range) {
  const fn = range.function && String(range.function).trim() ? String(range.function).trim() : "";
  return `${range.start}:${range.end}:${fn}`;
}

/** @param {string} loc `path/file.c:start:end` */
export function parseCallTreeLocation(loc) {
  const i = loc.lastIndexOf(":");
  if (i <= 0) {
    return null;
  }
  const j = loc.lastIndexOf(":", i - 1);
  if (j < 0) {
    return null;
  }
  const file = loc.slice(0, j);
  const start = Number.parseInt(loc.slice(j + 1, i), 10);
  const end = Number.parseInt(loc.slice(i + 1), 10);
  if (!Number.isFinite(start) || !Number.isFinite(end)) {
    return null;
  }
  return { file, start, end };
}

/** @param {Record<string, unknown>} node */
export function callTreeNodeMergeKey(node) {
  const loc = node.file || node.site;
  if (typeof loc !== "string") {
    return null;
  }
  const parsed = parseCallTreeLocation(loc);
  if (!parsed) {
    return null;
  }
  const fn = node.function && String(node.function).trim() ? String(node.function).trim() : "";
  return {
    file: parsed.file,
    start: parsed.start,
    end: parsed.end,
    key: `${parsed.start}:${parsed.end}:${fn}`,
  };
}

/** @param {Record<string, unknown>} rec @param {any} range @param {number} inclusiveFallback */
function compareTreeNodeTotalForSort(rec, range, inclusiveFallback) {
  if (range && rec._visualiser_arg_branch && app.selectedArg === "all") {
    const argVal = rec.arg;
    const key = argVal === undefined || argVal === null ? null : String(Number(argVal));
    if (key !== null && Number.isFinite(Number(argVal))) {
      return rangeTotalForArgKey(range, key);
    }
    return rangeTotalForArgKey(range, null);
  }
  if (range) {
    return rangeTotalForCurrentArg(range);
  }
  return inclusiveFallback;
}

/** @param {Record<string, unknown>} rec @param {any} range */
function compareTreeNodeCallsForSort(rec, range) {
  if (range && rec._visualiser_arg_branch && app.selectedArg === "all") {
    const argVal = rec.arg;
    const key = argVal === undefined || argVal === null ? null : String(Number(argVal));
    if (key !== null && Number.isFinite(Number(argVal))) {
      return rangeCallCountForArgKey(range, key);
    }
    return rangeCallCountForArgKey(range, null);
  }
  if (range) {
    return rangeCallCountForCurrentArg(range);
  }
  return 0;
}

/**
 * @param {unknown} a
 * @param {unknown} b
 * @param {Map<string, unknown>} filteredByKey
 */
function compareCallTreeSiblings(a, b, filteredByKey) {
  const recA = /** @type {Record<string, unknown>} */ (a);
  const recB = /** @type {Record<string, unknown>} */ (b);
  const nkA = callTreeNodeMergeKey(recA);
  const nkB = callTreeNodeMergeKey(recB);
  const path = app.selectedPath || "";
  const rangeA = nkA && nkA.file === path ? filteredByKey.get(nkA.key) : undefined;
  const rangeB = nkB && nkB.file === path ? filteredByKey.get(nkB.key) : undefined;

  const incA = Number(recA.inclusive_ns) || 0;
  const incB = Number(recB.inclusive_ns) || 0;

  if (app.profiledSortMode === "time") {
    const tA = compareTreeNodeTotalForSort(recA, rangeA, incA);
    const tB = compareTreeNodeTotalForSort(recB, rangeB, incB);
    if (tB !== tA) {
      return tB - tA;
    }
  } else if (app.profiledSortMode === "calls") {
    const cA = compareTreeNodeCallsForSort(recA, rangeA);
    const cB = compareTreeNodeCallsForSort(recB, rangeB);
    if (cB !== cA) {
      return cB - cA;
    }
    const tA = compareTreeNodeTotalForSort(recA, rangeA, incA);
    const tB = compareTreeNodeTotalForSort(recB, rangeB, incB);
    if (tB !== tA) {
      return tB - tA;
    }
  }

  const fileA = nkA ? nkA.file : "";
  const fileB = nkB ? nkB.file : "";
  const fc = fileA.localeCompare(fileB);
  if (fc !== 0) {
    return fc;
  }
  const sA = nkA ? nkA.start : 0;
  const sB = nkB ? nkB.start : 0;
  if (sA !== sB) {
    return sA - sB;
  }
  const eA = nkA ? nkA.end : 0;
  const eB = nkB ? nkB.end : 0;
  if (eA !== eB) {
    return eA - eB;
  }
  const argBranchRank = (r) => {
    if (!r._visualiser_arg_branch) {
      return 0;
    }
    if (r.arg === undefined || r.arg === null) {
      return -1e18;
    }
    const n = Number(r.arg);
    return Number.isFinite(n) ? n : 1e18;
  };
  return argBranchRank(recA) - argBranchRank(recB);
}

/** Same call/block site (path:start:end + function); `arg` is ignored so variants merge. */
function callTreeSiteMergeGroupKey(node) {
  const rec = /** @type {Record<string, unknown>} */ (node);
  const loc = rec.file || rec.site;
  if (typeof loc !== "string") {
    return `\0__bad__\0${String(typeof node)}`;
  }
  const fn = rec.function != null && String(rec.function).trim() ? String(rec.function).trim() : "";
  return `${loc}\0${fn}`;
}

/**
 * Merge sibling nodes that share the same site but differ by `arg` (or duplicate runs).
 * @param {unknown[]} nodes
 */
function mergeDuplicateSiteSiblings(nodes) {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return;
  }

  const snapshot = nodes.slice();
  for (const n of snapshot) {
    if (n && typeof n === "object") {
      const ch = /** @type {Record<string, unknown>} */ (n).children;
      if (Array.isArray(ch) && ch.length) {
        mergeDuplicateSiteSiblings(ch);
      }
    }
  }

  const orderKeys = [];
  const keyToGroup = new Map();
  for (const n of snapshot) {
    if (!n || typeof n !== "object") {
      continue;
    }
    const k = callTreeSiteMergeGroupKey(n);
    if (!keyToGroup.has(k)) {
      keyToGroup.set(k, []);
      orderKeys.push(k);
    }
    keyToGroup.get(k).push(n);
  }

  const next = [];
  for (const k of orderKeys) {
    const group = keyToGroup.get(k);
    if (group.length === 1) {
      next.push(group[0]);
    } else {
      next.push(mergeCallTreeNodeGroup(group));
    }
  }

  nodes.length = 0;
  for (const x of next) {
    nodes.push(x);
  }
}

function compareArgGroupMembersByArg(a, b) {
  const ra = /** @type {Record<string, unknown>} */ (a);
  const rb = /** @type {Record<string, unknown>} */ (b);
  const rank = (r) => {
    if (r.arg === undefined || r.arg === null) {
      return -1e18;
    }
    const n = Number(r.arg);
    return Number.isFinite(n) ? n : 1e18;
  };
  return rank(ra) - rank(rb);
}

function argIdentityKeyFromRecord(r) {
  if (r.arg === undefined || r.arg === null) {
    return "__no_arg__";
  }
  return String(Number(r.arg));
}

/**
 * Collapse multiple trace nodes with the same site + same arg.
 * @param {unknown[]} subGroup
 * @param {boolean} markArgBranch when true (child under multi-arg wrapper), tag for per-arg tree row
 */
function collapseSameArgDuplicates(subGroup, markArgBranch) {
  if (subGroup.length === 1) {
    const copy = structuredClone(subGroup[0]);
    const c = /** @type {Record<string, unknown>} */ (copy);
    delete c._visualiser_arg_group_wrapper;
    delete c._visualiser_merged_args;
    if (markArgBranch) {
      c._visualiser_arg_branch = true;
    } else {
      delete c._visualiser_arg_branch;
    }
    if (Array.isArray(c.children) && c.children.length) {
      mergeDuplicateSiteSiblings(c.children);
    }
    return copy;
  }
  const sorted = subGroup.slice().sort(compareArgGroupMembersByArg);
  const first = /** @type {Record<string, unknown>} */ (sorted[0]);
  const merged = { ...first };
  let sumInc = 0;
  let sumExc = 0;
  const allChildren = [];
  for (const g of sorted) {
    const r = /** @type {Record<string, unknown>} */ (g);
    sumInc += Number(r.inclusive_ns) || 0;
    sumExc += Number(r.exclusive_ns) || 0;
    if (Array.isArray(r.children) && r.children.length) {
      allChildren.push(...r.children);
    }
  }
  merged.inclusive_ns = sumInc;
  merged.exclusive_ns = sumExc;
  delete merged._visualiser_arg_group_wrapper;
  delete merged._visualiser_merged_args;
  if (markArgBranch) {
    merged._visualiser_arg_branch = true;
  } else {
    delete merged._visualiser_arg_branch;
  }
  if (allChildren.length) {
    merged.children = allChildren;
    mergeDuplicateSiteSiblings(merged.children);
  } else {
    delete merged.children;
  }
  return merged;
}

/**
 * @param {unknown[]} group
 */
function mergeCallTreeNodeGroup(group) {
  if (group.length === 1) {
    return group[0];
  }
  const sorted = group.slice().sort(compareArgGroupMembersByArg);

  const argOrder = [];
  const buckets = new Map();
  for (const g of sorted) {
    const r = /** @type {Record<string, unknown>} */ (g);
    const key = argIdentityKeyFromRecord(r);
    if (!buckets.has(key)) {
      buckets.set(key, []);
      argOrder.push(key);
    }
    buckets.get(key).push(g);
  }

  if (argOrder.length === 1) {
    return collapseSameArgDuplicates(buckets.get(argOrder[0]), false);
  }

  const first = /** @type {Record<string, unknown>} */ (sorted[0]);
  const wrapper = { ...first };
  let sumInc = 0;
  let sumExc = 0;
  for (const g of sorted) {
    const r = /** @type {Record<string, unknown>} */ (g);
    sumInc += Number(r.inclusive_ns) || 0;
    sumExc += Number(r.exclusive_ns) || 0;
  }
  wrapper.inclusive_ns = sumInc;
  wrapper.exclusive_ns = sumExc;
  delete wrapper.arg;
  delete wrapper.children;
  wrapper._visualiser_arg_group_wrapper = true;
  delete wrapper._visualiser_merged_args;
  delete wrapper._visualiser_arg_branch;

  const branchChildren = argOrder.map((key) => collapseSameArgDuplicates(buckets.get(key), true));
  wrapper.children = branchChildren;
  return wrapper;
}

/**
 * Sort sibling arrays at every depth (post-order) for list / nav consistency.
 * @param {unknown[]} nodes
 * @param {Map<string, unknown>} filteredByKey
 */
function sortCallTreeSiblingsRecursive(nodes, filteredByKey) {
  if (!Array.isArray(nodes)) {
    return;
  }
  for (const node of nodes) {
    if (node && typeof node === "object") {
      const ch = /** @type {Record<string, unknown>} */ (node).children;
      if (Array.isArray(ch) && ch.length) {
        sortCallTreeSiblingsRecursive(ch, filteredByKey);
      }
    }
  }
  nodes.sort((x, y) => compareCallTreeSiblings(x, y, filteredByKey));
}

/**
 * @param {unknown[]} filtered
 * @param {unknown[]} callTree
 * @param {string} filePath
 * @param {(a: any, b: any) => number} sortFn
 */
function orderFilteredByCallTree(filtered, callTree, filePath, sortFn) {
  const byKey = new Map();
  for (const r of filtered) {
    byKey.set(profiledRangeMergeKey(r), r);
  }
  const seen = new Set();
  const ordered = [];

  /** @param {unknown} nodes */
  function walk(nodes) {
    if (!Array.isArray(nodes)) {
      return;
    }
    for (const node of nodes) {
      if (!node || typeof node !== "object") {
        continue;
      }
      const nk = callTreeNodeMergeKey(/** @type {Record<string, unknown>} */ (node));
      if (nk && nk.file === filePath) {
        const k = nk.key;
        if (byKey.has(k) && !seen.has(k)) {
          seen.add(k);
          ordered.push(byKey.get(k));
        }
      }
      walk(/** @type {Record<string, unknown>} */ (node).children);
    }
  }
  walk(callTree);

  const tail = [];
  for (const r of filtered) {
    const k = profiledRangeMergeKey(r);
    if (!seen.has(k)) {
      tail.push(r);
    }
  }
  tail.sort(sortFn);
  return [...ordered, ...tail];
}

export function buildProfiledRanges(data) {
  const currentRange = app.profiledRanges[app.currentProfiledRangeIndex] || null;
  const filtered = (data.ranges || []).filter((range) => rangeSamplesForCurrentArg(range).length > 0);

  const sortFn = (a, b) => {
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
  };

  const useTree =
    app.profiledListDisplayMode === "tree" &&
    Array.isArray(data.call_tree) &&
    data.call_tree.length > 0 &&
    app.selectedPath;

  app.sortedCallTreeForDisplay = null;

  let ranges;
  if (useTree) {
    const filteredByKey = new Map(filtered.map((r) => [profiledRangeMergeKey(r), r]));
    const treeClone = structuredClone(data.call_tree);
    mergeDuplicateSiteSiblings(treeClone);
    sortCallTreeSiblingsRecursive(treeClone, filteredByKey);
    app.sortedCallTreeForDisplay = treeClone;
    ranges = orderFilteredByCallTree(filtered, treeClone, app.selectedPath, sortFn);
  } else {
    ranges = [...filtered].sort(sortFn);
  }

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
