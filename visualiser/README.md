# Kernel Source Heatmap Viewer

Small browser viewer for profiling reports shaped like:

- `"path/to/file.c:start-end": [samples...]`
- `"path/to/file.c:start-end": { "arg": [samples...], ... }`

It shows Linux source code with a per-line heat overlay and supports filtering by profiling argument.

## Quick start

From `visualiser/`:

```bash
python3 server.py
```

Open <http://127.0.0.1:8000>.

## Configuration

Environment variables:

- `KERNEL_PATH` (default: `../kernel`)
- `REPORT_PATH` (default: `./report.json`)

Example:

```bash
KERNEL_PATH=../kernel REPORT_PATH=./my-report.json python3 server.py
```

## Notes

- Cost for a range is currently applied to every line in that range.
- Heat color uses log scaling so very hot lines stay visible without flattening the rest.
- If you replace the report file while the server is running, click **Reload report**.
