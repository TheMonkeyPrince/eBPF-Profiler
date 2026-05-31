export async function fetchReportCatalog() {
  const res = await fetch("/api/reports");
  if (!res.ok) throw new Error(`Failed to list reports (${res.status})`);
  return res.json();
}

/** @param {string} id */
export async function fetchReport(id) {
  const res = await fetch(`/api/report/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Failed to load report (${res.status})`);
  return res.json();
}

/** @param {File} file */
export async function parseReportFile(file) {
  const text = await file.text();
  return JSON.parse(text);
}

/** @param {string} path Report path (e.g. kernel/bpf/verifier.c) */
export async function fetchSource(path) {
  const url = `/api/source?${new URLSearchParams({ path })}`;
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) {
    return { error: data.error || `HTTP ${res.status}`, ...data };
  }
  return data;
}
