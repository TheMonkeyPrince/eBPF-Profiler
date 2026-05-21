import json
from pathlib import Path
from time import time

from profiler_types import ProfilingResult, Record, RecordType, BPFInsnCode
from utils import find_block_start, find_call_name

SUPPORTED_KERNEL_COMPILERS = ("clang")
_KERNEL_ROOT = Path("/mnt/linux") if Path("/mnt/linux").is_dir() else Path("../linux")

with open(_KERNEL_ROOT / "kernel/bpf/file_ids.json") as f:
	file_ids = json.load(f)

FileId = int
LineNumber = int
FunctionName = str
InsnIdx = int
Site = tuple[FileId, LineNumber]

class SiteInfo:
	def __init__(self, file_id: int, line: int, is_call: bool):
		self.file_id = file_id
		self.line = line
		self.is_call = is_call
		self.durations: dict[InsnIdx, list[int]] = {}
		self.children: list[SiteInfo] = []
		self._inclusive_duration = -1
		self._exclusive_duration = -1
		self._children_duration = -1

	def add_duration(self, insn_idx: int, duration: int):
		if insn_idx not in self.durations:
			self.durations[insn_idx] = []
		self.durations[insn_idx].append(duration)

	@property
	def inclusive_duration(self) -> int:
		if self._inclusive_duration >= 0:
			return self._inclusive_duration
		
		self._inclusive_duration = sum(sum(durations) for durations in self.durations.values())
		return self._inclusive_duration

	@property
	def exclusive_duration(self) -> int:
		if self._exclusive_duration >= 0:
			return self._exclusive_duration
		
		self._exclusive_duration = self.inclusive_duration - self.children_duration
		return self._exclusive_duration
	
	@property
	def children_duration(self) -> int:
		if self._children_duration >= 0:
			return self._children_duration
		
		self._children_duration = sum(child.exclusive_duration for child in self.children)
		return self._children_duration
	
	def to_json_dict(self, compact: bool = False) -> tuple[str, dict]:
		filename, end_line_or_func_name = SiteInfo.resolve_site(self.file_id, self.line, self.is_call)
		if compact:
			key = f"{self.file_id}:{self.line}:{end_line_or_func_name}"
		else:
			key = f"{filename}:{self.line}:{end_line_or_func_name}"
		
		return [ key, {
				"durations" if not compact else "d": self.durations,
				"inclusive_duration" if not compact else "i": self.inclusive_duration,
				"exclusive_duration" if not compact else "e": self.exclusive_duration,
				"children" if not compact else "c": dict([child.to_json_dict() for child in self.children])
			}
		]

	# Cache for mapping (file_id, line) to (filename, line_number | function name)
	_site_cache: dict[Site, tuple[str, LineNumber | FunctionName]] = {}
	@staticmethod
	def resolve_site(file_id: int, line: int, is_call: bool) -> tuple[str, int | str] | None:
		if (file_id, line) in SiteInfo._site_cache:
			return SiteInfo._site_cache[(file_id, line)]

		if str(file_id) not in file_ids:
			raise ValueError(f"Unknown file_id: {file_id}")

		filename = file_ids[str(file_id)]
		full_path = _KERNEL_ROOT / filename
		if is_call:
			result = (filename, find_call_name(full_path, line))
		else:
			result = (filename, find_block_start(full_path, line))
		SiteInfo._site_cache[(file_id, line)] = result
		return result


