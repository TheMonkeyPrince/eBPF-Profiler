export async function apiGet(path) {
  const res = await fetch(path);
  let data = {};
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const msg = data.error || `HTTP ${res.status}`;
    let detail = msg;
    if (data.requested_path && data.kernel_path) {
      detail += ` — looked for ${data.requested_path} under KERNEL_PATH=${data.kernel_path}`;
    }
    throw new Error(`Request failed (${res.status}) for ${path}: ${detail}`);
  }
  return data;
}
