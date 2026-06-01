"""Merge analysis reports by recursively combining site trees"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from utils import stddev


@dataclass
class _MergedSite:
	inclusive_duration: int = 0
	nb_visits: int = 0
	instruction_type_totals: dict[str, tuple[float, int]] = field(default_factory=dict)
	instruction_class_totals: dict[str, tuple[float, int]] = field(default_factory=dict)
	children: dict[str, _MergedSite] = field(default_factory=dict)


def aggregate_reports(reports: list[dict]) -> dict:
	"""Merge a list of analysis report dicts into one aggregated report."""
	if not reports:
		raise ValueError("aggregate_reports requires at least one report")

	normalized = [_normalize_report(report) for report in reports]
	merged = _merge_normalized_reports(normalized)
	result = _finalize_report(merged, len(reports))
	result["aggregated"] = True
	result["source_programs"] = [
		report.get("program_name", "unknown") for report in reports
	]
	return result


def _normalize_report(report: dict) -> dict:
	stats = report.get("stats", {})
	verification_time = stats.get("verification_time", 0)
	return {
		"program_name": report.get("program_name", "unknown"),
		"verification_stats": dict(report.get("verification_stats", {})),
		"verification_time": verification_time,
		"program_length": stats.get("program_length", 0),
		"num_records": stats.get("num_records", 0),
		"site_tree": _normalize_site_tree(
			stats.get("site_tree", {}),
			verification_time,
			verification_time,
		),
		"insn_types": stats.get("insn_types", {}),
		"insn_classes": stats.get("insn_classes", {}),
	}


def _normalize_site_tree(
	tree: dict,
	verification_time: float,
	parent_duration: float,
) -> dict[str, _MergedSite]:
	if not tree:
		return {}

	normalized: dict[str, _MergedSite] = {}
	for key, raw in tree.items():
		normalized[key] = _normalize_site_node(
			raw,
			verification_time,
			parent_duration,
		)
	return normalized


def _normalize_site_node(
	raw,
	verification_time: float,
	parent_duration: float,
) -> _MergedSite:
	if isinstance(raw, list) and len(raw) == 3:
		pct_total, _pct_parent, children_raw = raw
		inclusive = int(pct_total * verification_time / 100.0)
		site = _MergedSite(inclusive_duration=inclusive, nb_visits=0)
		site.children = _normalize_site_tree(
			children_raw or {},
			verification_time,
			float(inclusive) if inclusive > 0 else parent_duration,
		)
		return site

	if not isinstance(raw, dict):
		raise ValueError(f"Unsupported site tree node type: {type(raw)!r}")

	if "percent_of_total" in raw and "inclusive_duration" not in raw:
		inclusive = int(raw["percent_of_total"] * verification_time / 100.0)
	else:
		inclusive = int(raw.get("inclusive_duration", 0))

	site = _MergedSite(
		inclusive_duration=inclusive,
		nb_visits=int(raw.get("nb_visits", 0)),
	)
	_merge_instruction_group_into(
		site.instruction_type_totals,
		raw.get("instruction_types"),
	)
	_merge_instruction_group_into(
		site.instruction_class_totals,
		raw.get("instruction_classes"),
	)

	children_raw = raw.get("children", {})
	if isinstance(children_raw, list):
		children_raw = dict(children_raw)

	site.children = _normalize_site_tree(
		children_raw,
		verification_time,
		float(inclusive) if inclusive > 0 else parent_duration,
	)
	return site


def _merge_instruction_group_into(
	target: dict[str, tuple[float, int]],
	group: dict | None,
) -> None:
	if not group:
		return
	for name, item in group.get("stats", {}).items():
		count = int(item.get("count", 0))
		avg_duration = float(item.get("avg_duration", 0))
		total_duration, existing_count = target.get(name, (0.0, 0))
		target[name] = (
			total_duration + avg_duration * count,
			existing_count + count,
		)


def _merge_normalized_reports(normalized: list[dict]) -> dict:
	merged_tree = _merge_site_trees([report["site_tree"] for report in normalized])
	return {
		"verification_time": sum(report["verification_time"] for report in normalized),
		"program_length": sum(report["program_length"] for report in normalized),
		"num_records": sum(report["num_records"] for report in normalized),
		"verification_stats": _merge_verification_stats(
			[report["verification_stats"] for report in normalized]
		),
		"site_tree": merged_tree,
		"insn_types": _merge_count_stats([report["insn_types"] for report in normalized]),
		"insn_classes": _merge_count_stats(
			[report["insn_classes"] for report in normalized]
		),
	}


def _merge_site_trees(trees: list[dict[str, _MergedSite]]) -> dict[str, _MergedSite]:
	keys: set[str] = set()
	for tree in trees:
		keys.update(tree.keys())

	merged: dict[str, _MergedSite] = {}
	for key in keys:
		nodes = [tree.get(key) for tree in trees]
		merged[key] = _merge_site_nodes(nodes)
	return merged


def _merge_site_nodes(nodes: list[_MergedSite | None]) -> _MergedSite:
	present = [node for node in nodes if node is not None]
	if not present:
		return _MergedSite()

	merged = _MergedSite(
		inclusive_duration=sum(node.inclusive_duration for node in present),
		nb_visits=sum(node.nb_visits for node in present),
	)
	for node in present:
		_merge_duration_totals(merged.instruction_type_totals, node.instruction_type_totals)
		_merge_duration_totals(merged.instruction_class_totals, node.instruction_class_totals)

	child_trees = [node.children for node in present]
	merged.children = _merge_site_trees(child_trees)
	return merged


def _merge_duration_totals(
	target: dict[str, tuple[float, int]],
	source: dict[str, tuple[float, int]],
) -> None:
	for name, (total_duration, count) in source.items():
		existing_total, existing_count = target.get(name, (0.0, 0))
		target[name] = (existing_total + total_duration, existing_count + count)


def _merge_verification_stats(stats_list: list[dict]) -> dict:
	if not stats_list:
		return {}

	merged: dict = {}
	sum_keys = {
		"subprog_cnt",
		"insn_processed",
		"total_states",
	}
	max_keys = {
		"complexity_limit_insns",
		"max_states_per_insn",
		"peak_states",
		"longest_mark_read_walk",
	}

	for key in sum_keys:
		merged[key] = sum(stats.get(key, 0) for stats in stats_list)
	for key in max_keys:
		merged[key] = max(stats.get(key, 0) for stats in stats_list)

	return merged


def _merge_count_stats(stats_list: list[dict]) -> dict:
	merged_counts: dict[str, int] = {}
	for stats in stats_list:
		for name, item in stats.items():
			merged_counts[name] = merged_counts.get(name, 0) + int(item.get("count", 0))

	total_count = sum(merged_counts.values())
	result: dict[str, dict[str, float | int]] = {}
	for name, count in merged_counts.items():
		result[name] = {
			"count": count,
			"percent": count / float(total_count) * 100 if total_count else 0.0,
		}
	return dict(sorted(result.items(), key=lambda item: item[1]["percent"], reverse=True))


def _finalize_report(merged: dict, num_programs: int) -> dict:
	verification_time = merged["verification_time"]
	site_tree = _finalize_site_tree(
		merged["site_tree"],
		verification_time,
		float(verification_time),
	)

	return {
		"program_name": f"aggregated ({num_programs} programs)",
		"verification_stats": merged["verification_stats"],
		"stats": {
			"verification_time": verification_time,
			"program_length": merged["program_length"],
			"num_records": merged["num_records"],
			"num_sites": _count_sites(site_tree),
			"site_tree": site_tree,
			"insn_types": merged["insn_types"],
			"insn_classes": merged["insn_classes"],
		},
	}


def _finalize_site_tree(
	tree: dict[str, _MergedSite],
	total_verification_time: float,
	parent_duration: float,
) -> dict:
	result: dict[str, dict] = {}
	for key, site in sorted(
		tree.items(),
		key=lambda item: item[1].inclusive_duration,
		reverse=True,
	):
		result[key] = _finalize_site_node(
			site,
			total_verification_time,
			parent_duration,
		)
	return result


def _finalize_site_node(
	site: _MergedSite,
	total_verification_time: float,
	parent_duration: float,
) -> dict:
	inclusive = site.inclusive_duration
	children = _finalize_site_tree(
		site.children,
		total_verification_time,
		float(inclusive) if inclusive > 0 else parent_duration,
	)
	children_duration = sum(
		child["inclusive_duration"] for child in children.values()
	)

	node: dict = {
		"percent_of_total": inclusive / float(total_verification_time) * 100
		if total_verification_time
		else 0.0,
		"percent_of_parent": inclusive / float(parent_duration) * 100
		if parent_duration
		else 0.0,
		"inclusive_duration": inclusive,
		"exclusive_duration": inclusive - children_duration,
		"nb_visits": site.nb_visits,
		"avg_duration_per_visit": inclusive / float(site.nb_visits)
		if site.nb_visits
		else 0.0,
		"children": children,
	}

	if site.instruction_type_totals:
		group = _finalize_instruction_group(site.instruction_type_totals, normalize=True)
		node["nb_insn_types"] = len(site.instruction_type_totals)
		node["avg_duration_per_insn_type"] = group["avg_avg_duration"]
		node["instruction_types"] = group

	if site.instruction_class_totals:
		group = _finalize_instruction_group(site.instruction_class_totals, normalize=True)
		node["nb_insn_classes"] = len(site.instruction_class_totals)
		node["avg_duration_per_insn_class"] = group["avg_avg_duration"]
		node["instruction_classes"] = group

	return node


def _finalize_instruction_group(
	totals: dict[str, tuple[float, int]],
	normalize: bool,
) -> dict:
	avg_by_name = {
		name: total_duration / float(count)
		for name, (total_duration, count) in totals.items()
		if count > 0
	}
	type_avgs = list(avg_by_name.values())
	reference = sum(type_avgs)

	def compute_score(name: str) -> float:
		total_duration, count = totals[name]
		if normalize:
			agg_duration = total_duration / float(count)
		else:
			agg_duration = total_duration
		return agg_duration / float(reference) * 100 if reference else 0.0

	sorted_names = sorted(avg_by_name.keys(), key=compute_score, reverse=True)
	stats = {
		name: {
			"avg_duration": avg_by_name[name],
			"count": totals[name][1],
			"score": compute_score(name),
		}
		for name in sorted_names
	}

	return {
		"avg_avg_duration": sum(type_avgs) / float(len(type_avgs)) if type_avgs else 0.0,
		"stddev_avg_duration": stddev(type_avgs),
		"count": sum(count for _, count in totals.values()),
		"stats": stats,
	}


def _count_sites(tree: dict) -> int:
	count = len(tree)
	for node in tree.values():
		count += _count_sites(node.get("children", {}))
	return count


def load_report(path: str | Path) -> dict:
	with open(path, encoding="utf-8") as f:
		return json.load(f)


if __name__ == "__main__":
	import sys

	if len(sys.argv) < 3:
		print(f"Usage: {sys.argv[0]} <output.json> <report.json> [...]")
		sys.exit(1)

	output_path = Path(sys.argv[1])
	report_paths = [Path(path) for path in sys.argv[2:]]
	reports = [load_report(path) for path in report_paths]
	aggregated = aggregate_reports(reports)
	aggregated["program_name"] = (
		f"aggregated ({len(reports)} programs)"
	)
	output_path.write_text(json.dumps(aggregated, indent=2), encoding="utf-8")
	print(f"Wrote aggregated report to {output_path}")
