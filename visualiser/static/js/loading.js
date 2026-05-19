/** @typedef {"global" | "editor" | "tree"} LoadingScope */

/** @type {Record<LoadingScope, { depth: number, message: string, barEl: HTMLElement | null, labelEl: HTMLElement | null }>} */
const scopes = {
  global: { depth: 0, message: "", barEl: null, labelEl: null },
  editor: { depth: 0, message: "", barEl: null, labelEl: null },
  tree: { depth: 0, message: "", barEl: null, labelEl: null },
};

function syncScope(scope) {
  const state = scopes[scope];
  const active = state.depth > 0;
  if (state.barEl) {
    state.barEl.hidden = !active;
    state.barEl.setAttribute("aria-hidden", String(!active));
  }
  if (state.labelEl) {
    state.labelEl.textContent = active ? state.message : "";
    state.labelEl.hidden = !active || !state.message;
  }
  document.body.classList.toggle(`is-loading-${scope}`, active);
}

/**
 * @param {LoadingScope} scope
 * @param {string} [message]
 */
export function beginLoading(scope, message = "Loading…") {
  const state = scopes[scope];
  state.depth += 1;
  if (message) {
    state.message = message;
  }
  syncScope(scope);
}

/** @param {LoadingScope} scope */
export function endLoading(scope) {
  const state = scopes[scope];
  state.depth = Math.max(0, state.depth - 1);
  if (state.depth === 0) {
    state.message = "";
  }
  syncScope(scope);
}

/**
 * @template T
 * @param {LoadingScope} scope
 * @param {string} message
 * @param {() => Promise<T>} fn
 * @returns {Promise<T>}
 */
export async function withLoading(scope, message, fn) {
  beginLoading(scope, message);
  try {
    return await fn();
  } finally {
    endLoading(scope);
  }
}

export function initLoading() {
  scopes.global.barEl = document.getElementById("globalLoadingBar");
  scopes.global.labelEl = document.getElementById("globalLoadingLabel");
  scopes.editor.barEl = document.getElementById("editorLoading");
  scopes.editor.labelEl = document.getElementById("editorLoadingLabel");
  scopes.tree.barEl = document.getElementById("treeLoadingBar");
  scopes.tree.labelEl = document.getElementById("treeLoadingLabel");
}
