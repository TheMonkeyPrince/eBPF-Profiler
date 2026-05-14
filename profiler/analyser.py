import json
from pathlib import Path

from profiler_types import BPFInsn, ProfileStats, Record, RecordType
from utils import find_block_end, find_block_start

_KERNEL_ROOT = Path("/mnt/linux") if Path("/mnt/linux").is_dir() else Path("../linux")


def _contains(outer: Record, inner: Record) -> bool:
    return outer.start_time < inner.start_time and outer.end_time > inner.end_time


def _exclusive_and_children(records: list[Record]) -> tuple[list[int], list[list[int]]]:
    n = len(records)
    children: list[list[int]] = [[] for _ in range(n)]
    for i in range(n):
        ei = records[i]
        best_j, best_start = -1, -1
        for j in range(n):
            if i == j:
                continue
            ej = records[j]
            if _contains(ej, ei) and ej.start_time > best_start:
                best_start, best_j = ej.start_time, j
        if best_j >= 0:
            children[best_j].append(i)
    exclusive = []
    for i in range(n):
        inc = records[i].duration()
        ch = sum(records[c].duration() for c in children[i])
        exclusive.append(max(0, inc - ch))
    return exclusive, children


def _site(ev: Record, kernel: str) -> tuple[str, int, int, str | None]:
    if ev.get_record_type() == RecordType.CALL:
        return (ev.file.decode(), int(ev.line), int(ev.line), ev.func_name.decode())
    if ev.get_record_type() != RecordType.BLOCK:
        raise ValueError(f"timed record expected, got {ev.get_record_type()}")
    path = str(_KERNEL_ROOT / ev.file.decode())
    if kernel == "clang":
        lo, hi = find_block_start(path, ev.line), ev.line
    elif kernel == "gcc":
        lo, hi = ev.line, find_block_end(path, ev.line)
    else:
        raise ValueError(f"unsupported kernel compiler: {kernel}")
    return (ev.file.decode(), int(lo), int(hi), None)


def _site_str(t: tuple[str, int, int, str | None]) -> str:
    f, s, e, _ = t
    return f"{f}:{s}:{e}"


def _insn_dict(i: BPFInsn) -> dict:
    return {
        "code": int(i.code),
        "dst": i.dst_reg,
        "src": i.src_reg,
        "off": int(i.off),
        "imm": int(i.imm),
    }


class TraceAnalyser:
    def __init__(
        self,
        program_name: str,
        trace: list[Record],
        program: list[BPFInsn] | None = None,
        stats: ProfileStats | None = None,
    ):
        self.program_name = program_name
        self.trace = trace
        self._program = list(program) if program else []
        self._stats = stats
        self.kernel_compiler = "clang"
        self.total_duration_ns = 0
        self._timed: list[Record] = []
        self._sites: list[tuple[str, int, int, str | None]] = []
        self._args: list[int | None] = []
        self._exclusive: list[int] = []
        self._children: list[list[int]] = []
        self._roots: list[int] = []

    def analyse(self, verbose: bool = True, kernel_compiler: str = "clang"):
        if verbose:
            print(f"Analysing trace for {self.program_name!r} with {len(self.trace)} records and {len(self._program)} BPF instructions...")
        
        self.kernel_compiler = kernel_compiler
        v0 = v1 = None
        timed: list[Record] = []
        args: list[int | None] = []

        for ev in self.trace:
            match ev.get_record_type():
                case RecordType.START:
                    v0 = ev.start_time
                case RecordType.END:
                    v1 = ev.end_time
                case RecordType.BLOCK | RecordType.CALL:
                    timed.append(ev)
                    args.append(ev.arg if ev.has_arg() else None)

        exc, ch = _exclusive_and_children(timed)
        mark = [False] * len(timed)
        for row in ch:
            for c in row:
                mark[c] = True
        roots = [i for i in range(len(timed)) if not mark[i]]

        self._timed = timed
        self._sites = [_site(e, kernel_compiler) for e in timed]
        self._args = args
        self._exclusive = exc
        self._children = ch
        self._roots = roots
        self.total_duration_ns = (v1 - v0) if v0 is not None and v1 is not None else 0

        if verbose:
            print(f"Total verification time: {self.total_duration_ns / 1e6:.2f} ms")

    def _node(self, i: int) -> dict:
        ev, sk = self._timed[i], self._sites[i]
        d: dict = {
            "file": _site_str(sk),
            "inclusive_ns": ev.duration(),
            "exclusive_ns": self._exclusive[i],
        }
        if sk[3]:
            d["function"] = sk[3]
        if self._args[i] is not None:
            d["arg"] = self._args[i]
        ch = self._children[i]
        if ch:
            d["children"] = [self._node(c) for c in ch]
        return d

    def to_json(self) -> str:
        out: dict = {
            "program_name": self.program_name,
            "verification_ns": self.total_duration_ns,
            "kernel_compiler": self.kernel_compiler,
            "trace_record_count": len(self.trace),
            "call_tree": [self._node(r) for r in self._roots],
        }
        if self._program:
            out["bpf_insns"] = [_insn_dict(i) for i in self._program]
        if self._stats is not None:
            out["profile_stats"] = self._stats.to_json_dict()
        return json.dumps(out, indent=2)
