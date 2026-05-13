import { app } from "./state.js";

const STORAGE_KEY = "visualiser.layout.v1";

const DEFAULT_LAYOUT = {
  sidebarWidth: 320,
  treeRatio: 0.55,
  bpfHeight: 240,
};

const layout = { ...DEFAULT_LAYOUT };

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function loadLayout() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    layout.sidebarWidth = Number.isFinite(saved.sidebarWidth)
      ? saved.sidebarWidth
      : DEFAULT_LAYOUT.sidebarWidth;
    layout.treeRatio = Number.isFinite(saved.treeRatio) ? saved.treeRatio : DEFAULT_LAYOUT.treeRatio;
    layout.bpfHeight = Number.isFinite(saved.bpfHeight) ? saved.bpfHeight : DEFAULT_LAYOUT.bpfHeight;
  } catch {
    Object.assign(layout, DEFAULT_LAYOUT);
  }
}

function saveLayout() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
  } catch {
    // Resizing should keep working even if storage is unavailable.
  }
}

function relayoutEditor() {
  app.editor?.layout();
}

function applyLayout() {
  const root = document.documentElement;
  root.style.setProperty("--sidebar-width", `${Math.round(layout.sidebarWidth)}px`);
  root.style.setProperty("--tree-height", `${clamp(layout.treeRatio, 0.18, 0.82) * 100}%`);
  root.style.setProperty("--bpf-panel-height", `${Math.round(layout.bpfHeight)}px`);
  relayoutEditor();
}

function startPointerResize(event, handle, cursor, onMove) {
  if (event.button !== 0) {
    return;
  }

  event.preventDefault();
  handle.classList.add("active");
  document.body.classList.add("resizing");
  document.body.style.cursor = cursor;

  const stop = () => {
    handle.classList.remove("active");
    document.body.classList.remove("resizing");
    document.body.style.cursor = "";
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", stop);
    document.removeEventListener("pointercancel", stop);
    saveLayout();
    relayoutEditor();
  };

  const move = (moveEvent) => {
    onMove(moveEvent);
    applyLayout();
  };

  document.addEventListener("pointermove", move);
  document.addEventListener("pointerup", stop);
  document.addEventListener("pointercancel", stop);
}

function addKeyboardResize(handle, onStep) {
  handle.addEventListener("keydown", (event) => {
    const keySteps = {
      ArrowLeft: -1,
      ArrowUp: -1,
      ArrowRight: 1,
      ArrowDown: 1,
    };
    const direction = keySteps[event.key];
    if (!direction) {
      return;
    }

    event.preventDefault();
    onStep(direction * (event.shiftKey ? 48 : 16));
    applyLayout();
    saveLayout();
  });
}

function setupMainSplitter() {
  const appLayout = document.getElementById("appLayout");
  const sidebarPane = document.getElementById("sidebarPane");
  const handle = document.getElementById("mainSplitter");
  if (!appLayout || !sidebarPane || !handle) {
    return;
  }

  handle.addEventListener("pointerdown", (event) => {
    const startX = event.clientX;
    const startWidth = sidebarPane.getBoundingClientRect().width;
    startPointerResize(event, handle, "col-resize", (moveEvent) => {
      const maxWidth = Math.max(220, appLayout.getBoundingClientRect().width - 360);
      layout.sidebarWidth = clamp(startWidth + moveEvent.clientX - startX, 220, maxWidth);
    });
  });

  addKeyboardResize(handle, (delta) => {
    const maxWidth = Math.max(220, appLayout.getBoundingClientRect().width - 360);
    layout.sidebarWidth = clamp(layout.sidebarWidth + delta, 220, maxWidth);
  });
}

function setupSidebarSplitter() {
  const sidebarPane = document.getElementById("sidebarPane");
  const tree = document.getElementById("tree");
  const profiledPanel = document.getElementById("profiledPanel");
  const handle = document.getElementById("sidebarSplitter");
  if (!sidebarPane || !tree || !profiledPanel || !handle) {
    return;
  }

  function setTreeHeight(newTreeHeight) {
    const totalHeight = tree.getBoundingClientRect().height + profiledPanel.getBoundingClientRect().height;
    if (totalHeight <= 0) {
      return;
    }
    layout.treeRatio = clamp(newTreeHeight / totalHeight, 0.18, 0.82);
  }

  handle.addEventListener("pointerdown", (event) => {
    const startY = event.clientY;
    const startHeight = tree.getBoundingClientRect().height;
    startPointerResize(event, handle, "row-resize", (moveEvent) => {
      setTreeHeight(startHeight + moveEvent.clientY - startY);
    });
  });

  addKeyboardResize(handle, (delta) => {
    setTreeHeight(tree.getBoundingClientRect().height + delta);
  });
}

function setupEditorSplitter() {
  const codePane = document.getElementById("codePane");
  const details = document.getElementById("bpfProgramDetails");
  const handle = document.getElementById("editorSplitter");
  if (!codePane || !details || !handle) {
    return;
  }

  function setBpfHeight(newHeight) {
    const totalHeight = codePane.getBoundingClientRect().height + details.getBoundingClientRect().height;
    const maxHeight = Math.max(96, totalHeight - 160);
    layout.bpfHeight = clamp(newHeight, 96, maxHeight);
  }

  handle.addEventListener("pointerdown", (event) => {
    if (!details.open) {
      return;
    }
    const startY = event.clientY;
    const startHeight = details.getBoundingClientRect().height;
    startPointerResize(event, handle, "row-resize", (moveEvent) => {
      setBpfHeight(startHeight - (moveEvent.clientY - startY));
    });
  });

  addKeyboardResize(handle, (delta) => {
    if (details.open) {
      setBpfHeight(details.getBoundingClientRect().height - delta);
    }
  });

  details.addEventListener("toggle", relayoutEditor);
}

export function initResizableLayout() {
  loadLayout();
  applyLayout();
  setupMainSplitter();
  setupSidebarSplitter();
  setupEditorSplitter();
  window.addEventListener("resize", () => {
    applyLayout();
    saveLayout();
  });
}
