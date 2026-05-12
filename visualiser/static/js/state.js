/** @typedef {{ metaEl: HTMLElement, treeEl: HTMLElement, fileTitleEl: HTMLElement, monacoEditorEl: HTMLElement, hoverDetailsEl: HTMLElement, copyDetailsBtnEl: HTMLElement, argFilterEl: HTMLSelectElement, scaleModeSelectEl: HTMLSelectElement, reloadButtonEl: HTMLButtonElement, reportSelectEl: HTMLSelectElement | null, themeToggleEl: HTMLInputElement, prevProfiledBtnEl: HTMLButtonElement, nextProfiledBtnEl: HTMLButtonElement, profileNavStatusEl: HTMLElement, toggleMetaBtnEl: HTMLButtonElement, toggleDetailsBtnEl: HTMLButtonElement, profiledSortSelectEl: HTMLSelectElement, profiledViewSelectEl: HTMLSelectElement | null, profiledListEl: HTMLElement, bpfDisasmPreEl: HTMLElement | null, bpfProgramDetailsEl: HTMLDetailsElement | null }} UiRefs */

export const HEAT_BUCKETS = 20;

/** @type {UiRefs | null} */
export let ui = null;

/** @param {UiRefs} refs */
export function bindUi(refs) {
  ui = refs;
}

export const app = {
  selectedPath: /** @type {string | null} */ (null),
  selectedArg: "all",
  selectedScaleMode: "profiled",
  selectedTheme: "dark",
  /** @type {Promise<unknown> | null} */
  monacoReady: null,
  /** @type {import('monaco-editor').editor.IStandaloneCodeEditor | null} */
  editor: null,
  /** @type {import('monaco-editor').editor.ITextModel | null} */
  model: null,
  decorationIds: /** @type {string[]} */ ([]),
  focusedRangeDecorationIds: /** @type {string[]} */ ([]),
  currentFileData: /** @type {null | { lines: string[], line_stats: Record<number, unknown>, ranges?: unknown[] }} */ (null),
  /** @type {Record<number, unknown[]>} */
  lineRangesIndex: {},
  profiledRanges: /** @type {unknown[]} */ ([]),
  currentProfiledRangeIndex: -1,
  profiledSortMode: "line",
  profiledViewMode: "list",
  /** Collapsed when false; missing = expanded */
  profiledTreeExpanded: /** @type {Record<number, boolean>} */ ({}),
  treeState: /** @type {Record<string, boolean>} */ ({}),
  treeChildrenCache: /** @type {Record<string, unknown>} */ ({}),
  totalDurationNs: 0,
  lastDetailsText: "Hover a line to see detailed profiling data.",
};
