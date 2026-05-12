import json
import struct
from pathlib import Path

from analyser import TraceAnalyser
from profiler_types import BPFInsn, ProfilingResult, Record

RESULTS_DIR = Path("out/results")
ANALYSIS_DIR = Path("out/analysis")


def fix_program_name(name: str) -> str:
    return name.replace("/", ".")


def result_bin_paths(name: str) -> list[Path]:
    base = fix_program_name(name)
    if not RESULTS_DIR.is_dir():
        return []
    out: list[Path] = []
    exact = RESULTS_DIR / f"{base}.bin"
    if exact.is_file():
        out.append(exact)
    prefix = f"{base}_"
    numbered = sorted(
        RESULTS_DIR.glob(f"{base}_*.bin"),
        key=lambda p: (
            int(p.stem[len(prefix) :])
            if p.stem.startswith(prefix) and p.stem[len(prefix) :].isdigit()
            else 10**9
        ),
    )
    out.extend(p for p in numbered if p not in out)
    return out


def _read_block(f, item_size: int, from_bytes):
    hdr = f.read(4)
    if len(hdr) != 4:
        raise ValueError("corrupt profile: short header")
    (n,) = struct.unpack("<I", hdr)
    blob = f.read(n * item_size)
    if len(blob) != n * item_size:
        raise ValueError("corrupt profile: truncated block")
    return [from_bytes(blob[i * item_size : (i + 1) * item_size]) for i in range(n)]


def read_profile_file(path: str | Path, program_name: str) -> ProfilingResult:
    with open(path, "rb") as f:
        program = _read_block(f, BPFInsn.size(), BPFInsn.from_bytes)
        trace = _read_block(f, Record.size(), Record.from_bytes)
    return ProfilingResult(program_name, program, trace)


def save_result(result: ProfilingResult):
    name = fix_program_name(result.program_name)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / f"{name}.bin", "wb") as f:
        f.write(struct.pack("<I", len(result.program)))
        for insn in result.program:
            f.write(bytes(insn))
        f.write(struct.pack("<I", len(result.trace)))
        for rec in result.trace:
            f.write(bytes(rec))


def load_analysis(name: str) -> dict:
    path = ANALYSIS_DIR / f"{fix_program_name(name)}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_analysis(name: str, analyser: TraceAnalyser):
    path = ANALYSIS_DIR / f"{fix_program_name(name)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(analyser.to_json(), encoding="utf-8")
