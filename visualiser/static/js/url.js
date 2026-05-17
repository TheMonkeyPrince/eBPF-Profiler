import { app, ui } from "./state.js";

export function updateUrlState(replace = false) {
  const url = new URL(window.location.href);
  if (app.selectedPath) {
    url.searchParams.set("file", app.selectedPath);
  } else {
    url.searchParams.delete("file");
  }
  if (app.selectedArg && app.selectedArg !== "all") {
    url.searchParams.set("arg", app.selectedArg);
  } else {
    url.searchParams.delete("arg");
  }
  if (app.selectedScaleMode !== "profiled") {
    url.searchParams.set("scale", app.selectedScaleMode);
  } else {
    url.searchParams.delete("scale");
  }
  url.searchParams.set("theme", app.selectedTheme);
  if (app.profiledListDisplayMode === "tree") {
    url.searchParams.set("pview", "tree");
  } else {
    url.searchParams.delete("pview");
  }
  if (app.bpfInsnFileFilter && app.bpfInsnFileFilter !== "all") {
    url.searchParams.set("bpfFile", app.bpfInsnFileFilter);
  } else {
    url.searchParams.delete("bpfFile");
  }
  if (app.bpfInsnScaleMode === "absolute") {
    url.searchParams.set("bpfScale", "absolute");
  } else {
    url.searchParams.delete("bpfScale");
  }

  const reportSelectEl = ui?.reportSelectEl;
  if (reportSelectEl && reportSelectEl.value && !reportSelectEl.selectedOptions[0]?.disabled) {
    url.searchParams.set("report", reportSelectEl.value);
  } else {
    url.searchParams.delete("report");
  }

  if (replace) {
    history.replaceState(null, "", url);
  } else {
    history.pushState(null, "", url);
  }
}

export function readUrlState() {
  const url = new URL(window.location.href);
  const maybeFile = url.searchParams.get("file");
  const maybeArg = url.searchParams.get("arg");
  const maybeTheme = url.searchParams.get("theme");
  const maybeScale = url.searchParams.get("scale");
  if (maybeFile) {
    app.selectedPath = maybeFile;
  }
  if (maybeArg) {
    app.selectedArg = maybeArg;
  }
  if (maybeTheme === "light" || maybeTheme === "dark") {
    app.selectedTheme = maybeTheme;
  }
  if (maybeScale === "absolute" || maybeScale === "profiled") {
    app.selectedScaleMode = maybeScale;
  }
  const maybePview = url.searchParams.get("pview");
  if (maybePview === "tree" || maybePview === "flat") {
    app.profiledListDisplayMode = maybePview;
  }
  const maybeBpfFile = url.searchParams.get("bpfFile");
  if (maybeBpfFile) {
    app.bpfInsnFileFilter = maybeBpfFile;
  }
  const maybeBpfScale = url.searchParams.get("bpfScale");
  if (maybeBpfScale === "absolute" || maybeBpfScale === "profiled") {
    app.bpfInsnScaleMode = maybeBpfScale;
  }
}
