import {
  formatDurationNs,
  formatPercent,
  formatCount,
  parseSiteKey,
  buildSiteParentMap,
} from "./format.js";
import { renderInstructionChart, destroyInstructionChart } from "./insn-chart.js";

/** @typedef {'total' | 'parent'} PercentScale */

/**
 * @param {object} node
 * @param {PercentScale} scale
 */
export function getSitePercent(node, scale) {
  if (scale === "parent") {
    return node.percent_of_parent ?? 0;
  }
  return node.percent_of_total ?? 0;
}

/**
 * @param {PercentScale} scale
 */
function percentColumnLabel(scale) {
  return scale === "parent" ? "% parent" : "% total";
}

/**
 * @param {Record<string, object>} siteTree
 * @returns {{ key: string, node: object, depth: number }[]}
 */
export function flattenSiteTree(siteTree, depth = 0) {
  const rows = [];
  for (const [key, node] of Object.entries(siteTree || {})) {
    rows.push({ key, node, depth });
    if (node.children && Object.keys(node.children).length) {
      rows.push(...flattenSiteTree(node.children, depth + 1));
    }
  }
  return rows;
}

/**
 * @param {HTMLElement} container
 * @param {Record<string, object>} siteTree
 * @param {(key: string, node: object) => void} onSelect
 * @param {{ percentScale?: PercentScale }} [options]
 * @returns {{ setPercentScale: (scale: PercentScale) => void }}
 */
