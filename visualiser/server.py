import json
import os
import re
from collections import defaultdict
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


HOST = "127.0.0.1"
PORT = 8000
_SERVER_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _SERVER_ROOT.parent
# Same layout as build-kernel.sh (sources live under repo/linux).
_DEFAULT_KERNEL_PATH = (_REPO_ROOT / "linux").resolve()
KERNEL_PATH = Path(
    os.environ.get("KERNEL_PATH", str(_DEFAULT_KERNEL_PATH))
).resolve()
_DEFAULT_KERNEL_PATCH_PATH = (_REPO_ROOT / "kernel-patch").resolve()
KERNEL_PATCH_PATH = Path(
    os.environ.get("KERNEL_PATCH_PATH", str(_DEFAULT_KERNEL_PATCH_PATH))
).resolve()
_DEFAULT_ANALYSIS_DIR = (_REPO_ROOT / "profiler" / "out" / "analysis").resolve()
ANALYSIS_DIR = Path(
    os.environ.get("ANALYSIS_DIR", str(_DEFAULT_ANALYSIS_DIR))
).resolve()
MAX_TREE_ENTRIES = 500


def list_analysis_report_stems(analysis_dir: Path) -> list[str]:
    if not analysis_dir.is_dir():
        return []
    return sorted(p.stem for p in analysis_dir.glob("*.json") if p.is_file())


def resolve_analysis_report_path(analysis_dir: Path, stem: str) -> Path | None:
    if not stem or "/" in stem or "\\" in stem or stem.startswith("."):
        return None
    root = analysis_dir.resolve()
    candidate = (root / f"{stem}.json").resolve()
    if candidate.parent != root:
        return None
    return candidate if candidate.is_file() else None


def reports_catalog(analysis_dir: Path) -> list[dict]:
    return [{"id": s, "label": s} for s in list_analysis_report_stems(analysis_dir)]

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


def _merge_visualiser_meta_from_report(indexed: dict, report: dict) -> None:
    kc = report.get("kernel_compiler")
    if isinstance(kc, str) and kc:
        indexed["kernel_compiler"] = kc
    else:
        meta = report.get("meta")
        if isinstance(meta, dict) and isinstance(meta.get("kernel_compiler"), str):
            indexed["kernel_compiler"] = meta["kernel_compiler"]

    insns = report.get("bpf_insns")
    if isinstance(insns, list):
        indexed["bpf_insns"] = insns
        indexed["bpf_insn_count"] = len(insns)
    else:
        meta = report.get("meta")
        if isinstance(meta, dict) and meta.get("bpf_insn_count") is not None:
            indexed["bpf_insn_count"] = int(meta["bpf_insn_count"])


def _total_duration_ns_from_report(report):
    if "verification_ns" in report:
        return int(report["verification_ns"])
    if "total_duration_ns" in report:
        return int(report["total_duration_ns"])
    td = report.get("total_duration")
    if td is not None:
        return int(td)
    ver = report.get("verification") or {}
    return int(ver.get("duration_ns", 0))


def _parse_file_colon_location(loc: str):
    """Parse `path/to/file.c:start:end` (split from the right)."""
    try:
        path, start_s, end_s = loc.rsplit(":", 2)
    except ValueError as err:
        raise ValueError(f"invalid file location string: {loc!r}") from err
    return path, int(start_s), int(end_s)


def _index_append_range(
    indexed,
    rel_file,
    start,
    end,
    no_arg,
    no_arg_exclusive,
    by_arg,
    by_arg_exclusive,
    function,
):
    """Append one logical range (already merged sample lists) to the profile index."""
    if not no_arg and not by_arg:
        return

    range_total = sum(no_arg) + sum(sum(samples) for samples in by_arg.values())
    range_count = len(no_arg) + sum(len(samples) for samples in by_arg.values())
    range_max = 0
    if no_arg:
        range_max = max(range_max, max(no_arg))
    for samples in by_arg.values():
        if samples:
            range_max = max(range_max, max(samples))

    file_entry = indexed["files"].setdefault(
        rel_file,
        {
            "line_stats": {},
            "ranges": [],
        },
    )

    range_entry = {
        "start": start,
        "end": end,
        "no_arg": no_arg,
        "by_arg": by_arg,
        "total_ns": range_total,
        "count": range_count,
        "max_ns": range_max,
    }
    if isinstance(function, str) and function:
        range_entry["function"] = function
    if no_arg_exclusive:
        range_entry["no_arg_exclusive"] = no_arg_exclusive
    if by_arg_exclusive:
        range_entry["by_arg_exclusive"] = by_arg_exclusive

    file_entry["ranges"].append(range_entry)

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


