import { formatNs } from "./formatting.js";
import { computeReferenceNs, rangeSamplesForCurrentArg, rangeTotalForCurrentArg } from "./ranges.js";
import { app, ui } from "./state.js";

function formatProfiledLocation(range) {
  if (range.function && String(range.function).trim()) {
    return { hasFn: true };
  }
  return { hasFn: false };
}

/**
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
    empty.textContent = "No profiled boxes for current arg filter.";
    profiledListEl.appendChild(empty);
    return;
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
