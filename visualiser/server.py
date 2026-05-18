import json
import os
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
    catalog = []
    for stem in list_analysis_report_stems(analysis_dir):
        entry = {"id": stem, "label": stem, "total_duration_ns": 0}
        path = resolve_analysis_report_path(analysis_dir, stem)
        if path is None:
            catalog.append(entry)
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                report = json.load(handle)
            if isinstance(report, dict):
                entry["total_duration_ns"] = _total_duration_ns_from_report(report)
        except (OSError, ValueError, json.JSONDecodeError):
            # Keep default duration when a report cannot be parsed.
            pass
        catalog.append(entry)
    return catalog

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

    insns = report.get("bpf_insns")
    if isinstance(insns, list):
        indexed["bpf_insns"] = insns
        indexed["bpf_insn_count"] = len(insns)

    ps = report.get("profile_stats")
    if isinstance(ps, dict):
        indexed["profile_stats"] = ps

    trc = report.get("trace_record_count")
    if isinstance(trc, int) and trc >= 0:
        indexed["trace_record_count"] = trc


def _total_duration_ns_from_report(report):
    if "verification_ns" not in report:
        raise ValueError("verification_ns is required")
    return int(report["verification_ns"])


def _parse_file_colon_location(loc: str):
    """Parse `file_id_or_path:start:end` (split from the right)."""
    try:
        path, start_s, end_s = loc.rsplit(":", 2)
    except ValueError as err:
        raise ValueError(f"invalid file location string: {loc!r}") from err
    return path, int(start_s), int(end_s)


def _resolve_file_id(file_ids: dict, file_id: str) -> str:
    rel = file_ids.get(file_id)
    if rel is None:
        rel = file_ids.get(str(file_id))
    if not isinstance(rel, str) or not rel:
        raise ValueError(f"unknown file id in call_tree: {file_id!r}")
    return rel


def _resolve_site_loc(loc: str, file_ids: dict) -> str:
    file_id, start, end = _parse_file_colon_location(loc)
    rel_file = _resolve_file_id(file_ids, file_id)
    return f"{rel_file}:{start}:{end}"


def normalize_call_tree_node(node: dict, file_ids: dict) -> dict:
    """Expand compact analyser nodes (f/i/e/a/c) for the visualiser API."""
    if not isinstance(node, dict):
        raise ValueError("call_tree node must be an object")
    loc = node.get("f")
    if not isinstance(loc, str):
        raise ValueError('call_tree node needs compact "f" (file_id:start:end)')

    out: dict = {
        "file": _resolve_site_loc(loc, file_ids),
        "inclusive_ns": int(node["i"]),
        "exclusive_ns": int(node["e"]),
    }
    if "a" in node:
        out["arg"] = node["a"]
    children = node.get("c")
    if children is not None:
        if not isinstance(children, list):
            raise ValueError("call_tree node children must be an array")
        if children:
            out["children"] = [normalize_call_tree_node(ch, file_ids) for ch in children]
    return out


def normalize_call_tree(roots: list, file_ids: dict) -> list:
    if not isinstance(roots, list):
        raise ValueError("call_tree must be an array")
    return [normalize_call_tree_node(node, file_ids) for node in roots]


def _node_matches_arg_filter(node: dict, arg_filter: str) -> bool:
    if arg_filter == "all":
        return True
    arg_val = node.get("arg")
    if arg_filter == "__no_arg__":
        return arg_val is None
    try:
        return arg_val is not None and str(int(arg_val)) == str(arg_filter)
    except (TypeError, ValueError):
        return False


def _prune_call_tree_node_for_file_arg(
    node: dict, rel_path: str, arg_filter: str
) -> dict | None:
    """Keep branches that touch rel_path, with arg filtering like the flat profiled list."""
    loc = node.get("file")
    if not isinstance(loc, str):
        return None
    try:
        nf, _start, _end = _parse_file_colon_location(loc)
    except ValueError:
        return None

    children_in = []
    for ch in node.get("children") or []:
        if not isinstance(ch, dict):
            continue
        pruned = _prune_call_tree_node_for_file_arg(ch, rel_path, arg_filter)
        if pruned is not None:
            children_in.append(pruned)

    in_file = nf == rel_path
    arg_ok = _node_matches_arg_filter(node, arg_filter)
    if children_in:
        out = dict(node)
        out["children"] = children_in
        return out
    if in_file and arg_ok:
        out = dict(node)
        out["children"] = []
        return out
    return None


def prune_call_tree_for_file_arg(roots: list, rel_path: str, arg_filter: str) -> list:
    if not isinstance(roots, list) or not rel_path:
        return []
    out = []
    for node in roots:
        if not isinstance(node, dict):
            continue
        pruned = _prune_call_tree_node_for_file_arg(node, rel_path, arg_filter)
        if pruned is not None:
            out.append(pruned)
    return out


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


def _sample_list_total_ns(samples):
    total = 0
    for item in samples or []:
        if isinstance(item, dict):
            total += int(item.get("inclusive_ns", item.get("ns", 0)))
        elif isinstance(item, (int, float)):
            total += int(item)
    return total


def insn_timing_from_index(indexed: dict, rel_file: str | None = None) -> dict[str, int]:
    """Aggregate inclusive time per bpf_insn_idx (by_arg samples only)."""
    summary = bpf_insn_profiling_from_index(indexed)
    if rel_file is None:
        return summary["insn_timing"]
    return summary["insn_timing_by_file"].get(rel_file, {})


