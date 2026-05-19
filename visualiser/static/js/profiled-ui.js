import { formatLineRangeLabel, formatNs } from "./formatting.js";
import {
  callTreeNodeMergeKey,
  computeReferenceNs,
  profiledRangeMergeKey,
  rangeCallCountForCurrentArg,
  rangeTotalForArgKey,
  rangeTotalForCurrentArg,
} from "./ranges.js";
import { app, ui } from "./state.js";

function formatProfiledLocation(range) {
  if (range.function && String(range.function).trim()) {
    return { hasFn: true };
  }
  return { hasFn: false };
}

/** @param {HTMLElement} labelEl @param {number | null} parentSharePct */
function appendParentShareFragment(labelEl, parentSharePct) {
  if (parentSharePct == null || !Number.isFinite(parentSharePct)) {
    return;
  }
  const span = document.createElement("span");
  span.className = "profiled-parent-pct";
  span.textContent = `  ·  ${parentSharePct.toFixed(1)}% of parent`;
  labelEl.appendChild(span);
}

/**
 * @param {HTMLElement} labelEl
 * @param {any} range
 * @param {number | null} [parentSharePct] share of direct parent's display total (tree mode)
 */
function fillProfiledLabelPrimary(labelEl, range, parentSharePct = null) {
  labelEl.textContent = "";
  const total = rangeTotalForCurrentArg(range);
  const referenceNs = app.currentFileData ? computeReferenceNs(app.currentFileData) : 0;
  const ratio = referenceNs ? (total / referenceNs) * 100 : 0;
  const count = rangeCallCountForCurrentArg(range);
  const loc = formatProfiledLocation(range);
  if (loc.hasFn) {
    const spanLoc = document.createElement("span");
    spanLoc.className = "profiled-loc";
    spanLoc.textContent = formatLineRangeLabel(range.start, range.end);
    const spanFn = document.createElement("span");
    spanFn.className = "profiled-fn";
    spanFn.textContent = ` ${range.function}`;
    labelEl.appendChild(spanLoc);
    labelEl.appendChild(spanFn);
    labelEl.appendChild(
      document.createTextNode(`  ·  ${formatNs(total)}  ·  ${ratio.toFixed(1)}%  ·  ${count} samples`),
    );
  } else {
    labelEl.appendChild(
      document.createTextNode(
        `${formatLineRangeLabel(range.start, range.end)}  ·  ${formatNs(total)}  ·  ${ratio.toFixed(1)}%  ·  ${count} samples`,
      ),
    );
  }
  appendParentShareFragment(labelEl, parentSharePct);
}

/**
 * @param {HTMLElement} labelEl
 * @param {Record<string, unknown>} node
 * @param {{ file: string, start: number, end: number, key: string } | null} nk
 * @param {number | null} [parentSharePct]
 */
function fillCallTreeContextLabel(labelEl, node, nk, parentSharePct = null) {
  labelEl.textContent = "";
  const loc = node.file;
  const shortFile = nk ? nk.file.split("/").pop() || nk.file : typeof loc === "string" ? loc : "";
  const fn = node.function && String(node.function).trim() ? String(node.function) : "";
  const spanFile = document.createElement("span");
  spanFile.className = "list-tree-context-file";
  spanFile.textContent = shortFile || "(unknown)";
  labelEl.appendChild(spanFile);
  if (nk) {
    labelEl.appendChild(document.createTextNode(`  ·  ${formatLineRangeLabel(nk.start, nk.end)}`));
  }
  if (fn) {
    const spanFn = document.createElement("span");
    spanFn.className = "profiled-fn";
    spanFn.textContent = `  ${fn}`;
    labelEl.appendChild(spanFn);
  }
  if (node._visualiser_arg_branch) {
    const av = node.arg;
    const tag = av === undefined || av === null ? "no arg" : `insn ${av}`;
    labelEl.appendChild(document.createTextNode(`  ·  ${tag}`));
  }
  const inc = treeNodeDisplayTotalNs(node);
  labelEl.appendChild(document.createTextNode(`  ·  ${formatNs(inc)}`));
  appendParentShareFragment(labelEl, parentSharePct);
}