export function renderSiteTree(container, siteTree, onSelect, options = {}) {
  let percentScale = options.percentScale ?? "total";
  const collapsed = new Set();
  let selectedKey = "";
  const parentMap = buildSiteParentMap(siteTree);

  function ancestorKeys(key) {
    const chain = [];
    let parent = parentMap.get(key) ?? null;
    while (parent) {
      chain.push(parent);
      parent = parentMap.get(parent) ?? null;
    }
    return chain;
  }

  function highlightRow(key) {
    tbody.querySelectorAll("tr").forEach((row) => {
      row.classList.toggle("bg-slate-800/80", row.dataset.siteKey === key);
    });
  }

  container.replaceChildren();
  const table = document.createElement("table");
  table.className = "w-full text-sm";

  const thead = document.createElement("thead");
  thead.className = "text-left text-slate-400 border-b border-slate-700";
  const headerRow = document.createElement("tr");
  headerRow.innerHTML = `
      <th class="py-2 pr-2 font-medium">Site</th>
      <th class="py-2 px-2 font-medium w-36 percent-col">% total</th>
      <th class="py-2 px-2 font-medium w-28 text-right">Inclusive</th>
      <th class="py-2 px-2 font-medium w-28 text-right">Exclusive</th>
      <th class="py-2 pl-2 font-medium w-24 text-right">Visits</th>
    `;
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  tbody.className = "divide-y divide-slate-800/80";

  function updatePercentHeader() {
    const col = headerRow.querySelector(".percent-col");
    if (col) col.textContent = percentColumnLabel(percentScale);
  }

  function renderLevel(tree, depth) {
    for (const [key, node] of Object.entries(tree || {})) {
      const hasChildren =
        node.children && Object.keys(node.children).length > 0;
      const isCollapsed = collapsed.has(key);

      const tr = document.createElement("tr");
      tr.className =
        "hover:bg-slate-800/60 cursor-pointer transition-colors group";
      tr.dataset.siteKey = key;
      if (key === selectedKey) {
        tr.classList.add("bg-slate-800/80");
      }

      const pct = getSitePercent(node, percentScale);
      const barWidth = Math.min(100, Math.max(0.15, pct));

      const { file, line, endLine, symbol } = parseSiteKey(key);
      const indent = depth * 16;
      const lineLabel = endLine ? `${line}:${endLine}` : line;
      const titleLabel = symbol || (endLine ? `lines ${lineLabel}` : file);

      tr.innerHTML = `
        <td class="py-1.5 pr-2 align-middle">
          <div class="flex items-start gap-1 min-w-0" style="padding-left:${indent}px">
            ${
              hasChildren
                ? `<button type="button" class="toggle shrink-0 w-5 h-5 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-700 text-xs leading-none" aria-label="Toggle">${isCollapsed ? "▸" : "▾"}</button>`
                : `<span class="w-5 shrink-0"></span>`
            }
            <div class="min-w-0">
              <div class="font-mono text-cyan-300/90 truncate" title="${escapeAttr(key)}">${escapeHtml(titleLabel)}</div>
              <div class="text-xs text-slate-500 truncate" title="${escapeAttr(file)}">${escapeHtml(file)}:${escapeHtml(lineLabel)}</div>
            </div>
          </div>
          <div class="mt-1 h-1 rounded-full bg-slate-800 overflow-hidden" style="margin-left:${indent + (hasChildren ? 24 : 20)}px">
            <div class="h-full rounded-full bg-gradient-to-r from-amber-600 to-rose-500" style="width:${barWidth}%"></div>
          </div>
        </td>
        <td class="py-1.5 px-2 align-middle tabular-nums text-amber-200/90">${formatPercent(pct)}</td>
        <td class="py-1.5 px-2 align-middle text-right tabular-nums text-slate-300">${formatDurationNs(node.inclusive_duration)}</td>
        <td class="py-1.5 px-2 align-middle text-right tabular-nums text-slate-400">${formatDurationNs(node.exclusive_duration)}</td>
        <td class="py-1.5 pl-2 align-middle text-right tabular-nums text-slate-400">${formatCount(node.nb_visits)}</td>
      `;

      tr.addEventListener("click", (e) => {
        if (e.target.closest(".toggle")) return;
        selectedKey = key;
        highlightRow(key);
        onSelect(key, node);
      });

      const toggle = tr.querySelector(".toggle");
      if (toggle) {
        toggle.addEventListener("click", (e) => {
          e.stopPropagation();
          if (collapsed.has(key)) collapsed.delete(key);
          else collapsed.add(key);
          rerender();
        });
      }

      tbody.appendChild(tr);

      if (hasChildren && !isCollapsed) {
        renderLevel(node.children, depth + 1);
      }
    }
  }

  function rerender() {
    updatePercentHeader();
    tbody.replaceChildren();
    renderLevel(siteTree, 0);
  }

  rerender();
  table.appendChild(tbody);
  container.appendChild(table);

  /**
   * @param {string} key
   * @param {{ scroll?: boolean }} [opts]
   */
  function selectSite(key, opts = {}) {
    if (!parentMap.has(key)) return;
    for (const anc of ancestorKeys(key)) {
      collapsed.delete(anc);
    }
    selectedKey = key;
    rerender();
    if (opts.scroll !== false) {
      requestAnimationFrame(() => {
        const row = tbody.querySelector(
          `tr[data-site-key="${CSS.escape(key)}"]`
        );
        row?.scrollIntoView({ block: "nearest", behavior: "smooth" });
        highlightRow(key);
      });
    }
  }

  function clearSelection() {
    selectedKey = "";
    highlightRow("");
  }

  return {
    setPercentScale(scale) {
      percentScale = scale;
      rerender();
    },
    selectSite,
    clearSelection,
  };
}

/**
 * @param {HTMLElement} container
 * @param {string} siteKey
 * @param {object} node
 * @param {PercentScale} [activeScale]
 */
