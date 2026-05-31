#!/usr/bin/env python3
"""Serve the trace analyser report viewer and analysis JSON APIs."""

import json
import os
import re
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HOST = "127.0.0.1"
PORT = 8000
_SERVER_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _SERVER_ROOT.parent
_DEFAULT_ANALYSIS_DIR = (_REPO_ROOT / "profiler" / "out" / "analysis").resolve()
_DEFAULT_AGGREGATED_DIR = (_REPO_ROOT / "profiler" / "out" / "aggregated").resolve()
ANALYSIS_DIR = Path(
    os.environ.get("ANALYSIS_DIR", str(_DEFAULT_ANALYSIS_DIR))
).resolve()
AGGREGATED_DIR = Path(
    os.environ.get("AGGREGATED_DIR", str(_DEFAULT_AGGREGATED_DIR))
).resolve()
_DEFAULT_KERNEL_PATCH_PATH = (_REPO_ROOT / "kernel-patch").resolve()
KERNEL_PATCH_PATH = Path(
    os.environ.get("KERNEL_PATCH_PATH", str(_DEFAULT_KERNEL_PATCH_PATH))
).resolve()
_CATALOG_PEEK_BYTES = 64 * 1024
_PROGRAM_NAME_RE = re.compile(r'"program_name"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"')
_VERIFICATION_TIME_RE = re.compile(r'"verification_time"\s*:\s*(\d+)')
_AGGREGATED_RE = re.compile(r'"aggregated"\s*:\s*true')

REPORT_SOURCES = {
    "analysis": ANALYSIS_DIR,
    "aggregated": AGGREGATED_DIR,
}


def list_report_stems(report_dir: Path) -> list[str]:
    if not report_dir.is_dir():
        return []
    return sorted(p.stem for p in report_dir.glob("*.json") if p.is_file())


def resolve_report_path(report_dir: Path, stem: str) -> Path | None:
    if not stem or "/" in stem or "\\" in stem or stem.startswith("."):
        return None
    root = report_dir.resolve()
    candidate = (root / f"{stem}.json").resolve()
    if candidate.parent != root:
        return None
    return candidate if candidate.is_file() else None


def parse_report_id(report_id: str) -> tuple[str, str] | None:
    if not report_id or report_id.startswith(".") or ".." in report_id:
        return None
    if "/" in report_id:
        source, stem = report_id.split("/", 1)
        if source not in REPORT_SOURCES or not stem or "/" in stem or stem.startswith("."):
            return None
        return source, stem
    return "analysis", report_id


def resolve_report_by_id(report_id: str) -> Path | None:
    parsed = parse_report_id(report_id)
    if parsed is None:
        return None
    source, stem = parsed
    return resolve_report_path(REPORT_SOURCES[source], stem)


def _peek_report_meta(report_path: Path) -> dict:
    try:
        with report_path.open("rb") as handle:
            chunk = handle.read(_CATALOG_PEEK_BYTES)
    except OSError:
        return {}
    text = chunk.decode("utf-8", errors="replace")
    meta: dict = {}
    name_match = _PROGRAM_NAME_RE.search(text)
    if name_match:
        meta["program_name"] = json.loads(f'"{name_match.group(1)}"')
    time_match = _VERIFICATION_TIME_RE.search(text)
    if time_match:
        try:
            meta["verification_time"] = int(time_match.group(1))
        except ValueError:
            pass
    if _AGGREGATED_RE.search(text):
        meta["aggregated"] = True
    return meta


def report_path_to_patch_rel(report_path: str) -> str:
    """Map analyser paths (e.g. kernel/bpf/verifier.c) under kernel-patch/."""
    rel = report_path.strip("/").replace("\\", "/")
    if rel.startswith("kernel/"):
        rel = rel[len("kernel/") :]
    return rel


def safe_patch_join(rel_path: str) -> Path:
    rel = report_path_to_patch_rel(rel_path)
    if not rel or rel.startswith(".."):
        raise ValueError("invalid path")
    root = KERNEL_PATCH_PATH.resolve()
    candidate = (root / rel).resolve()
    candidate.relative_to(root)
    return candidate


def serve_source_file(rel_path: str) -> dict:
    try:
        source_path = safe_patch_join(rel_path)
    except ValueError as err:
        return {"error": "invalid path", "detail": str(err)}

    if not source_path.is_file():
        return {
            "error": "file not found",
            "requested_path": rel_path,
            "resolved_path": str(source_path),
            "kernel_patch_path": str(KERNEL_PATCH_PATH),
        }

    try:
        content = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        return {"error": "failed to read file", "detail": str(err)}

    suffix = source_path.suffix.lower()
    language = "c" if suffix in {".c", ".h"} else "plaintext"

    return {
        "path": rel_path.strip("/"),
        "patch_rel": report_path_to_patch_rel(rel_path),
        "resolved_path": str(source_path),
        "language": language,
        "content": content,
    }


def _catalog_for_source(source: str, report_dir: Path) -> list[dict]:
    catalog = []
    for stem in list_report_stems(report_dir):
        entry: dict = {
            "id": f"{source}/{stem}",
            "label": stem,
            "source": source,
        }
        path = resolve_report_path(report_dir, stem)
        if path is None:
            catalog.append(entry)
            continue
        entry.update(_peek_report_meta(path))
        if source == "aggregated":
            entry["aggregated"] = True
        catalog.append(entry)
    return catalog


def reports_catalog() -> list[dict]:
    catalog = _catalog_for_source("analysis", ANALYSIS_DIR)
    catalog.extend(_catalog_for_source("aggregated", AGGREGATED_DIR))
    return catalog


class TraceReportHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(_SERVER_ROOT / "static"), **kwargs)

    def log_message(self, format, *args):
        if os.environ.get("VISUALIZER_QUIET"):
            return
        super().log_message(format, *args)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/reports":
            self._send_json(reports_catalog())
            return
        if parsed.path.startswith("/api/report/"):
            report_id = unquote(
                parsed.path.removeprefix("/api/report/").strip("/")
            )
            self._serve_report(report_id)
            return
        if parsed.path == "/api/source":
            query = parse_qs(parsed.query)
            rel_path = query.get("path", [""])[0]
            if not rel_path:
                self._send_error(HTTPStatus.BAD_REQUEST, "missing path")
                return
            payload = serve_source_file(rel_path)
            if "error" in payload:
                status = (
                    HTTPStatus.NOT_FOUND
                    if payload["error"] == "file not found"
                    else HTTPStatus.BAD_REQUEST
                )
                self._send_json(payload, status=status)
                return
            self._send_json(payload)
            return
        return super().do_GET()

    def _serve_report(self, report_id: str):
        path = resolve_report_by_id(report_id)
        if path is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Report not found")
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(err))
            return
        self._send_json(data)

    def _send_json(self, payload, status: HTTPStatus = HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str):
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer((HOST, PORT), TraceReportHandler)
    print(f"Trace report visualizer at http://{HOST}:{PORT}/")
    print(f"Analysis directory: {ANALYSIS_DIR}")
    print(f"Aggregated directory: {AGGREGATED_DIR}")
    print(f"Kernel patch sources: {KERNEL_PATCH_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