function findProfiledIndexForCallTreeNode(node) {
  const nk = callTreeNodeMergeKey(node);
  if (!nk || nk.file !== app.selectedPath) {
    return -1;
  }
  return app.profiledRanges.findIndex((r) => profiledRangeMergeKey(r) === nk.key);
}

/** Total ns for tree parent % and row weighting. */
function treeNodeDisplayTotalNs(node) {
  const rec = /** @type {Record<string, unknown>} */ (node);
  const idx = findProfiledIndexForCallTreeNode(rec);
  if (idx >= 0) {
    const range = app.profiledRanges[idx];
    if (rec._visualiser_arg_branch && app.selectedArg === "all") {
      const argVal = rec.arg;
      if (argVal === undefined || argVal === null) {
        return rangeTotalForArgKey(range, null);
      }
      const key = Number(argVal);
      return Number.isFinite(key) ? rangeTotalForArgKey(range, key) : 0;
    }
    return rangeTotalForCurrentArg(range);
  }
  const raw = Number(rec.inclusive_ns);
  return Number.isFinite(raw) ? raw : 0;
}

/**
 * @param {unknown[]} nodes
 * @param {string} pathPrefix
 * @param {number} depth
 * @param {number | null} parentDisplayTotalNs direct parent's display total, or null for roots
 */
function renderCallTreeRows(nodes, pathPrefix, depth, parentDisplayTotalNs) {
  const bucket = document.createDocumentFragment();
  if (!Array.isArray(nodes)) {
    return bucket;
  }

  nodes.forEach((node, i) => {
    const id = pathPrefix === "" ? `${i}` : `${pathPrefix}/${i}`;
    const rec = /** @type {Record<string, unknown>} */ (node);
    const children = rec.children;
    const hasCh = Array.isArray(children) && children.length > 0;
    const expanded = app.profiledTreeExpanded[id] !== false;
    const treeExpandable = hasCh;
    const showChildrenBlock = hasCh && expanded;

    const nk = callTreeNodeMergeKey(rec);
    const inFile = !!(nk && nk.file === app.selectedPath);
    const rangeIdx = findProfiledIndexForCallTreeNode(rec);
    const isActive = rangeIdx >= 0 && rangeIdx === app.currentProfiledRangeIndex;

    const ownDisplayTotal = treeNodeDisplayTotalNs(rec);
    let parentSharePct = null;
    if (parentDisplayTotalNs != null && parentDisplayTotalNs > 0 && Number.isFinite(ownDisplayTotal)) {
      parentSharePct = (100 * ownDisplayTotal) / parentDisplayTotalNs;
    }

    const row = document.createElement("div");
    row.className = "list-tree-row explorer-row";
    if (rec._visualiser_arg_branch) {
      row.classList.add("list-tree-row--arg-branch");
    }
    if (isActive) {
      row.classList.add("active");
    }
    if (!inFile) {
      row.classList.add("list-tree-row--foreign");
    }
    row.style.paddingLeft = `${2 + depth * 12}px`;

    const chev = document.createElement("button");
    chev.type = "button";
    chev.className = "explorer-chevron list-tree-twistie";
    if (treeExpandable) {
      chev.textContent = expanded ? "▾" : "▸";
      chev.setAttribute("aria-expanded", String(expanded));
      chev.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const cur = app.profiledTreeExpanded[id] !== false;
        app.profiledTreeExpanded[id] = !cur;
        renderProfiledList();
      });
    } else {
      chev.classList.add("placeholder");
      chev.disabled = true;
      chev.setAttribute("aria-hidden", "true");
    }
    const icon = document.createElement("span");
    icon.className = "explorer-icon list-tree-icon";
    icon.textContent = treeExpandable ? "📁" : "📄";

    const label = document.createElement("div");
    label.className = "list-tree-label profiled-range-label";
    if (rangeIdx >= 0) {
      fillProfiledLabelPrimary(label, app.profiledRanges[rangeIdx], parentSharePct);
    } else {
      label.classList.add("list-tree-label--context");
      fillCallTreeContextLabel(label, rec, nk, parentSharePct);
    }

    row.appendChild(chev);
    row.appendChild(icon);
    row.appendChild(label);

    row.addEventListener("click", async (e) => {
      if (e.target.closest(".explorer-chevron")) {
        return;
      }
      if (rangeIdx >= 0) {
        const { focusProfiledRange } = await import("./editor.js");
        await focusProfiledRange(rangeIdx, true);
      }
    });

    bucket.appendChild(row);

    if (showChildrenBlock) {
      const wrap = document.createElement("div");
      wrap.className = "list-tree-children";
      wrap.appendChild(renderCallTreeRows(children, id, depth + 1, ownDisplayTotal));
      bucket.appendChild(wrap);
    }
  });

  return bucket;
}

