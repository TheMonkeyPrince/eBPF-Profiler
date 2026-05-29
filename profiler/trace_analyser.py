import json
from pathlib import Path
from time import time
from dataclasses import dataclass, asdict

from profiler_types import *
from utils import find_block_start, find_call_name
from disasm import disasm_program, disasm_insn_name
from call_tree import SiteTree, RecordSite, CallTree

SUPPORTED_KERNEL_COMPILERS = "clang"
_KERNEL_ROOT = Path("/mnt/linux") if Path("/mnt/linux").is_dir() else Path("../linux")

with open(_KERNEL_ROOT / "kernel/bpf/file_ids.json") as f:
	file_ids = json.load(f)

@dataclass
class TraceAnalyserResult:
	program_name: str
	verification_stats: dict
	stats: dict
	site_tree: dict

	def to_json(self) -> str:
		return json.dumps(asdict(self), indent=2)
	
	@staticmethod
	def from_json(json_str: str) -> 'TraceAnalyserResult':
		data = json.loads(json_str)
		return TraceAnalyserResult(**data)

class TraceAnalyser:
	def __init__(
		self,
		profiling_result: ProfilingResult
	):
		self.profiling_result = profiling_result
		self.result: TraceAnalyserResult = None
		self.site_tree: SiteTree = None

	def analyse(self, verbose=False) -> TraceAnalyserResult | None:
		print(
			f"Analysing trace for {str(self.profiling_result.program_info)!r} (program {self.profiling_result.trace_index}) with {len(self.profiling_result.records)} records..."
		)
		analysis_start_time = time()

		if len(self.profiling_result.records) == 0:
			print("No records to analyse.")
			return None

		if self.profiling_result.records[0].get_record_type() == RecordType.START:
			verifier_start_time = self.profiling_result.records[0].start_time
		else:
			raise ValueError(
				f"First record is not a START record ({self.profiling_result.records[0].get_record_type().name}). The trace is incomplete."
			)

		if self.profiling_result.records[-1].get_record_type() == RecordType.END:
			verifier_end_time = self.profiling_result.records[-1].end_time
		else:
			raise ValueError(
				f"Last record is not an END record ({self.profiling_result.records[-1].get_record_type().name}). The trace is incomplete."
			)

		self.site_tree = SiteTree(CallTree(self.profiling_result.records[1:-1]))

		self.result = TraceAnalyserResult(
			program_name=str(self.profiling_result.program_info),
			verification_stats=self.profiling_result.stats.to_json_dict(),
			stats={
				"verification_time": verifier_end_time - verifier_start_time,
				"program_length": len(self.profiling_result.program),
				"num_records": len(self.profiling_result.records),
				"num_sites": self.site_tree.number_of_sites(),
			},
			site_tree=self.site_tree.serialize(resolve_site=resolve_site),
		)

		self._compute_site_tree_stats()
		self._compute_bpf_insn_stats()

		analysis_end_time = time()
		self.result.stats["analysis_time"] = f"{(analysis_end_time - analysis_start_time):.2f}s"

		if verbose:
			print(len(self.result.site_tree.roots), "root sites found in the call tree.")
		print(f"Total verification time: {self.result.stats['verification_time'] / 1e6:.2f} ms")
		print(f"Analysis completed in {self.result.stats['analysis_time']}.")

		return self.result

	def _compute_bpf_insn_stats(self):
		durations_per_insn: dict[BPFInsnCode, list[float]] = {}
		insn_counts: dict[str, int] = {}
		for insn in self.profiling_result.program:
			insn_name = disasm_insn_name(insn)
			if insn_name not in durations_per_insn:
				durations_per_insn[insn_name] = []
				insn_counts[insn_name] = 0
			insn_counts[insn_name] += 1
			
		def traverse_recordsite(site: RecordSite):
			for insn_idx, durations in site.durations.items():
				if insn_idx == Record.NO_INSN_IDX:
					continue
				insn_name = disasm_insn_name(self.profiling_result.program[insn_idx])
				durations_per_insn[insn_name].extend(durations)
			for child in site.children:
				traverse_recordsite(child)

		for recordsite in self.site_tree.roots:
			traverse_recordsite(recordsite)

		durations_per_insn_type: dict[str, tuple[int, int, float]] = {}
		for insn_name, durations in durations_per_insn.items():
			if insn_counts[insn_name] == 0:
				if durations:
					raise ValueError(f"Insn name {insn_name} has durations but no counts, which should be impossible.")
				durations_per_insn_type[insn_name] = (0, 0, 0)
			else:
				durations_per_insn_type[insn_name] = (insn_counts[insn_name], sum(durations), sum(durations) / insn_counts[insn_name])

		self.result.stats["durations_per_insn_type"] = dict(sorted(durations_per_insn_type.items(), key=lambda item: item[1][2], reverse=True))

	def _compute_site_tree_stats(self):
		def to_json_dict(site: RecordSite, parent_duration: float) -> tuple[str, dict]:
			filename, end_line_or_func_name = resolve_site(
				site.file_id, site.line, site.is_call
			)
			key = f"{filename}:{site.line}:{end_line_or_func_name}"

			percent_of_total = (
				site.inclusive_duration / float(self.result.stats['verification_time']) * 100
			)
			percent_of_parent = site.inclusive_duration / float(parent_duration) * 100

			if percent_of_total > 100.0:
				raise ValueError(
					f"Site {key} has inclusive duration {site.inclusive_duration} which is greater than total verification time {self.result.stats['verification_time']}. This should be impossible."
				)
			if percent_of_parent > 100.0:
				raise ValueError(
					f"Site {key} has inclusive duration {site.inclusive_duration} which is greater than parent duration {parent_duration}. This should be impossible."
				)

			return [
				key,
				[
					percent_of_total,
					percent_of_parent,
					dict(
						sorted(
							[
								to_json_dict(child, site.inclusive_duration)
								for child in site.children
							],
							key=lambda item: item[1][1],
							reverse=True,
						)
					),
				],
			]

		self.result.stats["site_tree"] = []
		for root in self.site_tree.roots:
			self.result.stats["site_tree"].append(to_json_dict(root, self.result.stats['verification_time']))
		self.result.stats["site_tree"] = dict(
			sorted(self.result.stats["site_tree"], key=lambda item: item[1][1], reverse=True)
		)


# Cache for mapping (file_id, line) to (filename, line_number | function name)
_site_cache: dict[Site, tuple[str, LineNumber | FunctionName]] = {}
def resolve_site(
	file_id: int, line: int, is_call: bool
) -> tuple[str, int | str] | None:
	if (file_id, line) in _site_cache:
		return _site_cache[(file_id, line)]

	if str(file_id) not in file_ids:
		raise ValueError(f"Unknown file_id: {file_id}")

	filename = file_ids[str(file_id)]
	full_path = _KERNEL_ROOT / filename
	if is_call:
		result = (filename, find_call_name(full_path, line))
	else:
		result = (filename, find_block_start(full_path, line))
	_site_cache[(file_id, line)] = result
	return result
