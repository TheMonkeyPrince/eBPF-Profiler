const metaEl = document.getElementById("meta");
const treeEl = document.getElementById("tree");
const fileTitleEl = document.getElementById("fileTitle");
const monacoEditorEl = document.getElementById("monacoEditor");
const hoverDetailsEl = document.getElementById("hoverDetails");
const argFilterEl = document.getElementById("argFilter");
const reloadButtonEl = document.getElementById("reloadButton");
const themeToggleEl = document.getElementById("themeToggle");
const prevProfiledBtnEl = document.getElementById("prevProfiledBtn");
const nextProfiledBtnEl = document.getElementById("nextProfiledBtn");
const profileNavStatusEl = document.getElementById("profileNavStatus");
const toggleMetaBtnEl = document.getElementById("toggleMetaBtn");
const toggleDetailsBtnEl = document.getElementById("toggleDetailsBtn");
const profiledSortSelectEl = document.getElementById("profiledSortSelect");
const profiledListEl = document.getElementById("profiledList");

let selectedPath = null;
let selectedArg = "all";
let selectedTheme = "dark";
let monacoReady = null;
let editor = null;
let model = null;
let decorationIds = [];
let focusedRangeDecorationIds = [];
let currentFileData = null;
let lineRangesIndex = {};
let profiledRanges = [];
let currentProfiledRangeIndex = -1;
let profiledSortMode = "line";
let treeState = {};
let treeChildrenCache = {};
const HEAT_BUCKETS = 20;

function formatNs(ns) {
  return `${Number(ns).toLocaleString()} ns`;
}

function heatAlpha(totalNs, maxTotalNs) {
  if (!totalNs || !maxTotalNs) {
    return 0;
  }
  const score = Math.log1p(totalNs) / Math.log1p(maxTotalNs);
  return Math.min(0.85, Math.max(0.05, score));
}

function heatBucket(alpha) {
  if (!alpha || alpha <= 0) {
    return 0;
  }
  return Math.min(HEAT_BUCKETS, Math.max(1, Math.ceil(alpha * HEAT_BUCKETS)));
}

function overviewColor(bucket) {
  const palette = [
    "#00000000",
    "#ff500030",
    "#ff500045",
    "#ff500058",
    "#ff50006b",
    "#ff500080",
    "#ff500095",
    "#ff5000ad",
    "#ff5000c2",
    "#ff5000d6",
    "#ff5000eb",
    "#ff5000f2",
    "#ff5000f4",
    "#ff5000f6",
    "#ff5000f8",
    "#ff5000fa",
    "#ff5000fc",
    "#ff5000fd",
    "#ff5000fe",
    "#ff5000ff",
    "#ff3b00ff",
  ];
  return palette[bucket] || palette[HEAT_BUCKETS];
}

function formatSampleList(samples) {
  if (!samples || samples.length === 0) {
    return "[]";
  }
  const shown = samples.slice(0, 8).map((v) => Number(v).toLocaleString());
  if (samples.length > 8) {
    shown.push(`... +${samples.length - 8}`);
  }
  return `[${shown.join(", ")}]`;
}

function buildLineRangesIndex(data) {
  lineRangesIndex = {};
  const ranges = data.ranges || [];
  for (const range of ranges) {
    for (let line = range.start; line <= range.end; line += 1) {
      if (!lineRangesIndex[line]) {
        lineRangesIndex[line] = [];
      }
      lineRangesIndex[line].push(range);
    }
  }
}

function rangeSamplesForCurrentArg(range) {
  if (selectedArg === "all") {
    const combined = [...(range.no_arg || [])];
    for (const argSamples of Object.values(range.by_arg || {})) {
      combined.push(...argSamples);
    }
    return combined;
  }
  if (selectedArg === "__no_arg__") {
    return [...(range.no_arg || [])];
  }
  return [...((range.by_arg && range.by_arg[selectedArg]) || [])];
}

function rangeTotalForCurrentArg(range) {
  return rangeSamplesForCurrentArg(range).reduce((acc, value) => acc + value, 0);
}

