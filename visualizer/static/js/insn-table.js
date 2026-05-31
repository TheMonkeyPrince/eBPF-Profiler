import { formatDurationNs, formatCount } from "./format.js";

/**
 * durations_per_insn_type: { name: [count, total_ns, avg_ns] }
 * @param {HTMLElement} container
 * @param {Record<string, [number, number, number]>} durations
 */
export function renderInsnTable(container, durations) {
  container.replaceChildren();
  if (!durations || !Object.keys(durations).length) {
    container.innerHTML =
      '<p class="text-slate-500 text-sm">No per-instruction timing data.</p>';
    return;
  }

  const rows = Object.entries(durations).map(([name, tuple]) => {
    const [count, total, avg] = tuple;
    return { name, count, total, avg };
  });
  const maxAvg = Math.max(...rows.map((r) => r.avg));

  const table = document.createElement("table");
  table.className = "w-full text-sm";
  table.innerHTML = `
    <thead class="text-left text-slate-400 border-b border-slate-700">
      <tr>
        <th class="py-2 font-medium">Instruction</th>
        <th class="py-2 px-2 font-medium text-right w-24">Count</th>
        <th class="py-2 px-2 font-medium text-right w-32">Total</th>
        <th class="py-2 pl-2 font-medium text-right w-32">Avg</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-slate-800/80"></tbody>`;

  const tbody = table.querySelector("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.className = "hover:bg-slate-800/40";
    const barPct = maxAvg > 0 ? (row.avg / maxAvg) * 100 : 0;
    tr.innerHTML = `
      <td class="py-2 pr-2">
        <span class="font-mono text-emerald-300/90">${escapeHtml(row.name)}</span>
        <div class="mt-1 h-1 rounded-full bg-slate-800 overflow-hidden max-w-xs">
          <div class="h-full rounded-full bg-emerald-500/70" style="width:${barPct}%"></div>
        </div>
      </td>
      <td class="py-2 px-2 text-right tabular-nums text-slate-400">${formatCount(row.count)}</td>
      <td class="py-2 px-2 text-right tabular-nums text-slate-300">${formatDurationNs(row.total)}</td>
      <td class="py-2 pl-2 text-right tabular-nums text-slate-200">${formatDurationNs(row.avg)}</td>`;
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
