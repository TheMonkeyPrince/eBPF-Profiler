import { apiGet } from "./api.js";
import { app, ui } from "./state.js";
import { updateUrlState } from "./url.js";

export async function fetchTreeChildren(path) {
  if (!app.treeChildrenCache[path]) {
    app.treeChildrenCache[path] = await apiGet(`/api/tree?path=${encodeURIComponent(path)}`);
  }
  return app.treeChildrenCache[path];
}

export async function ensureTreePathExpanded(filePath) {
  const parts = filePath.split("/");
  let current = "";
  for (let i = 0; i < parts.length - 1; i += 1) {
    current = current ? `${current}/${parts[i]}` : parts[i];
    app.treeState[current] = true;
    await fetchTreeChildren(current);
  }
}

function makeTreeNode(entry, depth) {
  const row = document.createElement("div");
  row.className = `explorer-row${!entry.is_dir && entry.path === app.selectedPath ? " active" : ""}`;
  row.style.paddingLeft = `${8 + depth * 12}px`;

  const chev = document.createElement("button");
  chev.type = "button";
  chev.className = "explorer-chevron";
  if (entry.is_dir) {
    chev.textContent = app.treeState[entry.path] ? "▾" : "▸";
    chev.setAttribute("aria-expanded", String(!!app.treeState[entry.path]));
    chev.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      app.treeState[entry.path] = !app.treeState[entry.path];
      if (app.treeState[entry.path]) {
        await fetchTreeChildren(entry.path);
      }
      await renderTree();
    });
  } else {
    chev.classList.add("placeholder");
    chev.disabled = true;
    chev.setAttribute("aria-hidden", "true");
  }
  row.appendChild(chev);

  const icon = document.createElement("span");
  icon.className = "explorer-icon";
  icon.textContent = entry.is_dir ? "📁" : "📄";
  row.appendChild(icon);

  const label = document.createElement("span");
  label.className = "explorer-label";
  label.textContent = entry.name;
  row.appendChild(label);

  row.addEventListener("click", async (e) => {
    if (e.target.closest(".explorer-chevron")) {
      return;
    }
    if (entry.is_dir) {
      app.treeState[entry.path] = !app.treeState[entry.path];
      if (app.treeState[entry.path]) {
        await fetchTreeChildren(entry.path);
      }
      await renderTree();
      return;
    }
    app.selectedPath = entry.path;
    updateUrlState();
    const { loadFile } = await import("./editor.js");
    await loadFile();
  });
  return row;
}

export async function renderTree() {
  const treeEl = ui?.treeEl;
  if (!treeEl) {
    return;
  }
  treeEl.innerHTML = "";
  const root = await fetchTreeChildren("");

  const renderEntries = async (entries, depth) => {
    for (const entry of entries) {
      treeEl.appendChild(makeTreeNode(entry, depth));
      if (entry.is_dir && app.treeState[entry.path]) {
        const child = await fetchTreeChildren(entry.path);
        await renderEntries(child.entries, depth + 1);
      }
    }
  };

  await renderEntries(root.entries, 0);
}