function buildProfiledRanges(data) {
  const currentRange = profiledRanges[currentProfiledRangeIndex] || null;
  const ranges = (data.ranges || [])
    .filter((range) => rangeSamplesForCurrentArg(range).length > 0)
    .sort((a, b) => {
      if (profiledSortMode === "time") {
        const diff = rangeTotalForCurrentArg(b) - rangeTotalForCurrentArg(a);
        if (diff !== 0) {
          return diff;
        }
      }
      if (a.start !== b.start) {
        return a.start - b.start;
      }
      return a.end - b.end;
    });
  profiledRanges = ranges;
  if (!profiledRanges.length) {
    currentProfiledRangeIndex = -1;
  } else if (currentRange) {
    const idx = profiledRanges.findIndex((item) => item.start === currentRange.start && item.end === currentRange.end);
    currentProfiledRangeIndex = idx >= 0 ? idx : 0;
  } else if (currentProfiledRangeIndex < 0 || currentProfiledRangeIndex >= profiledRanges.length) {
    currentProfiledRangeIndex = 0;
  }
}

function renderProfiledList() {
  profiledListEl.innerHTML = "";
  if (!selectedPath) {
    const empty = document.createElement("div");
    empty.className = "profiled-item-empty";
    empty.textContent = "Open a file to list profiled boxes.";
    profiledListEl.appendChild(empty);
    return;
  }
  if (!profiledRanges.length) {
    const empty = document.createElement("div");
    empty.className = "profiled-item-empty";
    empty.textContent = "No profiled boxes for current arg filter.";
    profiledListEl.appendChild(empty);
    return;
  }

  profiledRanges.forEach((range, idx) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `profiled-item${idx === currentProfiledRangeIndex ? " active" : ""}`;
    const total = rangeTotalForCurrentArg(range);
    const count = rangeSamplesForCurrentArg(range).length;
    button.textContent = `L${range.start}-${range.end} | ${formatNs(total)} | ${count} samples`;
    button.addEventListener("click", async () => {
      await focusProfiledRange(idx, true);
    });
    profiledListEl.appendChild(button);
  });
}

function updateProfileNavUI() {
  const total = profiledRanges.length;
  if (!total) {
    profileNavStatusEl.textContent = "0 / 0";
    prevProfiledBtnEl.disabled = true;
    nextProfiledBtnEl.disabled = true;
    renderProfiledList();
    return;
  }
  profileNavStatusEl.textContent = `${currentProfiledRangeIndex + 1} / ${total}`;
  prevProfiledBtnEl.disabled = false;
  nextProfiledBtnEl.disabled = false;
  renderProfiledList();
}

async function focusProfiledRange(index, reveal = true) {
  if (!editor || !currentFileData || !profiledRanges.length) {
    return;
  }
  const monaco = await ensureMonaco();
  const total = profiledRanges.length;
  currentProfiledRangeIndex = ((index % total) + total) % total;
  const range = profiledRanges[currentProfiledRangeIndex];
  const monacoRange = new monaco.Range(range.start, 1, range.end, 1);

  focusedRangeDecorationIds = editor.deltaDecorations(focusedRangeDecorationIds, [
    {
      range: monacoRange,
      options: {
        isWholeLine: true,
        className: "focused-profiled-range",
      },
    },
  ]);

  if (reveal) {
    editor.revealLineInCenter(range.start);
    editor.setSelection(monacoRange);
  }
  updateProfileNavUI();
}