export function renderSiteDetail(container, siteKey, node, activeScale) {
  destroyInstructionChart();
  container.replaceChildren();
  if (!node) {
    container.innerHTML =
      '<p class="text-slate-500 text-sm">Select a site in the call tree.</p>';
    return;
  }

  const { file, line, endLine, symbol } = parseSiteKey(siteKey);
  const lineLabel = endLine ? `${line}:${endLine}` : line;
  const titleLabel = symbol || (endLine ? `lines ${lineLabel}` : siteKey);
  const header = document.createElement("div");
  header.className = "mb-4";
  header.innerHTML = `
    <h3 class="text-lg font-semibold text-slate-100 font-mono">${escapeHtml(titleLabel)}</h3>
    <p class="text-sm text-slate-400 font-mono break-all">${escapeHtml(file)}:${escapeHtml(lineLabel)}</p>
  `;
  container.appendChild(header);

  const statsGrid = document.createElement("dl");
  statsGrid.className = "grid grid-cols-2 gap-x-4 gap-y-2 text-sm mb-6";
  const totalLabel =
    activeScale === "total" ? "% of total (bar scale)" : "% of total";
  const parentLabel =
    activeScale === "parent" ? "% of parent (bar scale)" : "% of parent";
  const entries = [
    [totalLabel, formatPercent(node.percent_of_total)],
    [parentLabel, formatPercent(node.percent_of_parent)],
    ["Inclusive", formatDurationNs(node.inclusive_duration)],
    ["Exclusive", formatDurationNs(node.exclusive_duration)],
    ["Visits", formatCount(node.nb_visits)],
    ["Avg / visit", formatDurationNs(node.avg_duration_per_visit)],
  ];
  if (node.nb_insn_types != null) {
    entries.push(["BPF insn types", formatCount(node.nb_insn_types)]);
    entries.push([
      "Avg / insn type",
      formatDurationNs(node.avg_duration_per_insn_type),
    ]);
    const insnStddev = node.instruction_types?.stddev_duration;
    if (Number.isFinite(insnStddev)) {
      entries.push(["Stddev / insn type", formatDurationNs(insnStddev)]);
    }
  }
  for (const [label, value] of entries) {
    statsGrid.innerHTML += `<dt class="text-slate-500">${label}</dt><dd class="text-slate-200 tabular-nums text-right">${value}</dd>`;
  }
  container.appendChild(statsGrid);

  if (node.instruction_types?.stats) {
    const title = document.createElement("h4");
    title.className = "text-sm font-medium text-slate-300 mb-1";
    title.textContent = "Instruction types (relative score)";
    container.appendChild(title);
    const insnTypes = node.instruction_types;
    if (Number.isFinite(insnTypes.stddev_duration)) {
      const summary = document.createElement("p");
      summary.className = "text-xs text-slate-500 mb-3 tabular-nums";
      summary.textContent = `Across ${formatCount(node.nb_insn_types ?? Object.keys(insnTypes.stats).length)} types: avg ${formatDurationNs(insnTypes.avg_duration)} · σ ${formatDurationNs(insnTypes.stddev_duration)}`;
      container.appendChild(summary);
    }

    const chartHost = document.createElement("div");
    chartHost.className = "mb-4";
    container.appendChild(chartHost);
    renderInstructionChart(chartHost, node.instruction_types);

    const list = document.createElement("div");
    list.className = "space-y-2";
    const insnStats = node.instruction_types.stats;
    const sorted = Object.entries(insnStats).sort(
      (a, b) => (b[1].score ?? 0) - (a[1].score ?? 0)
    );
    for (const [insn, stat] of sorted) {
      const score = stat.score ?? 0;
      const row = document.createElement("div");
      row.innerHTML = `
        <div class="flex justify-between text-xs mb-0.5">
          <span class="font-mono text-violet-300">${escapeHtml(insn)}</span>
          <span class="text-slate-400 tabular-nums">${formatPercent(score)} · ${formatDurationNs(stat.avg_duration)} · ${formatCount(stat.count)}×</span>
        </div>
        <div class="h-1.5 rounded-full bg-slate-800 overflow-hidden">
          <div class="h-full rounded-full bg-violet-500/80" style="width:${Math.min(100, score)}%"></div>
        </div>`;
      list.appendChild(row);
    }
    container.appendChild(list);
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, "&quot;");
}