def bpf_insn_profiling_from_index(indexed: dict) -> dict:
    """Per-file and report-wide timing keyed by bpf_insn_idx, plus profiled totals."""
    insn_timing_by_file: dict[str, dict[str, int]] = {}
    profiled_total_ns_by_file: dict[str, int] = {}
    profiled_insn_total_ns_by_file: dict[str, int] = {}

    for rel_file, file_entry in indexed.get("files", {}).items():
        insn_map: dict[str, int] = {}
        profiled_total = 0
        insn_total = 0
        for range_entry in file_entry.get("ranges", []):
            profiled_total += _sample_list_total_ns(range_entry.get("no_arg"))
            for arg, samples in (range_entry.get("by_arg") or {}).items():
                added = _sample_list_total_ns(samples)
                profiled_total += added
                if added > 0:
                    sk = str(arg)
                    insn_map[sk] = insn_map.get(sk, 0) + added
                    insn_total += added
        if not insn_map and profiled_total <= 0:
            continue
        insn_timing_by_file[rel_file] = insn_map
        profiled_total_ns_by_file[rel_file] = profiled_total
        profiled_insn_total_ns_by_file[rel_file] = insn_total

    insn_timing: dict[str, int] = {}
    for per_file in insn_timing_by_file.values():
        for arg, total in per_file.items():
            insn_timing[arg] = insn_timing.get(arg, 0) + total

    return {
        "insn_timing": insn_timing,
        "insn_timing_by_file": insn_timing_by_file,
        "profiled_files": sorted(insn_timing_by_file.keys()),
        "profiled_total_ns": sum(profiled_total_ns_by_file.values()),
        "profiled_insn_total_ns": sum(profiled_insn_total_ns_by_file.values()),
        "profiled_total_ns_by_file": profiled_total_ns_by_file,
        "profiled_insn_total_ns_by_file": profiled_insn_total_ns_by_file,
    }


def ingest_call_tree(report, roots: list):
    indexed = {
        "program_name": report.get("program_name"),
        "total_duration": _total_duration_ns_from_report(report),
        "files": {},
        "global_args": set(),
    }

    acc = {}

    def merge_node(node):
        if not isinstance(node, dict):
            raise ValueError("call_tree node must be an object")
        loc = node.get("file")
        if not isinstance(loc, str):
            raise ValueError('call_tree node needs "file" as path:start:end')
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
    file_ids = report.get("file_ids")
    if not isinstance(file_ids, dict):
        raise ValueError("file_ids must be an object")
    roots = report.get("call_tree")
    if not isinstance(roots, list):
        raise ValueError("call_tree must be an array")
    normalized = normalize_call_tree(roots, file_ids)
    return ingest_call_tree(report, normalized), normalized


class AppState:
    def __init__(self):
        self.analysis_dir = ANALYSIS_DIR
        self.current_report: str | None = None
        self.index = None
        self.load_error = None
        self.call_tree_roots: list | None = None
        stems = list_analysis_report_stems(self.analysis_dir)
        self.current_report = stems[0] if stems else None
        self._load_current_report_from_disk()

    def _empty_index_report(self):
        return {"call_tree": [], "file_ids": {}, "verification_ns": 0}

    def _load_current_report_from_disk(self):
        empty = self._empty_index_report()
        self.call_tree_roots = None
        try:
            if not self.current_report:
                self.index, self.call_tree_roots = ingest_report(empty)
                if not self.analysis_dir.is_dir():
                    self.load_error = f"Analysis directory not found: {self.analysis_dir}"
                else:
                    self.load_error = f"No .json reports in {self.analysis_dir}"
                return

            path = resolve_analysis_report_path(self.analysis_dir, self.current_report)
            if path is None:
                self.index, self.call_tree_roots = ingest_report(empty)
                self.load_error = (
                    f"Report file missing or invalid name for {self.current_report!r}"
                )
                return

            with path.open("r", encoding="utf-8") as handle:
                report = json.load(handle)
            self.index, self.call_tree_roots = ingest_report(report)
            self.load_error = None
        except Exception as exc:  # pylint: disable=broad-except
            self.index, self.call_tree_roots = ingest_report(empty)
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
                    **bpf_insn_profiling_from_index(STATE.index),
                    "load_error": STATE.load_error,
                    "profiled_files_count": len(STATE.index.get("files", {})),
                    "bpf_insn_count": STATE.index.get("bpf_insn_count"),
                    "bpf_insns": STATE.index.get("bpf_insns"),
                    "kernel_compiler": STATE.index.get("kernel_compiler"),
                    "profile_stats": STATE.index.get("profile_stats"),
                    "trace_record_count": STATE.index.get("trace_record_count"),
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

            call_tree_payload: list = []
            if STATE.call_tree_roots:
                call_tree_payload = prune_call_tree_for_file_arg(
                    STATE.call_tree_roots, rel_path, arg
                )

            self._write_json(
                {
                    "path": rel_path,
                    "lines": lines,
                    "line_stats": line_stats,
                    "max_total_ns": max_total,
                    "ranges": profile["ranges"],
                    "call_tree": call_tree_payload,
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
