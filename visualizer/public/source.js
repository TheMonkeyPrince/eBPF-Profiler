function qs(name){
  const params = new URLSearchParams(window.location.search);
  return params.get(name);
}

function renderLines(lines, start, end){
  const container = document.getElementById('source');
  container.innerHTML = '';
  const pre = document.createElement('pre');
  pre.className = 'text-sm p-4';
  const wrap = document.createElement('div');
  wrap.className = 'font-mono text-xs';

  const s = start ? start : null;
  const e = end ? end : null;

  lines.forEach((line, idx) => {
    const num = idx + 1;
    const row = document.createElement('div');
    row.className = 'flex gap-4';
    const numCol = document.createElement('div');
    numCol.className = 'text-gray-500 w-16 text-right pr-4 select-none';
    numCol.textContent = num;
    const codeCol = document.createElement('div');
    codeCol.className = 'flex-1';
    codeCol.textContent = line;
    if (s && e && num >= s && num <= e) {
      row.style.background = 'rgba(255,235,205,0.6)';
    }
    row.appendChild(numCol);
    row.appendChild(codeCol);
    wrap.appendChild(row);
  });
  pre.appendChild(wrap);
  container.appendChild(pre);
}

async function load(){
  const path = qs('path');
  const start = qs('start');
  const end = qs('end');
  if (!path) { document.getElementById('title').textContent = 'No path specified'; return; }
  document.getElementById('title').textContent = path;
  document.getElementById('info').textContent = (start ? ('Highlighting ' + start + (end ? ('-' + end) : '')) : '');

  const qp = new URLSearchParams({ path });
  if (start) qp.set('start', start);
  if (end) qp.set('end', end);
  const res = await fetch('/api/source?' + qp.toString());
  const data = await res.json();
  if (data.error) { document.getElementById('source').textContent = data.error; return; }
  renderLines(data.lines || [], data.start, data.end);
}

load().catch(err => { document.getElementById('source').textContent = err.message; });
