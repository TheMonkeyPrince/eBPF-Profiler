import { formatCount, formatPercent } from "./format.js";

/**
 * @typedef {{ count: number, percent: number }} InsnStat
 */

/**
 * @param {HTMLElement} container
 * @param {Record<string, InsnStat>} stats
 * @param {{ emptyMessage?: string }} [options]
 */
export function renderInsnTable(container, stats, options = {}) {
  container.replaceChildren();
  if (!stats || !Object.keys(stats).length) {
    container.innerHTML = `<p class="text-slate-500 text-sm">${
      options.emptyMessage ?? "No instruction data."
    }</p>`;
    return;
  }

  const rows = Object.entries(stats)
    .map(([name, stat]) => ({
      name,
      count: stat.count ?? 0,
      percent: stat.percent ?? 0,
    }))
    .sort((a, b) => b.count - a.count);

  const table = document.createElement("table");
  table.className = "w-full text-sm";
  table.innerHTML = `
    <thead class="text-left text-slate-400 border-b border-slate-700">
      <tr>
        <th class="py-2 font-medium">Instruction</th>
        <th class="py-2 px-2 font-medium text-right w-24">Count</th>
        <th class="py-2 pl-2 font-medium text-right w-32">% of program</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-slate-800/80"></tbody>`;

  const tbody = table.querySelector("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.className = "hover:bg-slate-800/40";
    const barPct = Math.min(100, Math.max(0, row.percent));
    tr.innerHTML = `
      <td class="py-2 pr-2">
        <span class="font-mono text-emerald-300/90">${escapeHtml(row.name)}</span>
        <div class="mt-1 h-1 rounded-full bg-slate-800 overflow-hidden max-w-xs">
          <div class="h-full rounded-full bg-emerald-500/70" style="width:${barPct}%"></div>
        </div>
      </td>
      <td class="py-2 px-2 text-right tabular-nums text-slate-400">${formatCount(row.count)}</td>
      <td class="py-2 pl-2 text-right tabular-nums text-slate-200">${formatPercent(row.percent)}</td>`;
    tbody.appendChild(tr);
  }

  container.appendChild(table);
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