def _split_timing_sample_pairs(items):
    inclusive = []
    exclusive = []
    for item in items:
        if isinstance(item, dict):
            inclusive.append(int(item["inclusive_ns"]))
            exclusive.append(
                int(item.get("exclusive_ns", item["inclusive_ns"]))
            )
        elif isinstance(item, (int, float)):
            v = int(item)
            inclusive.append(v)
            exclusive.append(v)
        else:
            raise ValueError("timing sample must be a number or object")
    return inclusive, exclusive


def ingest_regions_schema_v2(report):
    indexed = {
        "program_name": report.get("program_name"),
        "total_duration": _total_duration_ns_from_report(report),
        "files": {},
        "global_args": set(),
    }
    regions = report.get("regions")
    if not isinstance(regions, list):
        raise ValueError("regions must be an array")

    for region in regions:
        if not isinstance(region, dict):
            raise ValueError("each region must be an object")
        rel_file = region.get("file")
        if not isinstance(rel_file, str):
            raise ValueError("region.file must be a string")
        start = int(region["start_line"])
        end = int(region["end_line"])
        if start > end:
            start, end = end, start

        timing = region.get("timing")
        timing_by_arg = region.get("timing_by_arg")
        if timing is None and timing_by_arg is None:
            continue

        no_arg, no_arg_exclusive = [], []
        if timing is not None:
            if not isinstance(timing, list):
                raise ValueError("region.timing must be a list")
            no_arg, no_arg_exclusive = _split_timing_sample_pairs(timing)

        by_arg = {}
        by_arg_exclusive = {}
        if timing_by_arg is not None:
            if not isinstance(timing_by_arg, dict):
                raise ValueError("region.timing_by_arg must be an object")
            for arg_key, samples in timing_by_arg.items():
                if not isinstance(samples, list):
                    raise ValueError("timing_by_arg values must be lists")
                inc, exc = _split_timing_sample_pairs(samples)
                sk = str(arg_key)
                by_arg[sk] = inc
                by_arg_exclusive[sk] = exc

        if not no_arg and not by_arg:
            continue

        for arg in by_arg:
            indexed["global_args"].add(arg)

        fn = region.get("function")
        fn_str = fn if isinstance(fn, str) and fn else None
        _index_append_range(
            indexed,
            rel_file,
            start,
            end,
            no_arg,
            no_arg_exclusive,
            by_arg,
            by_arg_exclusive,
            fn_str,
        )

    indexed["global_args"] = sorted(indexed["global_args"], key=lambda a: int(a))
    _merge_visualiser_meta_from_report(indexed, report)
    return indexed


def ingest_legacy_execution_times(report):
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
    _merge_visualiser_meta_from_report(indexed, report)
    return indexed


def ingest_call_tree_schema_v3(report):
    indexed = {
        "program_name": report.get("program_name"),
        "total_duration": _total_duration_ns_from_report(report),
        "files": {},
        "global_args": set(),
    }

    roots = report.get("call_tree")
    if roots is None:
        raise ValueError("call_tree is required")
    if not isinstance(roots, list):
        raise ValueError("call_tree must be an array")

    acc = {}

    def merge_node(node):
        if not isinstance(node, dict):
            raise ValueError("call_tree node must be an object")
        loc = node.get("file") or node.get("site")
        if not isinstance(loc, str):
            raise ValueError(
                'call_tree node needs a compact "path:start:end" string in file (or legacy site)'
            )
        rel_file, start, end = _parse_file_colon_location(loc)
        if start > end:
            start, end = end, start

        inclusive = int(node["inclusive_ns"])
        exclusive = int(node["exclusive_ns"])
        fn_raw = node.get("function")
        fn_key = fn_raw if isinstance(fn_raw, str) and fn_raw else None

        key = (rel_file, start, end, fn_key)
        if key not in acc:
            acc[key] = {
                "no_arg": [],
                "no_arg_exclusive": [],
                "by_arg": defaultdict(list),
                "by_arg_exclusive": defaultdict(list),
            }
        bucket = acc[key]

        arg = node.get("arg")
        if arg is not None:
            k = str(int(arg))
            bucket["by_arg"][k].append(inclusive)
            bucket["by_arg_exclusive"][k].append(exclusive)
            indexed["global_args"].add(k)
        else:
            bucket["no_arg"].append(inclusive)
            bucket["no_arg_exclusive"].append(exclusive)

        for ch in node.get("children") or []:
            merge_node(ch)

    for root in roots:
        merge_node(root)

    for key_tuple in sorted(acc, key=lambda k: (k[0], k[1], k[2], k[3] or "")):
        rel_file, start, end, fn_key = key_tuple
        bucket = acc[key_tuple]
        by_arg = {k: list(v) for k, v in bucket["by_arg"].items()}
        by_arg_exclusive = {k: list(bucket["by_arg_exclusive"][k]) for k in by_arg}

        fn_str = fn_key if fn_key else None
        _index_append_range(
            indexed,
            rel_file,
            start,
            end,
            bucket["no_arg"],
            bucket["no_arg_exclusive"],
            by_arg,
            by_arg_exclusive,
            fn_str,
        )

    indexed["global_args"] = sorted(indexed["global_args"], key=lambda a: int(a))
    _merge_visualiser_meta_from_report(indexed, report)
    return indexed