function updateHoverDetails(lineNo) {
  if (!currentFileData || !lineNo) {
    hoverDetailsEl.textContent = "Hover a line to see detailed profiling data.";
    return;
  }

  const stat = currentFileData.line_stats[lineNo] || {
    total_ns: 0,
    count: 0,
    avg_ns: 0,
    max_ns: 0,
  };
  const touching = lineRangesIndex[lineNo] || [];

  const header = [
    `Line ${lineNo} (${selectedArg === "all" ? "all args" : `arg=${selectedArg}`})`,
    `total=${formatNs(stat.total_ns)} | count=${stat.count} | avg=${formatNs(stat.avg_ns)} | max=${formatNs(stat.max_ns)}`,
  ];

  if (!touching.length) {
    hoverDetailsEl.textContent = `${header.join("\n")}\nNo profiling ranges touch this line.`;
    return;
  }

  const rangeLines = touching.slice(0, 6).map((range) => {
    let samples = [];
    if (selectedArg === "all") {
      samples = [...(range.no_arg || [])];
      for (const argSamples of Object.values(range.by_arg || {})) {
        samples.push(...argSamples);
      }
    } else if (selectedArg === "__no_arg__") {
      samples = [...(range.no_arg || [])];
    } else {
      samples = [...((range.by_arg && range.by_arg[selectedArg]) || [])];
    }
    const total = samples.reduce((acc, v) => acc + v, 0);
    const count = samples.length;
    const max = count ? Math.max(...samples) : 0;
    return `range ${range.start}-${range.end} | total=${formatNs(total)} | count=${count} | max=${formatNs(max)} | samples=${formatSampleList(samples)}`;
  });

  const hidden = touching.length > 6 ? `\n... ${touching.length - 6} more touching ranges` : "";
  hoverDetailsEl.textContent = `${header.join("\n")}\n${rangeLines.join("\n")}${hidden}`;
}

async function apiGet(path) {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`Request failed (${res.status}) for ${path}`);
  }
  return res.json();
}

function updateUrlState(replace = false) {
  const url = new URL(window.location.href);
  if (selectedPath) {
    url.searchParams.set("file", selectedPath);
  } else {
    url.searchParams.delete("file");
  }
  if (selectedArg && selectedArg !== "all") {
    url.searchParams.set("arg", selectedArg);
  } else {
    url.searchParams.delete("arg");
  }
  url.searchParams.set("theme", selectedTheme);

  if (replace) {
    history.replaceState(null, "", url);
  } else {
    history.pushState(null, "", url);
  }
}

function readUrlState() {
  const url = new URL(window.location.href);
  const maybeFile = url.searchParams.get("file");
  const maybeArg = url.searchParams.get("arg");
  const maybeTheme = url.searchParams.get("theme");
  if (maybeFile) {
    selectedPath = maybeFile;
  }
  if (maybeArg) {
    selectedArg = maybeArg;
  }
  if (maybeTheme === "light" || maybeTheme === "dark") {
    selectedTheme = maybeTheme;
  }
}

function applyTheme() {
  const isLight = selectedTheme === "light";
  document.body.classList.toggle("light-theme", isLight);
  if (themeToggleEl) {
    themeToggleEl.checked = isLight;
  }
  if (editor && monacoReady) {
    window.monaco.editor.setTheme(isLight ? "vs" : "vs-dark");
  }
}

function buildArgOptions(globalArgs) {
  argFilterEl.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = "all";
  argFilterEl.appendChild(allOption);

  const noArgOption = document.createElement("option");
  noArgOption.value = "__no_arg__";
  noArgOption.textContent = "no arg";
  argFilterEl.appendChild(noArgOption);

  for (const arg of globalArgs) {
    const option = document.createElement("option");
    option.value = arg;
    option.textContent = arg;
    argFilterEl.appendChild(option);
  }
  const knownValues = new Set(["all", "__no_arg__", ...globalArgs.map(String)]);
  if (!knownValues.has(selectedArg)) {
    selectedArg = "all";
  }
  argFilterEl.value = selectedArg;
}

async function loadConfig() {
  const config = await apiGet("/api/config");
  const warnings = config.load_error ? ` | warning: ${config.load_error}` : "";
  metaEl.textContent = [
    `program: ${config.program_name || "n/a"}`,
    `duration: ${formatNs(config.total_duration || 0)}`,
    `profiled files: ${config.profiled_files_count}`,
    `KERNEL_PATH: ${config.kernel_path}`,
    `REPORT_PATH: ${config.report_path}`,
  ].join(" | ") + warnings;
  buildArgOptions(config.global_args || []);
}

