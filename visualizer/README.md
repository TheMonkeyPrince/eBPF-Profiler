# Trace Analyser Report Visualizer

Browser UI for JSON reports produced by `profiler/trace_analyser.py`.

## Quick start

From the repo root or `visualizer/`:

```bash
python3 visualizer/server.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Reports are loaded from `profiler/out/analysis/*.json` by default.

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANALYSIS_DIR` | `profiler/out/analysis` | Directory of analysis JSON files |
| `KERNEL_PATCH_PATH` | `kernel-patch` | Patched kernel sources (`kernel/bpf/…` → `bpf/…`) |
| `VISUALIZER_QUIET` | unset | Set to any value to suppress request logs |

Example:

```bash
ANALYSIS_DIR=/path/to/reports python3 visualizer/server.py
```

## Without the server

Open `visualizer/static/index.html` directly in a browser and use **Open JSON…** to load a report file. The report catalog and server-backed reload require the Python server.

## Views

- **Overview** — verification time, program size, trace size, verifier counters
- **Call tree** — hierarchical verifier sites with duration bars; scale bars by **% of total** or **% of parent** (choice is remembered in the browser session)
- **Source** — read-only Monaco editor; clicking a site loads the file from `kernel-patch/` and highlights the profiled line
- **Site detail** — per-site stats and BPF instruction-type breakdown when present
- **BPF instructions** — program-wide `durations_per_insn_type` table

## Generating reports

Run the trace analyser and write JSON under the analysis directory (see `profiler/` tooling). Each report matches `TraceAnalyserResult` in `trace_analyser.py`.
