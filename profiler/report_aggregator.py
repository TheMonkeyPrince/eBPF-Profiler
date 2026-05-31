"""Merge TraceAnalyser JSON reports by recursively combining site trees.

Each input report must match the JSON schema produced by ``TraceAnalyser``
(``profiler/trace_analyser.py``). Malformed or legacy reports raise
``KeyError``, ``TypeError``, or ``ValueError`` rather than being coerced.

Expected top-level report shape::

    {
        "program_name": str,
        "verification_stats": {
            "subprog_cnt": int,
            "insn_processed": int,
            "complexity_limit_insns": int,
            "max_states_per_insn": int,
            "total_states": int,
            "peak_states": int,
            "longest_mark_read_walk": int,
        },
        "stats": {
            "verification_time": int,
            "program_length": int,
            "num_records": int,
            "num_sites": int,
            "site_tree": {site_key: site_node, ...},
            "insn_types": {name: {"count": int, "percent": float}, ...},
            "insn_classes": {name: {"count": int, "percent": float}, ...},
        },
    }

Each ``site_node`` in ``site_tree`` must contain::

    {
        "percent_of_total": float,
        "percent_of_parent": float,
        "inclusive_duration": int,
        "exclusive_duration": int,
        "nb_visits": int,
        "avg_duration_per_visit": float,
        "children": {site_key: site_node, ...},
    }

Sites with per-instruction breakdown also include ``instruction_types`` and/or
``instruction_classes`` (each an instruction group as below), plus
``nb_insn_types`` / ``avg_duration_per_insn_type`` and/or
``nb_insn_classes`` / ``avg_duration_per_insn_class``.

Instruction group shape (``instruction_types``, ``instruction_classes``)::

    {
        "avg_avg_duration": float,
        "stddev_avg_duration": float,
        "count": int,
        "stats": {
            name: {"avg_duration": float, "count": int, "score": float},
            ...
        },
    }

Merge algorithm
----------------------
1. Normalize each report into internal ``_MergedSite`` nodes keyed by site path.
2. Recursively merge trees: union site keys, sum ``inclusive_duration`` and
   ``nb_visits``, combine instruction-type/class totals (weighted by count).
3. Recompute derived fields (percentages, exclusive time, instruction scores)
   against the summed ``verification_time``.
4. Sum additive ``verification_stats`` counters; take element-wise max for peaks.

The returned report adds ``aggregated: true``, ``source_programs``, and per-source
``unaggregated_insn_types`` / ``unaggregated_insn_classes`` lists preserving
each input report's instruction breakdown before merging. Saved reports belong
in ``out/aggregated/`` (not ``out/analysis/``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from utils import stddev

AGGREGATED_DIR = Path("out/aggregated")


@dataclass
class _MergedSite:
	inclusive_duration: int = 0
	nb_visits: int = 0
	instruction_type_totals: dict[str, tuple[float, int]] = field(default_factory=dict)
	instruction_class_totals: dict[str, tuple[float, int]] = field(default_factory=dict)
	children: dict[str, _MergedSite] = field(default_factory=dict)


def merge_reports(filenames: list[str]) -> dict:
	"""Load analysis JSON files and merge them into one aggregated report.

	Args:
		filenames: Paths to TraceAnalyser output JSON files.

	Returns:
		Merged report dict with ``aggregated`` set to ``True``.
	"""
	reports = []
	for filename in filenames:
		with open(filename, encoding="utf-8") as f:
			reports.append(json.load(f))
	return aggregate_reports(reports)


def save_aggregated_report(report: dict, name: str) -> Path:
	"""Write an aggregated report to ``out/aggregated/{name}.json``."""
	stem = name.removesuffix(".json")
	path = AGGREGATED_DIR / f"{stem}.json"
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(report, indent=2), encoding="utf-8")
	return path


def merge_reports_to_file(name: str, filenames: list[str]) -> Path:
	"""Merge analysis reports and save the result under ``out/aggregated/``."""
	return save_aggregated_report(merge_reports(filenames), name)


def aggregate_reports(reports: list[dict]) -> dict:
	"""Merge in-memory analysis report dicts into one aggregated report."""
	normalized = [_normalize_report(report) for report in reports]
	merged = _merge_normalized_reports(normalized)
	result = _finalize_report(merged, len(reports))
	result["aggregated"] = True
	result["source_programs"] = [report["program_name"] for report in reports]
	result["unaggregated_insn_types"] = [
		{"program_name": report["program_name"], "insn_types": report["insn_types"]}
		for report in normalized
	]
	result["unaggregated_insn_classes"] = [
		{"program_name": report["program_name"], "insn_classes": report["insn_classes"]}
		for report in normalized
	]
	return result


def _normalize_report(report: dict) -> dict:
	stats = report["stats"]
	return {
		"program_name": report["program_name"],
		"verification_stats": report["verification_stats"],
		"verification_time": stats["verification_time"],
		"program_length": stats["program_length"],
		"num_records": stats["num_records"],
		"site_tree": _normalize_site_tree(stats["site_tree"]),
		"insn_types": stats["insn_types"],
		"insn_classes": stats["insn_classes"],
	}


def _normalize_site_tree(tree: dict) -> dict[str, _MergedSite]:
	return {
		key: _normalize_site_node(raw)
		for key, raw in tree.items()
	}


def _normalize_site_node(raw: dict) -> _MergedSite:
	site = _MergedSite(
		inclusive_duration=raw["inclusive_duration"],
		nb_visits=raw["nb_visits"],
	)
	if "instruction_types" in raw:
		_merge_instruction_group_into(site.instruction_type_totals, raw["instruction_types"])
	if "instruction_classes" in raw:
		_merge_instruction_group_into(site.instruction_class_totals, raw["instruction_classes"])
	site.children = _normalize_site_tree(raw["children"])
	return site


def _merge_instruction_group_into(
	target: dict[str, tuple[float, int]],
	group: dict,
) -> None:
	for name, item in group["stats"].items():
		count = item["count"]
		avg_duration = item["avg_duration"]
		total_duration, existing_count = target.get(name, (0.0, 0))
		target[name] = (
			total_duration + avg_duration * count,
			existing_count + count,
		)


def _merge_normalized_reports(normalized: list[dict]) -> dict:
	return {
		"verification_time": sum(report["verification_time"] for report in normalized),
		"program_length": sum(report["program_length"] for report in normalized),
		"num_records": sum(report["num_records"] for report in normalized),
		"verification_stats": _merge_verification_stats(
			[report["verification_stats"] for report in normalized]
		),
		"site_tree": _merge_site_trees([report["site_tree"] for report in normalized]),
		"insn_types": _merge_count_stats([report["insn_types"] for report in normalized]),
		"insn_classes": _merge_count_stats([report["insn_classes"] for report in normalized]),
	}


def _merge_site_trees(trees: list[dict[str, _MergedSite]]) -> dict[str, _MergedSite]:
	keys: set[str] = set()
	for tree in trees:
		keys.update(tree.keys())

	return {
		key: _merge_site_nodes([tree[key] if key in tree else None for tree in trees])
		for key in keys
	}


def _merge_site_nodes(nodes: list[_MergedSite | None]) -> _MergedSite:
	present = [node for node in nodes if node is not None]
	merged = _MergedSite(
		inclusive_duration=sum(node.inclusive_duration for node in present),
		nb_visits=sum(node.nb_visits for node in present),
	)
	for node in present:
		_merge_duration_totals(merged.instruction_type_totals, node.instruction_type_totals)
		_merge_duration_totals(merged.instruction_class_totals, node.instruction_class_totals)
	merged.children = _merge_site_trees([node.children for node in present])
	return merged


def _merge_duration_totals(
	target: dict[str, tuple[float, int]],
	source: dict[str, tuple[float, int]],
) -> None:
	for name, (total_duration, count) in source.items():
		existing_total, existing_count = target.get(name, (0.0, 0))
		target[name] = (existing_total + total_duration, existing_count + count)


def _merge_verification_stats(stats_list: list[dict]) -> dict:
	sum_keys = ("subprog_cnt", "insn_processed", "total_states")
	max_keys = (
		"complexity_limit_insns",
		"max_states_per_insn",
		"peak_states",
		"longest_mark_read_walk",
	)
	return {
		**{key: sum(stats[key] for stats in stats_list) for key in sum_keys},
		**{key: max(stats[key] for stats in stats_list) for key in max_keys},
	}


def _merge_count_stats(stats_list: list[dict]) -> dict:
	merged_counts: dict[str, int] = {}
	for stats in stats_list:
		for name, item in stats.items():
			merged_counts[name] = merged_counts.get(name, 0) + item["count"]

	total_count = sum(merged_counts.values())
	return dict(
		sorted(
			{
				name: {
					"count": count,
					"percent": count / float(total_count) * 100,
				}
				for name, count in merged_counts.items()
			}.items(),
			key=lambda item: item[1]["percent"],
			reverse=True,
		)
	)


def _finalize_report(merged: dict, num_programs: int) -> dict:
	verification_time = merged["verification_time"]
	site_tree = _finalize_site_tree(
		merged["site_tree"],
		verification_time,
		verification_time,
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
	return {
		key: _finalize_site_node(site, total_verification_time, parent_duration)
		for key, site in sorted(
			tree.items(),
			key=lambda item: item[1].inclusive_duration,
			reverse=True,
		)
	}


def _finalize_site_node(
	site: _MergedSite,
	total_verification_time: float,
	parent_duration: float,
) -> dict:
	inclusive = site.inclusive_duration
	children = _finalize_site_tree(site.children, total_verification_time, inclusive)
	children_duration = sum(child["inclusive_duration"] for child in children.values())

	node: dict = {
		"percent_of_total": inclusive / float(total_verification_time) * 100,
		"percent_of_parent": inclusive / float(parent_duration) * 100,
		"inclusive_duration": inclusive,
		"exclusive_duration": inclusive - children_duration,
		"nb_visits": site.nb_visits,
		"avg_duration_per_visit": inclusive / float(site.nb_visits),
		"children": children,
	}

	if site.instruction_type_totals:
		group = _finalize_instruction_group(site.instruction_type_totals)
		node["nb_insn_types"] = len(site.instruction_type_totals)
		node["avg_duration_per_insn_type"] = group["avg_avg_duration"]
		node["instruction_types"] = group

	if site.instruction_class_totals:
		group = _finalize_instruction_group(site.instruction_class_totals)
		node["nb_insn_classes"] = len(site.instruction_class_totals)
		node["avg_duration_per_insn_class"] = group["avg_avg_duration"]
		node["instruction_classes"] = group

	return node


def _finalize_instruction_group(totals: dict[str, tuple[float, int]]) -> dict:
	avg_by_name = {
		name: total_duration / float(count)
		for name, (total_duration, count) in totals.items()
	}
	type_avgs = list(avg_by_name.values())
	reference = sum(type_avgs)

	def compute_score(name: str) -> float:
		total_duration, count = totals[name]
		agg_duration = total_duration / float(count)
		return agg_duration / float(reference) * 100

	sorted_names = sorted(avg_by_name.keys(), key=compute_score, reverse=True)
	return {
		"avg_avg_duration": sum(type_avgs) / float(len(type_avgs)),
		"stddev_avg_duration": stddev(type_avgs),
		"count": sum(count for _, count in totals.values()),
		"stats": {
			name: {
				"avg_duration": avg_by_name[name],
				"count": totals[name][1],
				"score": compute_score(name),
			}
			for name in sorted_names
		},
	}


def _count_sites(tree: dict) -> int:
	count = len(tree)
	for node in tree.values():
		count += _count_sites(node["children"])
	return count


if __name__ == "__main__":
	import sys

	if len(sys.argv) < 3:
		print(f"Usage: {sys.argv[0]} <name> <report.json> [...]")
		print(f"Writes to {AGGREGATED_DIR}/<name>.json")
		sys.exit(1)

	name = sys.argv[1]
	path = merge_reports_to_file(name, sys.argv[2:])
	print(f"Wrote aggregated report to {path}")
