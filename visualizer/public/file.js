function qs(name){
  const params = new URLSearchParams(window.location.search);
  return params.get(name);
}

function colorFor(value, max) {
  if (!max || max <= 0) return 'hsl(120,70%,85%)';
  const ratio = Math.min(1, value / max);
  const hue = 120 - Math.round(120 * ratio);
  return `hsl(${hue},70%,80%)`;
}

function createRow(key, value, bg) {
  const div = document.createElement('div');
  div.className = 'py-1 flex justify-between items-center border-b last:border-b-0';
  div.style.background = bg;
  const left = document.createElement('div');
  left.className = 'text-sm text-gray-800';
  left.textContent = key;
  const right = document.createElement('div');
  right.className = 'text-sm text-gray-600';
  right.textContent = value;
  div.appendChild(left);
  div.appendChild(right);
  return div;
}

async function load() {
  const name = qs('name');
  if (!name) { document.getElementById('title').textContent = 'No file specified'; return; }
  document.getElementById('title').textContent = name;
  const res = await fetch('/api/file/' + encodeURIComponent(name));
  const data = await res.json();
  document.getElementById('raw').textContent = JSON.stringify(data, null, 2);

  const summary = document.getElementById('summary');
  summary.innerHTML = '';
  summary.appendChild(createRow('Program', data.program_name || '—', 'transparent'));
  summary.appendChild(createRow('Total duration', data.total_duration || 0, 'transparent'));

  const exec = data.execution_times || {};
  const entries = Object.entries(exec).map(([k,v])=>{
    const sum = Array.isArray(v) ? v.reduce((a,b)=>a+b,0) : v;
    return [k, sum];
  });

  const profiledSum = entries.reduce((a,[_k,v])=>a+v,0);
  const totalDuration = data.total_duration || profiledSum || 1;

  function parseKey(k){
    // expected format: "path/to/file.c:start-end" or "path/to/file.c:start"
    const idx = k.indexOf(':');
    if (idx === -1) return { file: k, start: null, end: null };
    const file = k.slice(0, idx);
    const range = k.slice(idx+1);
    const parts = range.split('-');
    const start = parts[0] ? parseInt(parts[0],10) : null;
    const end = parts[1] ? parseInt(parts[1],10) : start;
    return { file, start, end };
  }

  function renderTable(){
    const only = document.getElementById('onlyProfiled').checked;
    const mode = document.querySelector('input[name="mode"]:checked').value;
    const baseMax = mode === 'total' ? totalDuration : profiledSum || totalDuration;
    const container = document.getElementById('tableContainer');
    container.innerHTML = '';
    const header = document.createElement('div');
    header.className = 'text-sm text-gray-500 mb-2';
    header.textContent = 'Profiled lines (click filename to open source)';
    container.appendChild(header);

    const list = document.createElement('div');
    entries.forEach(([k,v])=>{
      const bg = colorFor(v, baseMax);
      const parsed = parseKey(k);
      const row = document.createElement('div');
      row.className = 'py-1 flex justify-between items-center border-b last:border-b-0';
      row.style.background = bg;

      const left = document.createElement('div');
      left.className = 'text-sm text-gray-800 flex gap-2 items-center';
      const fileLabel = document.createElement('a');
      fileLabel.className = 'text-blue-600 hover:underline';
      if (parsed.file) {
        const qs = new URLSearchParams({ path: parsed.file });
        if (parsed.start) qs.set('start', parsed.start);
        if (parsed.end) qs.set('end', parsed.end);
        fileLabel.href = '/source?'+qs.toString();
        fileLabel.target = '_blank';
        fileLabel.textContent = parsed.file + ':' + (parsed.start || '') + (parsed.end ? ('-' + parsed.end) : '');
      } else {
        fileLabel.textContent = k;
      }
      left.appendChild(fileLabel);

      const right = document.createElement('div');
      right.className = 'text-sm text-gray-600';
      right.textContent = v;

      row.appendChild(left);
      row.appendChild(right);
      list.appendChild(row);
    });
    container.appendChild(list);
  }

  document.getElementById('onlyProfiled').addEventListener('change', renderTable);
  Array.from(document.querySelectorAll('input[name="mode"]')).forEach(r=>r.addEventListener('change', renderTable));
  document.getElementById('toggleRaw').addEventListener('click', ()=>{
    const raw = document.getElementById('raw');
    raw.style.display = raw.style.display === 'none' ? 'block' : 'none';
  });

  renderTable();
}

load().catch(err=>{ document.body.textContent = err.message; });
