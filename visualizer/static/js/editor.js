import { fetchSource } from "./api.js";

/** @returns {Promise<typeof monaco>} */
function loadMonaco() {
  if (window.monacoReady) return window.monacoReady;

  window.monacoReady = new Promise((resolve, reject) => {
    const loader = document.createElement("script");
    loader.src =
      "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs/loader.js";
    loader.onload = () => {
      // eslint-disable-next-line no-undef
      require.config({
        paths: {
          vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs",
        },
      });
      // eslint-disable-next-line no-undef
      require(["vs/editor/editor.main"], () => {
        resolve(window.monaco);
      }, reject);
    };
    loader.onerror = () => reject(new Error("Failed to load Monaco Editor"));
    document.head.appendChild(loader);
  });

  return window.monacoReady;
}

/**
 * @param {HTMLElement} container
 * @param {{ pathLabel?: HTMLElement, statusLabel?: HTMLElement, onCursorLine?: (file: string, line: number) => void }} options
 */
export async function createSourceEditor(container, options = {}) {
  const labels = options;
  const monaco = await loadMonaco();

  const editor = monaco.editor.create(container, {
    value: "// Select a site in the call tree to view source\n",
    language: "c",
    theme: "vs-dark",
    readOnly: true,
    automaticLayout: true,
    minimap: { enabled: true },
    scrollBeyondLastLine: false,
    fontSize: 13,
    fontFamily: "'IBM Plex Mono', ui-monospace, monospace",
    lineNumbers: "on",
    renderLineHighlight: "all",
    folding: true,
    wordWrap: "off",
  });

  let currentPath = "";
  /** @type {Map<string, Set<number>>} */
  let siteIndex = new Map();
  let lastSelectedLine = 0;
  let siteDecorations = [];
  let selectedDecorations = [];
  let suppressCursorSelect = false;

  function setStatus(text, isError = false) {
    if (!labels.statusLabel) return;
    labels.statusLabel.textContent = text;
    labels.statusLabel.className = isError
      ? "text-xs text-rose-400 truncate"
      : "text-xs text-slate-500 truncate";
  }

  function setPathLabel(text) {
    if (!labels.pathLabel) return;
    labels.pathLabel.textContent = text;
    labels.pathLabel.title = text;
  }

  function applySiteDecorations(file, selectedLine, selectedEndLine = selectedLine) {
    const lines = siteIndex.get(file);
    if (!lines || lines.size === 0) {
      siteDecorations = editor.deltaDecorations(siteDecorations, []);
      return;
    }
    const selectedStart = Math.min(selectedLine, selectedEndLine);
    const selectedEnd = Math.max(selectedLine, selectedEndLine);

    const decorations = [];
    for (const lineNum of lines) {
      if (lineNum >= selectedStart && lineNum <= selectedEnd) continue;
      decorations.push({
        range: new monaco.Range(lineNum, 1, lineNum, 1),
        options: {
          isWholeLine: true,
          className: "profiled-site-line",
          linesDecorationsClassName: "profiled-site-gutter",
        },
      });
    }
    siteDecorations = editor.deltaDecorations(siteDecorations, decorations);
  }

  function applySelectedDecoration(lineNumber, endLineNumber = lineNumber) {
    const start = Math.min(lineNumber, endLineNumber);
    const end = Math.max(lineNumber, endLineNumber);
    selectedDecorations = editor.deltaDecorations(selectedDecorations, [
      {
        range: new monaco.Range(start, 1, end, 1),
        options: {
          isWholeLine: true,
          className: "profiled-line-highlight",
          linesDecorationsClassName: "profiled-line-gutter",
        },
      },
    ]);
  }

  function refreshLineHighlights(file, selectedLine, selectedEndLine = selectedLine) {
    lastSelectedLine = selectedLine;
    applySiteDecorations(file, selectedLine, selectedEndLine);
    applySelectedDecoration(selectedLine, selectedEndLine);
  }

  /**
   * @param {Map<string, Set<number>>} byFile
   */
  function setSiteIndex(byFile) {
    siteIndex = byFile;
    if (currentPath) {
      refreshLineHighlights(currentPath, lastSelectedLine);
    }
  }

  /**
   * @param {string} file
   * @param {number} lineNumber
   * @param {string} [symbol]
   */
  function highlightSelection(file, lineNumber, symbol = "", endLineNumber = lineNumber) {
    const lineLabel =
      endLineNumber !== lineNumber
        ? `${Math.min(lineNumber, endLineNumber)}:${Math.max(lineNumber, endLineNumber)}`
        : String(lineNumber);
    const symbolSuffix = symbol ? ` — ${symbol}` : "";
    setPathLabel(`${file}:${lineLabel}${symbolSuffix}`);
    refreshLineHighlights(file, lineNumber, endLineNumber);
    const siteCount = siteIndex.get(file)?.size ?? 0;
    const status =
      endLineNumber !== lineNumber
        ? `Lines ${lineLabel} · ${siteCount.toLocaleString()} profiled line(s) in file`
        : siteCount > 1
          ? `Line ${lineNumber.toLocaleString()} · ${siteCount} profiled sites in file`
          : `Line ${lineNumber.toLocaleString()}`;
    setStatus(status);
  }

  editor.onDidChangeCursorPosition((e) => {
    if (suppressCursorSelect || !currentPath) return;
    const line = e.position.lineNumber;
    const lines = siteIndex.get(currentPath);
    if (!lines?.has(line)) return;
    options.onCursorLine?.(currentPath, line);
  });

  /**
   * @param {string} file
   * @param {string|number} line
   * @param {string} [symbol]
   * @param {string|number} [endLine]
   */
  async function openAt(file, line, symbol = "", endLine = line) {
    const lineNumber = Math.max(1, parseInt(String(line), 10) || 1);
    const endLineNumber = Math.max(1, parseInt(String(endLine), 10) || lineNumber);
    setStatus("Loading source…");

    try {
      const needsFetch = file !== currentPath;
      const payload = needsFetch
        ? await fetchSource(file)
        : {
            path: file,
            content: editor.getModel()?.getValue() ?? "",
            language: editor.getModel()?.getLanguageId() ?? "c",
          };

      if (payload.error) {
        throw new Error(payload.error);
      }

      if (needsFetch) {
        currentPath = file;
        const uri = monaco.Uri.parse(
          `inmemory:///${payload.patch_rel || payload.path}`
        );
        let model = monaco.editor.getModel(uri);
        if (model) {
          model.dispose();
        }
        model = monaco.editor.createModel(
          payload.content,
          payload.language || "c",
          uri
        );
        editor.setModel(model);
      }

      suppressCursorSelect = true;
      editor.revealLineInCenter(lineNumber);
      editor.setPosition({ lineNumber, column: 1 });
      editor.focus();
      highlightSelection(file, lineNumber, symbol, endLineNumber);
      setTimeout(() => {
        suppressCursorSelect = false;
      }, 0);
    } catch (err) {
      setPathLabel(file ? `${file}:${lineNumber}` : "Source");
      setStatus(err.message || "Failed to load source", true);
    }
  }

  function clearSelection() {
    lastSelectedLine = 0;
    selectedDecorations = editor.deltaDecorations(selectedDecorations, []);
    if (currentPath) {
      applySiteDecorations(currentPath, 0);
      setPathLabel(currentPath);
      const siteCount = siteIndex.get(currentPath)?.size ?? 0;
      setStatus(
        siteCount > 0
          ? `${siteCount} profiled site(s) in file`
          : ""
      );
    } else {
      setPathLabel("—");
      setStatus("");
    }
  }

  return { editor, openAt, setSiteIndex, highlightSelection, clearSelection };
}
