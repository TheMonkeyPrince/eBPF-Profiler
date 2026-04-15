import json
import os
import re
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


HOST = "127.0.0.1"
PORT = 8000
KERNEL_PATH = Path(os.environ.get("KERNEL_PATH", "../kernel")).resolve()
REPORT_PATH = Path(os.environ.get("REPORT_PATH", "./report.json")).resolve()
MAX_TREE_ENTRIES = 500

RANGE_RE = re.compile(r"^(?P<file>.+):(?P<start>\d+)-(?P<end>\d+)$")


def to_rel_kernel_path(path: Path) -> str:
    return path.relative_to(KERNEL_PATH).as_posix()


def safe_kernel_join(rel_path: str) -> Path:
    candidate = (KERNEL_PATH / rel_path).resolve()
    try:
        candidate.relative_to(KERNEL_PATH)
    except ValueError as err:
        raise ValueError("path escapes kernel root") from err
    return candidate


def tree_entries_from_report(base_rel: str, profiled_files):
    base = base_rel.strip("/")
    if base:
        prefix = f"{base}/"
    else:
        prefix = ""

    dirs = set()
    files = set()
    for rel_file in profiled_files:
        if prefix and not rel_file.startswith(prefix):
            continue
        remainder = rel_file[len(prefix) :] if prefix else rel_file
        if not remainder:
            continue
        if "/" in remainder:
            dirs.add(remainder.split("/", 1)[0])
        else:
            files.add(remainder)

    entries = []
    for name in sorted(dirs):
        entries.append(
            {
                "name": name,
                "path": f"{base}/{name}" if base else name,
                "is_dir": True,
            }
        )
    for name in sorted(files):
        entries.append(
            {
                "name": name,
                "path": f"{base}/{name}" if base else name,
                "is_dir": False,
            }
        )
    return entries[:MAX_TREE_ENTRIES]


def parse_samples(value):
    if isinstance(value, list):
        if not all(isinstance(item, (int, float)) for item in value):
            raise ValueError("sample list contains non-numeric values")
        return {"no_arg": [int(v) for v in value], "by_arg": {}}
    if isinstance(value, dict):
        parsed = {}
        for arg, samples in value.items():
            if not isinstance(samples, list) or not all(
                isinstance(item, (int, float)) for item in samples
            ):
                raise ValueError("arg sample list is malformed")
            parsed[str(arg)] = [int(v) for v in samples]
        return {"no_arg": [], "by_arg": parsed}
    raise ValueError("invalid execution_times entry")


def empty_line_stats():
    return {
        "total_ns": 0,
        "count": 0,
        "max_ns": 0,
        "by_arg": {},
    }


def ingest_report(report):
    indexed = {
        "program_name": report.get("program_name"),
        "total_duration": int(report.get("total_duration", 0)),
        "files": {},
        "global_args": set(),
    }

    execution_times = report.get("execution_times", {})
    if not isinstance(execution_times, dict):
        raise ValueError("execution_times must be an object")

    for key, value in execution_times.items():
        match = RANGE_RE.match(key)
        if not match:
            continue

        rel_file = match.group("file")
        start = int(match.group("start"))
        end = int(match.group("end"))
        if start > end:
            start, end = end, start

        parsed = parse_samples(value)
        no_arg = parsed["no_arg"]
        by_arg = parsed["by_arg"]
        for arg in by_arg:
            indexed["global_args"].add(arg)

        file_entry = indexed["files"].setdefault(
            rel_file,
            {
                "line_stats": {},
                "ranges": [],
            },
        )

        range_total = sum(no_arg) + sum(sum(samples) for samples in by_arg.values())
        range_count = len(no_arg) + sum(len(samples) for samples in by_arg.values())
        range_max = 0
        if no_arg:
            range_max = max(range_max, max(no_arg))
        for samples in by_arg.values():
            if samples:
                range_max = max(range_max, max(samples))

        file_entry["ranges"].append(
            {
                "start": start,
                "end": end,
                "no_arg": no_arg,
                "by_arg": by_arg,
                "total_ns": range_total,
                "count": range_count,
                "max_ns": range_max,
            }
        )

        for line in range(start, end + 1):
            line_stat = file_entry["line_stats"].setdefault(line, empty_line_stats())

            line_stat["total_ns"] += range_total
            line_stat["count"] += range_count
            line_stat["max_ns"] = max(line_stat["max_ns"], range_max)

            if no_arg:
                no_arg_stat = line_stat["by_arg"].setdefault(
                    "__no_arg__", {"total_ns": 0, "count": 0, "max_ns": 0}
                )
                no_arg_stat["total_ns"] += sum(no_arg)
                no_arg_stat["count"] += len(no_arg)
                no_arg_stat["max_ns"] = max(no_arg_stat["max_ns"], max(no_arg))

            for arg, samples in by_arg.items():
                arg_stat = line_stat["by_arg"].setdefault(
                    arg, {"total_ns": 0, "count": 0, "max_ns": 0}
                )
                arg_stat["total_ns"] += sum(samples)
                arg_stat["count"] += len(samples)
                if samples:
                    arg_stat["max_ns"] = max(arg_stat["max_ns"], max(samples))

    indexed["global_args"] = sorted(indexed["global_args"], key=lambda a: int(a))
    return indexed