async function fetchTreeChildren(path) {
  if (!treeChildrenCache[path]) {
    treeChildrenCache[path] = await apiGet(`/api/tree?path=${encodeURIComponent(path)}`);
  }
  return treeChildrenCache[path];
}

async function ensureTreePathExpanded(filePath) {
  const parts = filePath.split("/");
  let current = "";
  for (let i = 0; i < parts.length - 1; i += 1) {
    current = current ? `${current}/${parts[i]}` : parts[i];
    treeState[current] = true;
    await fetchTreeChildren(current);
  }
}

function makeTreeNode(entry, depth) {
  const row = document.createElement("div");
  row.className = `explorer-row${!entry.is_dir && entry.path === selectedPath ? " active" : ""}`;
  row.style.paddingLeft = `${depth * 14 + 8}px`;

  const twisty = document.createElement("span");
  twisty.className = "explorer-twisty";
  if (entry.is_dir) {
    twisty.textContent = treeState[entry.path] ? "▾" : "▸";
  } else {
    twisty.textContent = "";
  }
  row.appendChild(twisty);

  const icon = document.createElement("span");
  icon.className = "explorer-icon";
  icon.textContent = entry.is_dir ? "📁" : "📄";
  row.appendChild(icon);

  const label = document.createElement("span");
  label.className = "explorer-label";
  label.textContent = entry.name;
  row.appendChild(label);

  row.addEventListener("click", async () => {
    if (entry.is_dir) {
      treeState[entry.path] = !treeState[entry.path];
      if (treeState[entry.path]) {
        await fetchTreeChildren(entry.path);
      }
      await renderTree();
      return;
    }
    selectedPath = entry.path;
    updateUrlState();
    await loadFile();
  });
  return row;
}

async function renderTree() {
  treeEl.innerHTML = "";
  const root = await fetchTreeChildren("");

  const renderEntries = async (entries, depth) => {
    for (const entry of entries) {
      treeEl.appendChild(makeTreeNode(entry, depth));
      if (entry.is_dir && treeState[entry.path]) {
        const child = await fetchTreeChildren(entry.path);
        await renderEntries(child.entries, depth + 1);
      }
    }
  };

  await renderEntries(root.entries, 0);
}

function ensureMonaco() {
  if (monacoReady) {
    return monacoReady;
  }
  monacoReady = new Promise((resolve, reject) => {
    if (!window.require) {
      reject(new Error("Monaco loader is missing"));
      return;
    }
    window.require.config({
      paths: {
        vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.2/min/vs",
      },
    });
    window.require(["vs/editor/editor.main"], () => resolve(window.monaco), reject);
  });
  return monacoReady;
}

async function ensureEditor() {
  const monaco = await ensureMonaco();
  if (editor) {
    return monaco;
  }
  editor = monaco.editor.create(monacoEditorEl, {
    value: "",
    language: "c",
    theme: selectedTheme === "light" ? "vs" : "vs-dark",
    readOnly: true,
    minimap: { enabled: true },
    scrollBeyondLastLine: false,
    automaticLayout: true,
    fontSize: 12,
    renderWhitespace: "selection",
  });
  editor.onMouseMove((event) => {
    if (!event.target.position) {
      return;
    }
    updateHoverDetails(event.target.position.lineNumber);
  });
  editor.onMouseLeave(() => {
    updateHoverDetails(null);
  });
  return monaco;
}

