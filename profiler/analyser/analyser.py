import json
import os
from dataclasses import dataclass
from time import perf_counter
from typing import Literal

from event import Event
from .utils import find_block_start, find_block_end

KERNEL_SOURCE_PATH = "/mnt/linux/"
if not os.path.isdir(KERNEL_SOURCE_PATH):
    KERNEL_SOURCE_PATH = "../linux/"


KernelCompiler = Literal["clang", "gcc"]


def _strictly_contains(outer: Event, inner: Event) -> bool:
    return (
        outer.start_time < inner.start_time and outer.end_time > inner.end_time
    )


def call_tree_exclusive_and_children(
    events: list[Event],
) -> tuple[list[int], list[list[int]]]:
    """
    For strict time nesting: immediate parent has largest outer start_time.
    Returns exclusive duration per occurrence and adjacency lists of child
    indices (siblings in trace order).
    """
    n = len(events)
    children: list[list[int]] = [[] for _ in range(n)]

    for i in range(n):
        ei = events[i]
        parent_j = -1
        best_parent_start = -1
        for j in range(n):
            if i == j:
                continue
            ej = events[j]
            if _strictly_contains(ej, ei) and ej.start_time > best_parent_start:
                best_parent_start = ej.start_time
                parent_j = j
        if parent_j >= 0:
            children[parent_j].append(i)

    exclusive: list[int] = []
    for i in range(n):
        inc = events[i].duration()
        child_sum = sum(events[c].duration() for c in children[i])
        exclusive.append(max(0, inc - child_sum))
    return exclusive, children


@dataclass(frozen=True, slots=True)
class SiteKey:
    file: str
    start_line: int
    end_line: int
    function: str | None


def site_compact(site: SiteKey) -> str:
    """Compact location: kernel/path/file.c:start:end"""
    return f"{site.file}:{site.start_line}:{site.end_line}"


def resolve_site_key(ev: Event, kernel_compiler: KernelCompiler) -> SiteKey:
    if ev.get_event_type() == Event.EVENT_TYPE.FUNC_TIMER_RESULT:
        return SiteKey(
            file=ev.file.decode(),
            start_line=int(ev.line),
            end_line=int(ev.line),
            function=ev.func_name.decode(),
        )
    if ev.get_event_type() != Event.EVENT_TYPE.BLOCK_TIMER_RESULT:
        raise ValueError(f"timed event expected, got {ev.get_event_type()}")
    path = KERNEL_SOURCE_PATH + ev.file.decode()
    if kernel_compiler == "clang":
        start_line = find_block_start(path, ev.line)
        end_line = ev.line
    elif kernel_compiler == "gcc":
        start_line = ev.line
        end_line = find_block_end(path, start_line)
    else:
        raise ValueError(f"Unsupported kernel compiler: {kernel_compiler}")
    return SiteKey(
        file=ev.file.decode(),
        start_line=int(start_line),
        end_line=int(end_line),
        function=None,
    )


class TraceAnalyser:
    """Builds verifier timing as a nested call tree (interval containment)."""

    def __init__(self, program_name: str, trace: list[Event]):
        self.program_name = program_name
        self.trace = trace
        self.kernel_compiler: KernelCompiler = "clang"
        self.total_duration_ns = 0
        self.analysis_time_s = 0.0
        self._timed_events: list[Event] = []
        self._site_keys: list[SiteKey] = []
        self._timed_args: list[int | None] = []
        self._exclusive_ns: list[int] = []
        self._children: list[list[int]] = []
        self._root_indices: list[int] = []

    def analyse(self, verbose: bool = True, kernel_compiler: KernelCompiler = "clang"):
        self.kernel_compiler = kernel_compiler
        t0 = perf_counter()

        verification_start_ns: int | None = None
        verification_end_ns: int | None = None
        timed_events: list[Event] = []
        timed_args: list[int | None] = []

        for ev in self.trace:
            match ev.get_event_type():
                case Event.EVENT_TYPE.VERIFIER_START:
                    verification_start_ns = ev.timestamp
                case Event.EVENT_TYPE.VERIFIER_END:
                    verification_end_ns = ev.timestamp
                case Event.EVENT_TYPE.BLOCK_TIMER_RESULT | Event.EVENT_TYPE.FUNC_TIMER_RESULT:
                    timed_events.append(ev)
                    ta: int | None
                    if ev.get_event_type() == Event.EVENT_TYPE.BLOCK_TIMER_RESULT:
                        ta = ev.arg if ev.has_arg() else None
                    else:
                        ta = None
                    timed_args.append(ta)
                    if ev.get_event_type() == Event.EVENT_TYPE.FUNC_TIMER_RESULT:
                        print(f"Function: {ev.func_name.decode()}, Args: {ev.arg}")

        site_keys = [resolve_site_key(e, kernel_compiler) for e in timed_events]
        exclusive_ns, children = call_tree_exclusive_and_children(timed_events)

        child_mark = [False] * len(timed_events)
        for chs in children:
            for c in chs:
                child_mark[c] = True
        roots = [i for i in range(len(timed_events)) if not child_mark[i]]

        self._timed_events = timed_events
        self._site_keys = site_keys
        self._timed_args = timed_args
        self._exclusive_ns = exclusive_ns
        self._children = children
        self._root_indices = roots

        if verification_start_ns is not None and verification_end_ns is not None:
            self.total_duration_ns = verification_end_ns - verification_start_ns
        else:
            self.total_duration_ns = 0

        self.analysis_time_s = perf_counter() - t0

        if verbose:
            print(
                "Total verification time: "
                f"{self.total_duration_ns / 1_000_000:.2f} ms"
            )
        print(f"Analysis completed in {self.analysis_time_s:.2f} seconds")

    def _serialize_node(self, i: int) -> dict:
        ev = self._timed_events[i]
        sk = self._site_keys[i]
        node: dict = {
            "file": site_compact(sk),
            "inclusive_ns": ev.duration(),
            "exclusive_ns": self._exclusive_ns[i],
        }
        if sk.function:
            node["function"] = sk.function
        arg = self._timed_args[i]
        if arg is not None:
            node["arg"] = arg
        ch = self._children[i]
        if ch:
            node["children"] = [self._serialize_node(c) for c in ch]
        return node

    def _call_tree_payload(self) -> list[dict]:
        return [self._serialize_node(r) for r in self._root_indices]

    def to_json(self) -> str:
        payload = {
            "schema_version": 3,
            "program_name": self.program_name,
            "total_duration_ns": self.total_duration_ns,
            "total_duration": self.total_duration_ns,
            "meta": {
                "kernel_compiler": self.kernel_compiler,
                "analysis_time_s": round(self.analysis_time_s, 6),
            },
            "verification": {"duration_ns": self.total_duration_ns},
            "call_tree": self._call_tree_payload(),
        }
        return json.dumps(payload, indent=2)
