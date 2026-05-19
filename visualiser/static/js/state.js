/** @typedef {{ metaEl: HTMLElement, treeEl: HTMLElement, fileTitleEl: HTMLElement, monacoEditorEl: HTMLElement, hoverDetailsEl: HTMLElement, copyDetailsBtnEl: HTMLElement, argFilterEl: HTMLSelectElement, scaleModeSelectEl: HTMLSelectElement, reloadButtonEl: HTMLButtonElement, reportSelectEl: HTMLSelectElement | null, themeToggleEl: HTMLInputElement, prevProfiledBtnEl: HTMLButtonElement, nextProfiledBtnEl: HTMLButtonElement, profileNavStatusEl: HTMLElement, toggleMetaBtnEl: HTMLButtonElement, toggleDetailsBtnEl: HTMLButtonElement, profiledSortSelectEl: HTMLSelectElement, profiledDisplaySelectEl: HTMLSelectElement, profiledListEl: HTMLElement, bpfDisasmPreEl: HTMLElement | null, bpfProgramDetailsEl: HTMLDetailsElement | null, bpfInsnFileFilterEl: HTMLSelectElement | null, bpfInsnScaleSelectEl: HTMLSelectElement | null }} UiRefs */

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
  currentFileData: /** @type {null | { lines: string[], line_stats: Record<number, unknown>, ranges?: unknown[], call_tree?: unknown[] }} */ (null),
  /** @type {Record<number, unknown[]>} */
  lineRangesIndex: {},
  profiledRanges: /** @type {unknown[]} */ ([]),
  currentProfiledRangeIndex: -1,
  profiledSortMode: "line",
  /** "flat" | "tree" — tree uses analyser call_tree when available */
  profiledListDisplayMode: "flat",
  /** Sibling-sorted clone of `call_tree` for tree UI + nav DFS order; null in flat mode */
  sortedCallTreeForDisplay: /** @type {unknown[] | null} */ (null),
  /** @type {Record<string, boolean>} */
  profiledTreeExpanded: {},
  treeState: /** @type {Record<string, boolean>} */ ({}),
  treeChildrenCache: /** @type {Record<string, unknown>} */ ({}),
  totalDurationNs: 0,
  /** @type {unknown[] | null} */
  bpfDisasmInsns: null,
  /** @type {Record<string, number>} */
  insnTiming: {},
  /** @type {Record<string, Record<string, number>>} */
  insnTimingByFile: {},
  /** @type {string[]} */
  bpfProfiledFiles: [],
  bpfInsnFileFilter: "all",
  bpfInsnScaleMode: "profiled",
  /** All insn indices seen in the report (dropdown shows top 200 by time). */
  globalArgs: /** @type {string[]} */ ([]),
  lastDetailsText: "Hover a line to see detailed profiling data.",
};