def ingest_report(report):
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    if isinstance(report.get("call_tree"), list):
        return ingest_call_tree_schema_v3(report)
    schema = int(report.get("schema_version", 1))
    if schema >= 2 and "regions" in report:
        return ingest_regions_schema_v2(report)
    return ingest_legacy_execution_times(report)


class AppState:
    def __init__(self):
        self.analysis_dir = ANALYSIS_DIR
        self.current_report: str | None = None
        self.index = None
        self.load_error = None
        stems = list_analysis_report_stems(self.analysis_dir)
        self.current_report = stems[0] if stems else None
        self._load_current_report_from_disk()

    def _empty_index_report(self):
        return {"call_tree": []}

    def _load_current_report_from_disk(self):
        empty = self._empty_index_report()
        try:
            if not self.current_report:
                self.index = ingest_report(empty)
                if not self.analysis_dir.is_dir():
                    self.load_error = f"Analysis directory not found: {self.analysis_dir}"
                else:
                    self.load_error = f"No .json reports in {self.analysis_dir}"
                return

            path = resolve_analysis_report_path(self.analysis_dir, self.current_report)
            if path is None:
                self.index = ingest_report(empty)
                self.load_error = (
                    f"Report file missing or invalid name for {self.current_report!r}"
                )
                return

            with path.open("r", encoding="utf-8") as handle:
                report = json.load(handle)
            self.index = ingest_report(report)
            self.load_error = None
        except Exception as exc:  # pylint: disable=broad-except
            self.index = ingest_report(empty)
            self.load_error = f"Failed to parse report: {exc}"

    def reload_report(self, report_stem: str | None = None):
        stems = list_analysis_report_stems(self.analysis_dir)
        if report_stem is not None:
            if report_stem not in stems:
                self.load_error = (
                    f"Unknown report {report_stem!r} — use one of: "
                    + (", ".join(stems) if stems else "(no reports)")
                )
                return
            self.current_report = report_stem
        elif self.current_report not in stems:
            self.current_report = stems[0] if stems else None

        self._load_current_report_from_disk()


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
            catalog = reports_catalog(STATE.analysis_dir)
            self._write_json(
                {
                    "kernel_path": str(KERNEL_PATH),
                    "analysis_dir": str(STATE.analysis_dir),
                    "reports": catalog,
                    "current_report": STATE.current_report,
                    "program_name": STATE.index.get("program_name"),
                    "total_duration": int(STATE.index.get("total_duration", 0)),
                    "total_duration_ns": int(STATE.index.get("total_duration", 0)),
                    "global_args": STATE.index.get("global_args", []),
                    "load_error": STATE.load_error,
                    "profiled_files_count": len(STATE.index.get("files", {})),
                    "bpf_insn_count": STATE.index.get("bpf_insn_count"),
                    "bpf_insns": STATE.index.get("bpf_insns"),
                    "kernel_compiler": STATE.index.get("kernel_compiler"),
                }
            )
            return

        if parsed.path == "/api/reload":
            query = parse_qs(parsed.query)
            rid = query.get("report", [None])[0]
            STATE.reload_report(report_stem=rid if rid else None)
            self._write_json(
                {
                    "ok": True,
                    "load_error": STATE.load_error,
                    "current_report": STATE.current_report,
                }
            )
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
                self._write_json(
                    {
                        "error": "file does not exist",
                        "requested_path": rel_path,
                        "resolved_path": str(source_path),
                        "kernel_path": str(KERNEL_PATH),
                    },
                    status=HTTPStatus.NOT_FOUND,
                )
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

def apply_kernel_patch():
    print(f"Applying kernel patch from {KERNEL_PATCH_PATH}...")
    os.system(f"cp -r {KERNEL_PATCH_PATH}/* {KERNEL_PATH}/kernel/")

def main():
    if not KERNEL_PATH.exists():
        print(f"[warning] KERNEL_PATH does not exist: {KERNEL_PATH}")
    else:
        print("Applying kernel patch...")
        apply_kernel_patch()
    print(f"Serving on http://{HOST}:{PORT}")
    print(f"KERNEL_PATH={KERNEL_PATH}")
    print(f"ANALYSIS_DIR={ANALYSIS_DIR}")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