function makeProfiledRangeRow(range, idx) {
  const row = document.createElement("div");
  row.className = `explorer-row profiled-range-row${idx === app.currentProfiledRangeIndex ? " active" : ""}`;
  row.dataset.rangeIndex = String(idx);

  const label = document.createElement("div");
  label.className = "profiled-range-label";
  fillProfiledLabelPrimary(label, range);

  row.appendChild(label);

  row.addEventListener("click", async () => {
    const { focusProfiledRange } = await import("./editor.js");
    await focusProfiledRange(idx, true);
  });

  return row;
}

export function renderProfiledList() {
  const profiledListEl = ui?.profiledListEl;
  if (!profiledListEl) {
    return;
  }
  profiledListEl.innerHTML = "";
  const treeMode = app.profiledListDisplayMode === "tree";
  profiledListEl.classList.toggle("profiled-list--tree", treeMode);

  if (!app.selectedPath) {
    const empty = document.createElement("div");
    empty.className = "profiled-item-empty";
    empty.textContent = "Open a file to list profiled boxes.";
    profiledListEl.appendChild(empty);
    return;
  }
  if (!app.profiledRanges.length) {
    const empty = document.createElement("div");
    empty.className = "profiled-item-empty";
    empty.textContent = "No profiled boxes for current BPF insn index filter.";
    profiledListEl.appendChild(empty);
    return;
  }

  if (treeMode && app.currentFileData) {
    const rawCt = app.currentFileData.call_tree;
    if (!Array.isArray(rawCt) || !rawCt.length) {
      const note = document.createElement("div");
      note.className = "profiled-tree-unavailable";
      note.textContent = "No call tree for this file; showing a sorted list.";
      profiledListEl.appendChild(note);
    } else {
      const ct =
        Array.isArray(app.sortedCallTreeForDisplay) && app.sortedCallTreeForDisplay.length
          ? app.sortedCallTreeForDisplay
          : rawCt;
      profiledListEl.appendChild(renderCallTreeRows(ct, "", 0, null));
      return;
    }
  }

  for (let idx = 0; idx < app.profiledRanges.length; idx += 1) {
    profiledListEl.appendChild(makeProfiledRangeRow(app.profiledRanges[idx], idx));
  }
}

export function updateProfileNavUI() {
  const profileNavStatusEl = ui?.profileNavStatusEl;
  const prevProfiledBtnEl = ui?.prevProfiledBtnEl;
  const nextProfiledBtnEl = ui?.nextProfiledBtnEl;
  if (!profileNavStatusEl || !prevProfiledBtnEl || !nextProfiledBtnEl) {
    return;
  }
  const total = app.profiledRanges.length;
  if (!total) {
    profileNavStatusEl.textContent = "0 / 0";
    prevProfiledBtnEl.disabled = true;
    nextProfiledBtnEl.disabled = true;
    renderProfiledList();
    return;
  }
  profileNavStatusEl.textContent = `${app.currentProfiledRangeIndex + 1} / ${total}`;
  prevProfiledBtnEl.disabled = false;
  nextProfiledBtnEl.disabled = false;
  renderProfiledList();
}