class AppState:
    def __init__(self):
        self.index = None
        self.load_error = None
        self.reload_report()

    def reload_report(self):
        try:
            if REPORT_PATH.exists():
                with REPORT_PATH.open("r", encoding="utf-8") as handle:
                    report = json.load(handle)
                self.index = ingest_report(report)
                self.load_error = None
            else:
                self.index = ingest_report({"execution_times": {}})
                self.load_error = f"Report not found at {REPORT_PATH}"
        except Exception as exc:  # pylint: disable=broad-except
            self.index = ingest_report({"execution_times": {}})
            self.load_error = f"Failed to parse report: {exc}"


STATE = AppState()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="static", **kwargs)

    def _write_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            self._write_json(
                {
                    "kernel_path": str(KERNEL_PATH),
                    "report_path": str(REPORT_PATH),
                    "program_name": STATE.index.get("program_name"),
                    "total_duration": STATE.index.get("total_duration", 0),
                    "global_args": STATE.index.get("global_args", []),
                    "load_error": STATE.load_error,
                    "profiled_files_count": len(STATE.index.get("files", {})),
                }
            )
            return

        if parsed.path == "/api/reload":
            STATE.reload_report()
            self._write_json({"ok": True, "load_error": STATE.load_error})
            return

        if parsed.path == "/api/tree":
            query = parse_qs(parsed.query)
            rel = query.get("path", [""])[0].strip("/")
            try:
                safe_kernel_join(rel)
            except ValueError:
                self._write_json({"error": "invalid path"}, status=HTTPStatus.BAD_REQUEST)
                return

            profiled_files = set(STATE.index.get("files", {}).keys())
            entries = tree_entries_from_report(rel, profiled_files)

            self._write_json({"base": rel, "entries": entries})
            return

        if parsed.path == "/api/file":
            query = parse_qs(parsed.query)
            rel_path = query.get("path", [""])[0].strip("/")
            arg = query.get("arg", ["all"])[0]

            if not rel_path:
                self._write_json({"error": "missing path"}, status=HTTPStatus.BAD_REQUEST)
                return

            try:
                source_path = safe_kernel_join(rel_path)
            except ValueError:
                self._write_json({"error": "invalid path"}, status=HTTPStatus.BAD_REQUEST)
                return

            if not source_path.exists():
                self._write_json({"error": "file does not exist"}, status=HTTPStatus.NOT_FOUND)
                return
            if not source_path.is_file():
                self._write_json({"error": "path is not a file"}, status=HTTPStatus.BAD_REQUEST)
                return

            try:
                source = source_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                self._write_json({"error": "failed to read file"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return

            lines = source.splitlines()
            profile = STATE.index.get("files", {}).get(rel_path, {"line_stats": {}, "ranges": []})
            line_stats = {}
            max_total = 0

            for line_num, stat in profile["line_stats"].items():
                if arg == "all":
                    total_ns = stat["total_ns"]
                    count = stat["count"]
                    max_ns = stat["max_ns"]
                else:
                    picked = stat["by_arg"].get(arg, {"total_ns": 0, "count": 0, "max_ns": 0})
                    total_ns = picked["total_ns"]
                    count = picked["count"]
                    max_ns = picked["max_ns"]

                avg_ns = int(total_ns / count) if count else 0
                line_stats[line_num] = {
                    "total_ns": total_ns,
                    "count": count,
                    "avg_ns": avg_ns,
                    "max_ns": max_ns,
                }
                if total_ns > max_total:
                    max_total = total_ns

            self._write_json(
                {
                    "path": rel_path,
                    "lines": lines,
                    "line_stats": line_stats,
                    "max_total_ns": max_total,
                    "ranges": profile["ranges"],
                }
            )
            return

        super().do_GET()


def main():
    if not KERNEL_PATH.exists():
        print(f"[warning] KERNEL_PATH does not exist: {KERNEL_PATH}")
    print(f"Serving on http://{HOST}:{PORT}")
    print(f"KERNEL_PATH={KERNEL_PATH}")
    print(f"REPORT_PATH={REPORT_PATH}")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