class NewTraceAnalyser:
	def __init__(
		self,
		profiling_result: ProfilingResult,
		kernel_compiler = "clang",
	):
		if kernel_compiler not in SUPPORTED_KERNEL_COMPILERS:
			raise ValueError(f"Invalid kernel compiler: {kernel_compiler!r}")

		self.profiling_result = profiling_result
		self.kernel_compiler = kernel_compiler

		# Call tree representation: each site maps to a list of its children (call sites it directly called)
		self.roots: list[Site] = []
		self.site_info: dict[Site, SiteInfo] = {}

		self.normalized_durations_per_insn_code: dict[BPFInsnCode, float] = {}

	def analyse(self, verbose = False, show_progress = False):
		print(f"Analysing trace for {self.profiling_result.program_name!r} with {len(self.profiling_result.records)} records...")
		analysis_start_time = time()

		if len(self.profiling_result.records) == 0:
			print("No records to analyse.")
			return
		
		if self.profiling_result.records[0].get_record_type() == RecordType.START:
			verifier_start_time = self.profiling_result.records[0].start_time
		else:
			print(f"Warning: First record is not a START record ({self.profiling_result.records[0].get_record_type().name}). The trace is incomplete.")
			return
		
		if self.profiling_result.records[-1].get_record_type() == RecordType.END:
			verifier_end_time = self.profiling_result.records[-1].end_time
		else:
			print(f"Warning: Last record is not an END record ({self.profiling_result.records[-1].get_record_type().name}). The trace is incomplete.")
			return

		self.verification_time = verifier_end_time - verifier_start_time
		self._build_call_tree()
		self._compute_bpf_insn_stats()

		analysis_end_time = time()

		if verbose:
			print(len(self.roots), "root sites found in the call tree.")
		print(f"Total verification time: {self.verification_time / 1e6:.2f} ms")
		print(f"Analysis completed in {analysis_end_time - analysis_start_time:.2f} seconds.")
	
	def to_json(self, compact: bool = False) -> str:
		out = {
			"program_name": self.profiling_result.program_name,
			"verification_time": self.verification_time,
			"verification_stats": self.profiling_result.stats.to_json_dict(),
			"program": [i.to_json_dict(compact=compact) for i in self.profiling_result.program],
			"stats": {
					"normalized_durations_per_insn_code": self.normalized_durations_per_insn_code,
			},
			"call_tree": dict([root.to_json_dict(compact=compact) for root in self.roots]),
		}
		if compact:
			out["files"] = file_ids
			return json.dumps(out, separators=(",", ":"))
		return json.dumps(out, indent=2)
	
	def _build_call_tree(self):
		self.roots: list[SiteInfo] = []
		self.site_info: dict[Site, SiteInfo] = {}

		stack: list[Site] = []
		time_boundaries: dict[Site, tuple[int, int]] = {}
		for record in reversed(self.profiling_result.records):
			if record.get_record_type() == RecordType.START or record.get_record_type() == RecordType.END:
				continue
			
			cur_site = (record.file_id, record.line)
			time_boundaries[cur_site] = (record.start_time, record.end_time)
			if cur_site not in self.site_info:
				self.site_info[cur_site] = SiteInfo(record.file_id, record.line, record.get_record_type() == RecordType.CALL)
			self.site_info[cur_site].add_duration(record.insn_idx, record.duration())

			added = False
			while stack:
				top_site = stack[-1]
				if top_site == cur_site:
					# The current site is the same as the top of the stack, so we are still within that call
					break
				elif self.site_info[cur_site] in self.site_info[top_site].children:
					# The current site is a child of the top of the stack, so we are still within that call
					break
				else:
					if time_boundaries[cur_site][0] >= time_boundaries[top_site][0] and time_boundaries[cur_site][1] <= time_boundaries[top_site][1]:
						# The current site is within the time boundaries of the top of the stack, so it must be a child
						self.site_info[top_site].children.append(self.site_info[cur_site])
						added = True
						break
					else:
						stack.pop()

			stack.append(cur_site)		
			if not added:	
				if self.site_info[cur_site] not in self.roots:
					self.roots.append(self.site_info[cur_site])

	def _compute_bpf_insn_stats(self):
		durations_per_insn: dict[BPFInsnCode, list[float]] = {}
		insn_counts: dict[BPFInsnCode, int] = {}
		for insn in self.profiling_result.program:
			if insn.code not in durations_per_insn:
				durations_per_insn[insn.code] = []
				insn_counts[insn.code] = 0
			insn_counts[insn.code] += 1

		def traverse_site_info(site_info: SiteInfo):
			for insn_idx, durations in site_info.durations.items():
				if insn_idx == Record.NO_INSN_IDX:
					continue
				insn_code = self.profiling_result.program[insn_idx].code
				durations_per_insn[insn_code].extend(durations)
			for child in site_info.children:
				traverse_site_info(child)

		for site_info in self.roots:
			traverse_site_info(site_info)

		self.normalized_durations_per_insn_code: dict[BPFInsnCode, float] = {}
		for insn_code, durations in durations_per_insn.items():
			if insn_counts[insn_code] == 0:
				if durations:
					raise ValueError(f"Insn code {insn_code} has durations but no counts, which should be impossible.")
				self.normalized_durations_per_insn_code[insn_code] = 0
			else:
				self.normalized_durations_per_insn_code[insn_code] = sum(durations) / insn_counts[insn_code]

		self.normalized_durations_per_insn_code = dict(sorted(self.normalized_durations_per_insn_code.items(), reverse=True))