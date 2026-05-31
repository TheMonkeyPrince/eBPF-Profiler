/** @param {number} ns */
export function formatDurationNs(ns) {
  if (!Number.isFinite(ns) || ns < 0) return "—";
  if (ns < 1_000) return `${ns.toFixed(0)} ns`;
  if (ns < 1_000_000) return `${(ns / 1_000).toFixed(2)} µs`;
  if (ns < 1_000_000_000) return `${(ns / 1_000_000).toFixed(2)} ms`;
  return `${(ns / 1_000_000_000).toFixed(2)} s`;
}

/** @param {number} value */
export function formatPercent(value) {
  if (!Number.isFinite(value)) return "—";
  if (value >= 0.01) return `${value.toFixed(2)}%`;
  if (value > 0) return `${value.toExponential(2)}%`;
  return "0%";
}

/** @param {number} n */
export function formatCount(n) {
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString();
}

/**
 * @param {Record<string, object>} siteTree
 * @returns {Map<string, Set<number>>}
 */
export function collectSiteLocations(siteTree) {
  /** @type {Map<string, Set<number>>} */
  const byFile = new Map();

  function walk(tree) {
    for (const [key, node] of Object.entries(tree || {})) {
      const { file, line, endLine } = parseSiteKey(key);
      const lineNum = parseInt(String(line), 10);
      const endLineNum = parseInt(String(endLine), 10);
      if (file && Number.isFinite(lineNum) && lineNum > 0) {
        if (!byFile.has(file)) byFile.set(file, new Set());
        const lines = byFile.get(file);
        const start = Number.isFinite(endLineNum)
          ? Math.min(lineNum, endLineNum)
          : lineNum;
        const end = Number.isFinite(endLineNum)
          ? Math.max(lineNum, endLineNum)
          : lineNum;
        for (let i = start; i <= end; i += 1) {
          lines.add(i);
        }
      }
      if (node.children) walk(node.children);
    }
  }

  walk(siteTree);
  return byFile;
}

/**
 * @param {Record<string, object>} siteTree
 * @returns {Map<string, Map<number, { key: string, node: object, depth: number }[]>>}
 */
export function collectSiteLineIndex(siteTree) {
  /** @type {Map<string, Map<number, { key: string, node: object, depth: number }[]>>} */
  const index = new Map();

  function walk(tree, depth) {
    for (const [key, node] of Object.entries(tree || {})) {
      const { file, line, endLine } = parseSiteKey(key);
      const lineNum = parseInt(String(line), 10);
      const endLineNum = parseInt(String(endLine), 10);
      if (file && Number.isFinite(lineNum) && lineNum > 0) {
        if (!index.has(file)) index.set(file, new Map());
        const byLine = index.get(file);
        const start = Number.isFinite(endLineNum)
          ? Math.min(lineNum, endLineNum)
          : lineNum;
        const end = Number.isFinite(endLineNum)
          ? Math.max(lineNum, endLineNum)
          : lineNum;
        for (let i = start; i <= end; i += 1) {
          if (!byLine.has(i)) byLine.set(i, []);
          byLine.get(i).push({ key, node, depth });
        }
      }
      if (node.children) walk(node.children, depth + 1);
    }
  }

  walk(siteTree, 0);
  return index;
}

/**
 * @param {Map<string, Map<number, { key: string, node: object, depth: number }[]>>} index
 * @param {string} file
 * @param {number} line
 */
export function pickSiteAtLine(index, file, line) {
  const candidates = index.get(file)?.get(line);
  if (!candidates?.length) return null;
  return candidates.reduce((best, cur) =>
    cur.depth > best.depth ? cur : best
  );
}

/**
 * @param {Record<string, object>} siteTree
 * @returns {Map<string, string | null>}
 */
export function buildSiteParentMap(siteTree) {
  /** @type {Map<string, string | null>} */
  const parents = new Map();

  function walk(tree, parentKey) {
    for (const [key, node] of Object.entries(tree || {})) {
      parents.set(key, parentKey);
      if (node.children) walk(node.children, key);
    }
  }

  walk(siteTree, null);
  return parents;
}

/** @param {string} siteKey */
export function parseSiteKey(siteKey) {
  const lastColon = siteKey.lastIndexOf(":");
  const secondColon = siteKey.lastIndexOf(":", lastColon - 1);
  if (secondColon < 0) {
    return { file: siteKey, line: "", endLine: "", symbol: "" };
  }
  const middle = siteKey.slice(secondColon + 1, lastColon);
  const tail = siteKey.slice(lastColon + 1);
  const isLineRange =
    /^\d+$/.test(middle) &&
    /^\d+$/.test(tail);
  if (isLineRange) {
    return {
      file: siteKey.slice(0, secondColon),
      line: middle,
      endLine: tail,
      symbol: "",
    };
  }
  return {
    file: siteKey.slice(0, secondColon),
    line: middle,
    endLine: "",
    symbol: tail,
  };
}
