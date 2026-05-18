import json
import sys
from pathlib import Path
from time import time

from profiler_types import BPFInsn, NO_ARG, ProfileStats, Record, RecordType
from utils import find_block_end, find_block_start


class _NoopProgress:
	def update(self, n: int = 1) -> None:
		pass

	def close(self) -> None:
		pass

	def __enter__(self):
		return self

	def __exit__(self, *_args) -> None:
		pass

	def iter(self, iterable):
		yield from iterable


_MAX_PROGRESS_UPDATES = 8


class _ProgressBar:
	def __init__(self, total: int, desc: str = "", enabled: bool = True, width: int = 36):
		self.total = int(total)
		self.desc = desc
		self.enabled = enabled and self.total > 0
		self.width = width
		self.n = 0
		self._tty = enabled and sys.stdout.isatty()
		self._step = max(1, (self.total + _MAX_PROGRESS_UPDATES - 1) // _MAX_PROGRESS_UPDATES)
		self._last_render_n = 0

	def _render(self, final: bool = False) -> None:
		pct = self.n / self.total
		filled = int(self.width * pct)
		bar = "#" * filled + "-" * (self.width - filled)
		line = f"{self.desc} |{bar}| {self.n}/{self.total} ({100 * pct:.0f}%)"
		if self._tty and not final:
			sys.stdout.write(f"\r{line}")
		else:
			sys.stdout.write(f"{line}\n")
		sys.stdout.flush()
		self._last_render_n = self.n

	def _should_render(self) -> bool:
		if self.n >= self.total:
			return True
		if self.n - self._last_render_n < self._step:
			return False
		return self.n % self._step == 0

	def update(self, n: int = 1) -> None:
		if not self.enabled:
			return
		self.n = min(self.n + n, self.total)
		if self._should_render():
			self._render(final=self.n >= self.total)

	def close(self) -> None:
		if not self.enabled:
			return
		if self._tty:
			self._render(final=True)
		elif self.n < self.total:
			self.n = self.total
			self._render(final=True)

	def __enter__(self):
		if self.enabled and not self._tty:
			print(f"{self.desc}:", flush=True)
		return self

	def __exit__(self, *_args) -> None:
		self.close()

	def iter(self, iterable):
		if not self.enabled:
			yield from iterable
			return
		for item in iterable:
			yield item
			self.update(1)


def _progress(total: int, desc: str, enabled: bool) -> _ProgressBar | _NoopProgress:
	if enabled and total > 0:
		return _ProgressBar(total, desc)
	return _NoopProgress()

_KERNEL_ROOT = Path("/mnt/linux") if Path("/mnt/linux").is_dir() else Path("../linux")

with open(_KERNEL_ROOT / "kernel/bpf/file_ids.json") as f:
	file_ids = json.load(f)

def _exclusive_and_children(
	records: list[Record], *, progress: _ProgressBar | None = None
) -> tuple[list[int], list[list[int]], list[int]]:
	"""Build parent/child links and exclusive times (intervals assumed properly nested)."""
	n = len(records)
	if n == 0:
		return [], [], []

	starts = [r.start_time for r in records]
	ends = [r.end_time for r in records]
	durations = [e - s for s, e in zip(starts, ends)]
	order = sorted(range(n), key=lambda i: (starts[i], -ends[i]))

	children: list[list[int]] = [[] for _ in range(n)]
	stack: list[int] = []
	for i in order:
		while stack:
			j = stack[-1]
			if starts[j] < starts[i] and ends[j] > ends[i]:
				break
			stack.pop()
		if stack:
			children[stack[-1]].append(i)
		stack.append(i)
		if progress is not None:
			progress.update(1)

	exclusive = [0] * n
	for i in range(n):
		child_total = 0
		for c in children[i]:
			child_total += durations[c]
		exclusive[i] = max(0, durations[i] - child_total)
	return exclusive, children, durations


_site_cache: dict[tuple[str, int, str], tuple[str, int, int, str | None]] = {}


def _site(ev: Record, kernel: str) -> tuple[str, int, int, str | None]:
	if ev.get_record_type() == RecordType.CALL:
		return (str(ev.file_id), int(ev.line), int(ev.line), None)
	if ev.get_record_type() != RecordType.BLOCK:
		raise ValueError(f"timed record expected, got {ev.get_record_type()}")

	cache_key = (str(ev.file_id), int(ev.line), kernel)
	cached = _site_cache.get(cache_key)
	if cached is not None:
		return cached

	file_name = file_ids.get(str(ev.file_id), f"<unknown:{ev.file_id}>")
	path = str(_KERNEL_ROOT / file_name)
	if kernel == "clang":
		lo, hi = find_block_start(path, ev.line), ev.line
	elif kernel == "gcc":
		lo, hi = ev.line, find_block_end(path, ev.line)
	else:
		raise ValueError(f"unsupported kernel compiler: {kernel}")
	result = (str(ev.file_id), int(lo), int(hi), None)
	_site_cache[cache_key] = result
	return result


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
		program: list[BPFInsn],
		stats: ProfileStats,
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
		self._durations: list[int] = []
		self._site_strs: list[str] = []
		self._overhead_model: tuple[float, float] = (0, 0)
		self._show_progress = True

	def analyse(
		self,
		verbose: bool = True,
		kernel_compiler: str = "clang",
		estimate_overhead: bool = False,
		show_progress: bool = True,
	):
		self._show_progress = show_progress
		_site_cache.clear()
		verbose = True
		if verbose:
			print(
				f"Analysing trace for {self.program_name!r} with {len(self.trace)} records "
				f"and {len(self._program)} BPF instructions..."
			)

		analysis_start_time = time()
		self.kernel_compiler = kernel_compiler
		v0 = v1 = None
		timed: list[Record] = []
		args: list[int | None] = []

		block_t = RecordType.BLOCK.value
		call_t = RecordType.CALL.value
		start_t = RecordType.START.value
		end_t = RecordType.END.value
		with _progress(len(self.trace), "Scanning trace", self._show_progress) as scan_bar:
			for ev in scan_bar.iter(self.trace):
				t = ev.type
				if t == start_t:
					v0 = ev.start_time
				elif t == end_t:
					v1 = ev.end_time
				elif t == block_t or t == call_t:
					timed.append(ev)
					args.append(ev.arg if ev.arg != NO_ARG else None)

		with _progress(len(timed), "Building call tree", self._show_progress) as tree_bar:
			exc, ch, durations = _exclusive_and_children(
				timed, progress=tree_bar if isinstance(tree_bar, _ProgressBar) else None
			)
		mark = [False] * len(timed)
		for row in ch:
			for c in row:
				mark[c] = True
		roots = [i for i in range(len(timed)) if not mark[i]]

		self._timed = timed
		self._durations = durations
		sites: list[tuple[str, int, int, str | None]] = []
		site_strs: list[str] = []
		with _progress(len(timed), "Resolving source sites", self._show_progress) as site_bar:
			for e in site_bar.iter(timed):
				sk = _site(e, kernel_compiler)
				sites.append(sk)
				site_strs.append(sk[3] if sk[3] else _site_str(sk))
		self._sites = sites
		self._site_strs = site_strs
		self._args = args
		self._exclusive = exc
		self._children = ch
		self._roots = roots
		self.total_duration_ns = (v1 - v0) if v0 is not None and v1 is not None else 0
		analysis_end_time = time()
		if verbose:
			print(f"Total verification time: {self.total_duration_ns / 1e6:.2f} ms")
			print(f"Analysis time: {analysis_end_time - analysis_start_time:.2f} s")
		if estimate_overhead:
			self._model_overhead()
			self._apply_overhead_model(show_progress=self._show_progress)
			if verbose:
				print(f"Total verification time after overhead estimation: {self.total_duration_ns / 1e6:.2f} ms")

	def _model_overhead(self):
		def t(nodes: list[int]):
			x = []
			for i in nodes:
				x.append(len(self._children[i]))
			return x

		n1 = self._roots[:5]
		n2 = self._roots[-5:]
		x = t(n1)
		if x != t(n2):
			raise ValueError("unexpected tree structure, cannot estimate overhead")
		avg = []
		for a, b in zip(n1, n2):
			avg.append((self._durations[a] + self._durations[b]) / 2)

		self._overhead_model = linear_fit(x, avg)
		print(f"Estimated overhead model: {self._overhead_model[0]:.2f} ns per child + {self._overhead_model[1]:.2f} ns")

	def _apply_overhead_model(self, show_progress: bool = False):
		n_timed = len(self._timed)

		def apply(i: int, bar: _ProgressBar | _NoopProgress) -> float:
			estimated_overhead = self._overhead_model[0] * len(self._children[i]) + self._overhead_model[1]
			for c in self._children[i]:
				estimated_overhead += apply(c, bar)
			if estimated_overhead > self._exclusive[i]:
				estimated_overhead = self._exclusive[i]
			self._exclusive[i] -= estimated_overhead
			bar.update(1)
			return estimated_overhead

		with _progress(n_timed, "Applying overhead model", show_progress) as overhead_bar:
			total_overhead = self._overhead_model[0] * len(self._roots) + self._overhead_model[1]
			for r in self._roots:
				total_overhead += apply(r, overhead_bar)
		self.total_duration_ns = self.total_duration_ns - total_overhead

	def _node(self, i: int) -> dict:
		d: dict = {
			"f": self._site_strs[i],
			"i": self._durations[i],
			"e": self._exclusive[i],
		}
		if self._args[i] is not None:
			d["a"] = self._args[i]
		ch = self._children[i]
		if ch:
			d["c"] = [self._node(c) for c in ch]
		return d

	def to_json(self) -> str:
		call_tree: list[dict] = []
		with _progress(len(self._roots), "Serializing call tree", self._show_progress) as json_bar:
			for r in json_bar.iter(self._roots):
				call_tree.append(self._node(r))
		out: dict = {
			"program_name": self.program_name,
			"verification_ns": self.total_duration_ns,
			"kernel_compiler": self.kernel_compiler,
			"trace_record_count": len(self.trace),
			"file_ids": file_ids,
			"profile_stats": self._stats.to_json_dict(),
			"bpf_insns": [_insn_dict(i) for i in self._program],
			"call_tree": call_tree,
		}
		return json.dumps(out, separators=(",", ":"))

def linear_fit(x, y):
	n = len(x)

	x_mean = sum(x) / n
	y_mean = sum(y) / n

	numerator = sum((xi - x_mean) * (yi - y_mean)
					for xi, yi in zip(x, y))

	denominator = sum((xi - x_mean) ** 2 for xi in x)

	m = numerator / denominator
	b = y_mean - m * x_mean

	return m, b