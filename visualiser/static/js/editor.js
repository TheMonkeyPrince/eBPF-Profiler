import { apiGet } from "./api.js";
import { updateHoverDetails } from "./details.js";
import { ensureTreePathExpanded, renderTree } from "./explorer.js";
import { formatNs, heatAlpha, heatBucket, overviewColor } from "./formatting.js";
import {
  buildLineRangesIndex,
  buildProfiledRanges,
  computeReferenceNs,
  lineSampleStats,
} from "./ranges.js";
import { app, ui } from "./state.js";
import { updateProfileNavUI } from "./profiled-ui.js";

export function ensureMonaco() {
  if (app.monacoReady) {
    return app.monacoReady;
  }
  app.monacoReady = new Promise((resolve, reject) => {
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
  return app.monacoReady;
}

export async function ensureEditor() {
  const monaco = await ensureMonaco();
  if (app.editor) {
    return monaco;
  }
  const monacoEditorEl = ui?.monacoEditorEl;
  if (!monacoEditorEl) {
    throw new Error("Monaco container missing");
  }
  app.editor = monaco.editor.create(monacoEditorEl, {
    value: "",
    language: "c",
    theme: app.selectedTheme === "light" ? "vs" : "vs-dark",
    readOnly: true,
    minimap: { enabled: true },
    glyphMargin: true,
    scrollBeyondLastLine: false,
    automaticLayout: true,
    fontSize: 12,
    renderWhitespace: "selection",
  });
  app.editor.onDidChangeCursorPosition((event) => {
    if (!event.position) {
      return;
    }
    updateHoverDetails(event.position.lineNumber);
  });
  return monaco;
}

export async function focusProfiledRange(index, reveal = true) {
  if (!app.editor || !app.currentFileData || !app.profiledRanges.length) {
    return;
  }
  const monaco = await ensureMonaco();
  const total = app.profiledRanges.length;
  app.currentProfiledRangeIndex = ((index % total) + total) % total;
  const range = app.profiledRanges[app.currentProfiledRangeIndex];
  const monacoRange = new monaco.Range(range.start, 1, range.end, 1);

  app.focusedRangeDecorationIds = app.editor.deltaDecorations(app.focusedRangeDecorationIds, [
    {
      range: monacoRange,
      options: {
        isWholeLine: true,
        className: "focused-profiled-range",
        linesDecorationsClassName: "focused-profiled-line-number",
        glyphMarginClassName: "focused-profiled-glyph",
        overviewRuler: {
          color: "#ffe066",
          position: monaco.editor.OverviewRulerLane.Center,
        },
      },
    },
  ]);

  if (reveal) {
    app.editor.revealLineInCenter(range.start);
    app.editor.setSelection(monacoRange);
  }
  updateProfileNavUI();
}

export async function renderCode(data) {
  const monaco = await ensureEditor();
  if (!app.model) {
    app.model = monaco.editor.createModel("", "c");
    app.editor.setModel(app.model);
  }

  app.model.setValue(data.lines.join("\n"));
  monaco.editor.setModelLanguage(app.model, "c");
  app.currentFileData = data;
  buildLineRangesIndex(data);
  buildProfiledRanges(data);
  const cursorLine = app.editor && app.editor.getPosition() ? app.editor.getPosition().lineNumber : 1;
  updateHoverDetails(cursorLine);

  const referenceNs = computeReferenceNs(data);
  const nextDecorations = [];

  data.lines.forEach((_, idx) => {
    const lineNo = idx + 1;
    const stat = data.line_stats[lineNo] || {
      total_ns: 0,
      count: 0,
      avg_ns: 0,
      max_ns: 0,
    };
    const alpha = heatAlpha(stat.total_ns, referenceNs);
    const bucket = heatBucket(alpha);
    const lineStats = lineSampleStats(lineNo);
    const share = referenceNs ? (stat.total_ns / referenceNs) * 100 : 0;
    const touch = app.lineRangesIndex[lineNo] || [];
    const hoverFns = [];
    for (const r of touch) {
      if (r.function && String(r.function).trim()) {
        const s = String(r.function).trim();
        if (!hoverFns.includes(s)) {
          hoverFns.push(s);
        }
      }
    }
    const fnHover = hoverFns.length ? ` | ${hoverFns.join(", ")}` : "";
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
            `line ${lineNo}${fnHover}`,
            `total: ${formatNs(stat.total_ns)}`,
            `share: ${share.toFixed(2)}% (${app.selectedScaleMode})`,
            `count: ${lineStats.count}`,
            `min: ${formatNs(lineStats.min)}`,
            `max: ${formatNs(lineStats.max)}`,
            `avg: ${formatNs(lineStats.avg)}`,
            `med: ${formatNs(lineStats.med)}`,
          ].join(" | "),
        },
      },
    });
  });

  app.decorationIds = app.editor.deltaDecorations(app.decorationIds, nextDecorations);
  if (!app.profiledRanges.length) {
    app.focusedRangeDecorationIds = app.editor.deltaDecorations(app.focusedRangeDecorationIds, []);
    updateProfileNavUI();
    return;
  }
  await focusProfiledRange(app.currentProfiledRangeIndex, false);
}

export async function loadFile() {
  if (!app.selectedPath) {
    return;
  }
  const fileTitleEl = ui?.fileTitleEl;
  const hoverDetailsEl = ui?.hoverDetailsEl;
  if (fileTitleEl) {
    fileTitleEl.textContent = app.selectedPath;
  }
  try {
    const data = await apiGet(
      `/api/file?path=${encodeURIComponent(app.selectedPath)}&arg=${encodeURIComponent(app.selectedArg)}`,
    );
    await renderCode(data);
    await ensureTreePathExpanded(app.selectedPath);
    await renderTree();
  } catch (err) {
    console.error(err);
    if (fileTitleEl) {
      fileTitleEl.textContent = `${app.selectedPath} (failed to load source)`;
    }
    app.lastDetailsText = err.message || String(err);
    if (hoverDetailsEl) {
      hoverDetailsEl.textContent = app.lastDetailsText;
    }
  }
}

export function applyTheme() {
  const isLight = app.selectedTheme === "light";
  document.body.classList.toggle("light-theme", isLight);
  if (ui?.themeToggleEl) {
    ui.themeToggleEl.checked = isLight;
  }
  if (app.editor && app.monacoReady) {
    window.monaco.editor.setTheme(isLight ? "vs" : "vs-dark");
  }
}
