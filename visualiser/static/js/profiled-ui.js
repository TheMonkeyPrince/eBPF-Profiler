import { formatNs } from "./formatting.js";
import {
  buildProfiledContainmentTree,
  computeReferenceNs,
  rangeSamplesForCurrentArg,
  rangeTotalForCurrentArg,
} from "./ranges.js";
import { app, ui } from "./state.js";
import { updateUrlState } from "./url.js";

function profiledTreeNodeExpanded(idx) {
  return app.profiledTreeExpanded[idx] !== false;
}

function formatProfiledLocation(range) {
  const loc = `L${range.start}-${range.end}`;
  if (range.function && String(range.function).trim()) {
    return { hasFn: true };
  }
  return { hasFn: false };
}

/**
 * Primary label (line + optional function) + stats line for explorer-style rows.
 * @param {HTMLElement} labelEl
 * @param {any} range
 */
function fillProfiledLabelPrimary(labelEl, range) {
  labelEl.textContent = "";
  const total = rangeTotalForCurrentArg(range);
  const referenceNs = app.currentFileData ? computeReferenceNs(app.currentFileData) : 0;
  const ratio = referenceNs ? (total / referenceNs) * 100 : 0;
  const count = rangeSamplesForCurrentArg(range).length;
  const loc = formatProfiledLocation(range);
  if (loc.hasFn) {
    const spanLoc = document.createElement("span");
    spanLoc.className = "profiled-loc";
    spanLoc.textContent = `L${range.start}-${range.end}`;
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
        `L${range.start}-${range.end}  ·  ${formatNs(total)}  ·  ${ratio.toFixed(1)}%  ·  ${count} samples`,
      ),
    );
  }
}

/**
 * VS Code–style row: chevron button (toggle) + label (select). No nested buttons.
 */
function makeProfiledExplorerRow(range, idx, depth, hasChildren, expanded, onToggleExpand) {
  const row = document.createElement("div");
  row.className = `explorer-row profiled-range-row${idx === app.currentProfiledRangeIndex ? " active" : ""}`;
  row.dataset.rangeIndex = String(idx);
  row.style.paddingLeft = `${8 + depth * 12}px`;

  const chev = document.createElement("button");
  chev.type = "button";
  chev.className = "explorer-chevron profiled-range-chevron";
  if (hasChildren) {
    chev.textContent = expanded ? "▾" : "▸";
    chev.setAttribute("aria-expanded", String(expanded));
    chev.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      onToggleExpand();
    });
  } else {
    chev.classList.add("placeholder");
    chev.disabled = true;
    chev.setAttribute("aria-hidden", "true");
  }

  const label = document.createElement("div");
  label.className = "profiled-range-label";
  fillProfiledLabelPrimary(label, range);

  row.appendChild(chev);
  row.appendChild(label);

  row.addEventListener("click", async (e) => {
    if (e.target.closest(".profiled-range-chevron")) {
      return;
    }
    const { focusProfiledRange } = await import("./editor.js");
    await focusProfiledRange(idx, true);
  });

  return row;
}

function ensureAncestorsExpanded(parentIdx, activeIdx) {
  let i = activeIdx;
  while (parentIdx[i] >= 0) {
    const p = parentIdx[i];
    app.profiledTreeExpanded[p] = true;
    i = p;
  }
}

export function renderProfiledList() {
  const profiledListEl = ui?.profiledListEl;
  if (!profiledListEl) {
    return;
  }
  profiledListEl.innerHTML = "";
  if (!app.selectedPath) {
    profiledListEl.classList.remove("profiled-list--tree");
    const empty = document.createElement("div");
    empty.className = "profiled-item-empty";
    empty.textContent = "Open a file to list profiled boxes.";
    profiledListEl.appendChild(empty);
    return;
  }
  if (!app.profiledRanges.length) {
    profiledListEl.classList.remove("profiled-list--tree");
    const empty = document.createElement("div");
    empty.className = "profiled-item-empty";
    empty.textContent = "No profiled boxes for current arg filter.";
    profiledListEl.appendChild(empty);
    return;
  }

  let layoutTree = app.profiledViewMode === "tree";
  /** @type {{ roots: number[], children: number[][], parentIdx: number[] } | null} */
  let treeData = null;
  if (layoutTree) {
    try {
      treeData = buildProfiledContainmentTree(app.profiledRanges);
    } catch (err) {
      console.error("profiled tree layout failed", err);
      layoutTree = false;
      app.profiledViewMode = "list";
      const sel = document.getElementById("profiledViewSelect");
      if (sel instanceof HTMLSelectElement) {
        sel.value = "list";
      }
      updateUrlState();
    }
  }

  profiledListEl.classList.toggle("profiled-list--tree", layoutTree);

  if (layoutTree && treeData) {
    const { roots, children, parentIdx } = treeData;
    if (app.currentProfiledRangeIndex >= 0) {
      ensureAncestorsExpanded(parentIdx, app.currentProfiledRangeIndex);
    }

    const renderNode = (idx, depth) => {
      const ch = children[idx];
      const hasChildren = ch.length > 0;
      const expanded = profiledTreeNodeExpanded(idx);
      const range = app.profiledRanges[idx];
      const row = makeProfiledExplorerRow(range, idx, depth, hasChildren, expanded, () => {
        app.profiledTreeExpanded[idx] = !profiledTreeNodeExpanded(idx);
        renderProfiledList();
      });
      profiledListEl.appendChild(row);

      if (hasChildren && expanded) {
        for (const c of ch) {
          renderNode(c, depth + 1);
        }
      }
    };
    for (const r of roots) {
      renderNode(r, 0);
    }
    return;
  }

  for (let idx = 0; idx < app.profiledRanges.length; idx += 1) {
    const range = app.profiledRanges[idx];
    const row = makeProfiledExplorerRow(range, idx, 0, false, true, () => {});
    profiledListEl.appendChild(row);
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