async function renderCode(data) {
  const monaco = await ensureEditor();
  if (!model) {
    model = monaco.editor.createModel("", "c");
    editor.setModel(model);
  }

  model.setValue(data.lines.join("\n"));
  monaco.editor.setModelLanguage(model, "c");
  currentFileData = data;
  buildLineRangesIndex(data);
  buildProfiledRanges(data);
  updateHoverDetails(null);

  const max = data.max_total_ns || 0;
  const nextDecorations = [];

  data.lines.forEach((_, idx) => {
    const lineNo = idx + 1;
    const stat = data.line_stats[lineNo] || {
      total_ns: 0,
      count: 0,
      avg_ns: 0,
      max_ns: 0,
    };
    const alpha = heatAlpha(stat.total_ns, max);
    const bucket = heatBucket(alpha);
    if (!bucket) {
      return;
    }
    nextDecorations.push({
      range: new monaco.Range(lineNo, 1, lineNo, 1),
      options: {
        isWholeLine: true,
        className: `heat-line-${bucket}`,
        linesDecorationsClassName: "hot-line-number",
        overviewRuler: {
          color: overviewColor(bucket),
          position: monaco.editor.OverviewRulerLane.Full,
        },
        stickiness: monaco.editor.TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges,
        hoverMessage: {
          value: [
            `line ${lineNo}`,
            `total: ${formatNs(stat.total_ns)}`,
            `count: ${stat.count}`,
            `avg: ${formatNs(stat.avg_ns)}`,
            `max sample: ${formatNs(stat.max_ns)}`,
          ].join(" | "),
        },
      },
    });
  });

  decorationIds = editor.deltaDecorations(decorationIds, nextDecorations);
  if (!profiledRanges.length) {
    focusedRangeDecorationIds = editor.deltaDecorations(focusedRangeDecorationIds, []);
    updateProfileNavUI();
    return;
  }
  await focusProfiledRange(currentProfiledRangeIndex, false);
}

async function loadFile() {
  if (!selectedPath) {
    return;
  }
  fileTitleEl.textContent = selectedPath;
  const data = await apiGet(
    `/api/file?path=${encodeURIComponent(selectedPath)}&arg=${encodeURIComponent(selectedArg)}`
  );
  await renderCode(data);
  await ensureTreePathExpanded(selectedPath);
  await renderTree();
}

reloadButtonEl.addEventListener("click", async () => {
  await apiGet("/api/reload");
  treeChildrenCache = {};
  await loadConfig();
  if (selectedPath) {
    await ensureTreePathExpanded(selectedPath);
    await renderTree();
  } else {
    await renderTree();
  }
  if (selectedPath) {
    await loadFile();
  }
});

profiledSortSelectEl.addEventListener("change", async (event) => {
  profiledSortMode = event.target.value === "time" ? "time" : "line";
  if (!currentFileData) {
    renderProfiledList();
    return;
  }
  buildProfiledRanges(currentFileData);
  if (!profiledRanges.length) {
    focusedRangeDecorationIds = editor.deltaDecorations(focusedRangeDecorationIds, []);
    updateProfileNavUI();
    return;
  }
  await focusProfiledRange(currentProfiledRangeIndex, false);
});

argFilterEl.addEventListener("change", async (ev) => {
  selectedArg = ev.target.value;
  updateUrlState();
  if (selectedPath) {
    await loadFile();
  }
});

prevProfiledBtnEl.addEventListener("click", async () => {
  await focusProfiledRange(currentProfiledRangeIndex - 1, true);
});

nextProfiledBtnEl.addEventListener("click", async () => {
  await focusProfiledRange(currentProfiledRangeIndex + 1, true);
});

themeToggleEl.addEventListener("change", () => {
  selectedTheme = themeToggleEl.checked ? "light" : "dark";
  applyTheme();
  updateUrlState();
});

toggleMetaBtnEl.addEventListener("click", () => {
  document.body.classList.toggle("show-meta");
});

toggleDetailsBtnEl.addEventListener("click", () => {
  document.body.classList.toggle("show-details");
});

async function boot() {
  readUrlState();
  await ensureEditor();
  applyTheme();
  await loadConfig();
  if (selectedPath) {
    await ensureTreePathExpanded(selectedPath);
  }
  await renderTree();
  updateUrlState(true);
  updateProfileNavUI();
  renderProfiledList();
  if (selectedPath) {
    await loadFile();
  }
}

boot().catch((err) => {
  metaEl.textContent = `Failed to initialize: ${err.message}`;
});
