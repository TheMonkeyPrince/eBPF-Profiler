"""Tests for visualiser report ingestion and catalog helpers."""

import json
import tempfile
import unittest
from pathlib import Path

from server import (
    _finalize_sample_agg,
    _new_sample_agg,
    _peek_verification_ns,
    ingest_report,
    prune_compact_call_tree_for_file_arg,
    reports_catalog,
)


class TestCatalogPeek(unittest.TestCase):
    def test_peek_verification_ns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "big.json"
            path.write_text(
                '{"program_name":"p","verification_ns":424242,'
                '"file_ids":{"1":"a.c"},"call_tree":[]}',
                encoding="utf-8",
            )
            self.assertEqual(_peek_verification_ns(path), 424242)

    def test_reports_catalog_without_full_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.json").write_text(
                json.dumps(
                    {
                        "program_name": "one",
                        "verification_ns": 100,
                        "file_ids": {"1": "net/core.c"},
                        "call_tree": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "two.json").write_text(
                json.dumps(
                    {
                        "program_name": "two",
                        "verification_ns": 200,
                        "file_ids": {"1": "net/core.c"},
                        "call_tree": [],
                    }
                ),
                encoding="utf-8",
            )
            catalog = reports_catalog(root)
            by_id = {e["id"]: e["total_duration_ns"] for e in catalog}
            self.assertEqual(by_id["one"], 100)
            self.assertEqual(by_id["two"], 200)


class TestIngestAggregation(unittest.TestCase):
    def test_ingest_aggregates_samples(self):
        report = {
            "program_name": "test",
            "verification_ns": 1000,
            "file_ids": {"1": "net/core.c"},
            "call_tree": [
                {
                    "f": "1:10:12",
                    "i": 100,
                    "e": 40,
                    "a": 3,
                },
                {
                    "f": "1:10:12",
                    "i": 200,
                    "e": 80,
                    "a": 3,
                },
            ],
        }
        indexed, compact, file_ids = ingest_report(report)
        self.assertEqual(len(compact), 2)
        ranges = indexed["files"]["net/core.c"]["ranges"]
        self.assertEqual(len(ranges), 1)
        block = ranges[0]["by_arg"]["3"]
        self.assertEqual(block["count"], 2)
        self.assertEqual(block["total_ns"], 300)
        self.assertEqual(block["min_ns"], 100)
        self.assertEqual(block["max_ns"], 200)
        self.assertEqual(len(block["preview"]), 2)

    def test_prune_compact_tree(self):
        report = {
            "verification_ns": 1,
            "file_ids": {"1": "a.c", "2": "b.c"},
            "call_tree": [
                {
                    "f": "1:1:2",
                    "i": 10,
                    "e": 10,
                    "c": [{"f": "2:3:4", "i": 5, "e": 5}],
                }
            ],
        }
        _, compact, file_ids = ingest_report(report)
        pruned = prune_compact_call_tree_for_file_arg(compact, file_ids, "a.c", "all")
        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0]["f"], "1:1:2")


class TestSampleAgg(unittest.TestCase):
    def test_finalize_empty(self):
        self.assertIsNone(_finalize_sample_agg(_new_sample_agg()))


if __name__ == "__main__":
    unittest.main()
