import json
from pathlib import Path
from time import time
from dataclasses import dataclass, asdict

from profiler_types import *
from utils import find_block_start, find_call_name
from disasm import disasm_program, disasm_insn_name
from call_tree import SiteTree, RecordSite, CallTree
from utils import stddev

SUPPORTED_KERNEL_COMPILERS = "clang"
_KERNEL_ROOT = Path("/mnt/linux") if Path("/mnt/linux").is_dir() else Path("../linux")

with open(_KERNEL_ROOT / "kernel/bpf/file_ids.json") as f:
	file_ids = json.load(f)

@dataclass
class TraceAnalyserResult:
	program_name: str
	verification_stats: dict
	stats: dict
	# site_tree: dict

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
			}
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
			filename, start_line_or_func_name = resolve_site(
				site.file_id, site.line, site.is_call
			)
			if site.is_call:
				key = f"{filename}:{site.line}:{start_line_or_func_name}"
			else:
				key = f"{filename}:{start_line_or_func_name}:{site.line}"

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

			nb_visits = sum(len(durations) for durations in site.durations.values())
			avg_duration_per_visit = site.inclusive_duration / float(nb_visits)

			stats = {
				"percent_of_total": percent_of_total,
				"percent_of_parent": percent_of_parent,
				"inclusive_duration": site.inclusive_duration,
				"exclusive_duration": site.exclusive_duration,
				"nb_visits": nb_visits,
				"avg_duration_per_visit": avg_duration_per_visit,
			}
			
			if list(site.durations.keys())[0] != Record.NO_INSN_IDX:
				def compute_stats(durations: dict[type, list[int]], reference: float, normalize: bool) -> dict[type, dict[str, int | float]]:
					def compute_score(durations: list[int], normalize: bool) -> float:
						if normalize:
							agg_duration = sum(durations) / float(len(durations))
						else:
							agg_duration = sum(durations)
						return agg_duration / float(reference) * 100 # this score represents how much slower this item is compared to the average time per visit for this site, so a score of 2 means this item is on average twice as slow as the average time per visit for this site 

					sorted_items = sorted(durations.items(), key=lambda item: compute_score(item[1], normalize), reverse=True)

					type_avgs = [
						sum(durations) / float(len(durations))
						for durations in durations.values()
					]

					slowest_elts: dict[type, float | int | dict[str, type]] = {
						"avg_duration": sum(type_avgs) / float(len(type_avgs)),
						"stddev_duration": stddev(type_avgs),
						"count": sum(len(durations) for durations in durations.values()),
						"stats": {}
					}

					for insn_idx, isn_durations in sorted_items:
						avg_duration = sum(isn_durations) / float(len(isn_durations))
						slowest_elts["stats"][insn_idx] = {
							"avg_duration": avg_duration,
							"count": len(isn_durations),
							"score": compute_score(isn_durations, normalize),
						}

					total_score = sum(item["score"] for item in slowest_elts["stats"].values())
					if abs(total_score - 100.0) > 1e-2:
						raise ValueError(
							f"Total score for site {key} is {total_score:.2f} which is not close enough to 100. This should be impossible since the score of each item is computed as a percentage of the reference value."
						)
					return slowest_elts

				# save top 10 slowest instructions for this site
				# stats["slowest_instructions"] = compute_stats(site.durations, site.inclusive_duration, False)

				# compute average duration per instruction type for this site
				durations_per_insn_type: dict[str, list[int]] = {}
				for insn_idx, durations in site.durations.items():
					insn_name = disasm_insn_name(self.profiling_result.program[insn_idx])
					if insn_name not in durations_per_insn_type:
						durations_per_insn_type[insn_name] = []
					durations_per_insn_type[insn_name].extend(durations)

				avg: dict[str, float] = {insn_name: sum(durations) / float(len(durations)) for insn_name, durations in durations_per_insn_type.items()}
				stats["nb_insn_types"] = len(durations_per_insn_type)
				stats["avg_duration_per_insn_type"] = sum(avg.values()) / float(stats["nb_insn_types"])
				stats["instruction_types"] = compute_stats(durations_per_insn_type, sum(avg.values()), True)

			stats["children"] = dict(
				sorted(
					[
						to_json_dict(child, site.inclusive_duration)
						for child in site.children
					],
					key=lambda item: item[1]["percent_of_total"],
					reverse=True,
				)
			)

			return [key, stats,]

		self.result.stats["site_tree"] = []
		for root in self.site_tree.roots:
			self.result.stats["site_tree"].append(to_json_dict(root, self.result.stats['verification_time']))
		self.result.stats["site_tree"] = dict(
			sorted(self.result.stats["site_tree"], key=lambda item: item[1]["percent_of_total"], reverse=True)
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
