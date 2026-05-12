"""End-to-end: parse the sample BASE/ and assert summary/stages/actions schema."""
from __future__ import annotations

import unittest
from pathlib import Path

from tests import _path  # noqa: F401
from tests._path import sample_bundle_dir
from nsight.analyze import actions as actions_builder
from nsight.analyze import stages as stages_builder
from nsight.analyze import summary as summary_builder


# REGIMES is opt-in; without it `attach_headline_metrics` becomes a no-op,
# which is the documented degraded mode when the file is absent.
class TestSummaryPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = sample_bundle_dir()
        cls.fake_trace = cls.bundle.parent / "fake.ngfx-gputrace"
        cls.fake_trace.write_bytes(b"")  # placeholder so trace_path.exists() works
        cls.basics = summary_builder.load_basics(cls.bundle)

    @classmethod
    def tearDownClass(cls):
        cls.fake_trace.unlink(missing_ok=True)

    def test_load_basics(self):
        self.assertEqual(self.basics["n_frames"], 40)
        self.assertGreater(len(self.basics["frame_metrics"]), 50)
        self.assertGreater(self.basics["events"]["marker_count"], 100)
        # 5 headline metric keys should all resolve from this sample.
        self.assertEqual(set(self.basics["headline_picks"]), {
            "sm_throughput", "sm_inst_executed", "warps_inactive",
            "l1_hit_rate", "l1_throughput",
        })

    def test_summary_schema(self):
        doc = summary_builder.build(self.fake_trace, self.basics)
        self.assertEqual(doc["schema_version"], 1)
        self.assertEqual(doc["summary"]["frame_count"], 40)
        self.assertGreater(doc["summary"]["metric_count"], 50)
        self.assertGreater(doc["summary"]["marker_count"], 100)
        # frame_budget verdict should be one of the documented values.
        self.assertIn(doc["analysis"]["frame_budget"]["verdict"],
                      {"60fps", "30fps", "below_30fps", "no_frames"})
        # hardware_context fields are populated from REPRO_INFO.xls.
        self.assertEqual(doc["hardware_context"]["chip"], "AD104")
        self.assertEqual(doc["hardware_context"]["api"], "Vulkan")
        self.assertIn("RTX", doc["hardware_context"]["gpu"])

    def test_stages_schema(self):
        doc = stages_builder.build(self.fake_trace, self.basics, self.bundle)
        self.assertEqual(doc["schema_version"], 1)
        self.assertTrue(doc["roots"], "expected at least one depth-0 root")
        self.assertTrue(doc["top_stages"], "expected depth-1 stages")
        # Render Camera dominates this sample.
        names = [s["name"] for s in doc["top_stages"]]
        self.assertIn("Render Camera", names)

    def test_actions_schema(self):
        doc = actions_builder.build(self.fake_trace, self.basics, self.bundle)
        self.assertEqual(doc["schema_version"], 1)
        self.assertTrue(doc["definition"].startswith("leaf-marker"))
        actions = doc["top_20_slowest_actions"]
        self.assertTrue(actions, "expected top leaf actions")
        for action in actions:
            self.assertGreaterEqual(action["depth"], 1)
            self.assertGreater(action["instance_count"], 0)
            self.assertGreaterEqual(action["total_duration_ns"], action["max_duration_ns"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
