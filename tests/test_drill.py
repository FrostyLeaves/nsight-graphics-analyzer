"""drill subcommand queries (stages / actions / metric) on the sample bundle."""
from __future__ import annotations

import re
import unittest

from tests import _path  # noqa: F401
from tests._path import sample_bundle_dir
from nsight.queries import actions as actions_query
from nsight.queries import stages as stages_query
from nsight.queries import metric as metric_query


class TestDrillStages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = sample_bundle_dir()
        cls.fake_trace = cls.bundle.parent / "fake.ngfx-gputrace"
        cls.fake_trace.write_bytes(b"")

    @classmethod
    def tearDownClass(cls):
        cls.fake_trace.unlink(missing_ok=True)

    def test_depth_default(self):
        result = stages_query.query_depth(self.fake_trace, depth=1, top_n=10)
        self.assertEqual(result["scope"], "depth_1")
        self.assertTrue(result["stages"])
        self.assertTrue(any(s["name"] == "Render Camera" for s in result["stages"]))

    def test_parent_regex(self):
        pattern = re.compile("Render Camera", re.IGNORECASE)
        result = stages_query.query_parent(
            self.fake_trace, pattern, depth=None, top_n=10,
        )
        # Render Camera fires twice per frame in this sample (40 frames -> 80 instances)
        # but at the marker level there are 2 rows representing the two Render Camera
        # invocations per frame. parent_instances reports those marker rows.
        self.assertTrue(result["parent_instances"])
        self.assertTrue(result["stages"])
        for s in result["stages"]:
            self.assertGreater(s["total_duration_ns"], 0)


class TestDrillActions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = sample_bundle_dir()
        cls.fake_trace = cls.bundle.parent / "fake.ngfx-gputrace"
        cls.fake_trace.write_bytes(b"")

    @classmethod
    def tearDownClass(cls):
        cls.fake_trace.unlink(missing_ok=True)

    def test_top_n_no_filter(self):
        result = actions_query.query(
            self.fake_trace, name_re=None, in_marker_re=None,
            sort_by="duration", top_n=5, with_metrics=False,
        )
        self.assertEqual(result["count"], 5)
        self.assertGreaterEqual(
            result["actions"][0]["total_duration_ns"],
            result["actions"][-1]["total_duration_ns"],
        )

    def test_in_marker_filter(self):
        in_marker_re = re.compile("Gbuffer", re.IGNORECASE)
        result = actions_query.query(
            self.fake_trace, name_re=None, in_marker_re=in_marker_re,
            sort_by="duration", top_n=10, with_metrics=False,
        )
        self.assertGreater(result["count"], 0)
        for action in result["actions"]:
            self.assertIn("Gbuffer", action["path"])


class TestDrillMetric(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = sample_bundle_dir()
        cls.fake_trace = cls.bundle.parent / "fake.ngfx-gputrace"
        cls.fake_trace.write_bytes(b"")

    @classmethod
    def tearDownClass(cls):
        cls.fake_trace.unlink(missing_ok=True)

    def test_global_only(self):
        pattern = re.compile("GPUTrace.sm__throughput.avg.pct_of_peak_sustained_elapsed",
                             re.IGNORECASE)
        result = metric_query.query(
            self.fake_trace, name_pattern=pattern,
            in_marker_re=None, all_matches=False,
        )
        # Single result block.
        self.assertIsInstance(result, dict)
        self.assertEqual(result["sample_count"], 40)
        self.assertGreater(result["global"]["avg"], 0.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
