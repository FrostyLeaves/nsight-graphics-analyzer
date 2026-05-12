"""gputrace-draws query: bucketing, verdict, end-to-end."""
from __future__ import annotations

import unittest

from tests import _path  # noqa: F401
from tests._path import sample_bundle_dir
from nsight.queries import draws as q


def _leaf(name: str, dur_ms: float, instances: int = 1) -> dict:
    return {
        "name": name,
        "total_duration_ms": dur_ms * instances,
        "instance_count": instances,
        "is_leaf": True,
    }


class TestBucketing(unittest.TestCase):
    def test_small_leaf_pct_threshold_strict(self):
        # 3 leaves: two at 0.001 ms (small), one at 0.5 ms (not small).
        # Threshold _SMALL_LEAF_MS = 0.005.
        leaves = [_leaf("a", 0.001), _leaf("b", 0.001), _leaf("c", 0.500)]
        s = q._bucket_leaves(leaves, n_frames=1)
        self.assertEqual(s["leaf_count_per_frame"], 3)
        self.assertEqual(s["small_leaf_count_per_frame"], 2)
        self.assertAlmostEqual(s["small_leaf_pct"], 2/3)

    def test_state_change_regex_catches_keywords(self):
        leaves = [_leaf("ClearRenderTarget", 0.020),
                  _leaf("ResolveMSAA", 0.040),
                  _leaf("Foo.Barrier.X", 0.010),
                  _leaf("DrawSomething", 0.100)]
        s = q._bucket_leaves(leaves, n_frames=1)
        self.assertEqual(s["state_change_count_per_frame"], 3)
        self.assertAlmostEqual(s["state_change_ms_per_frame"], 0.070)

    def test_top_names_aggregate_by_name(self):
        leaves = ([_leaf("A", 0.001)] * 5 + [_leaf("B", 0.001)] * 3 + [_leaf("C", 0.001)])
        s = q._bucket_leaves(leaves, n_frames=1)
        self.assertEqual(s["top_leaf_names"][0], {"name": "A", "count": 5})
        self.assertEqual(s["top_leaf_names"][1], {"name": "B", "count": 3})

    def test_n_frames_normalization(self):
        # 4 leaves each totalling 0.020 ms across 2 frames → 0.010 ms each / frame
        leaves = [_leaf("a", 0.020)] * 4
        s = q._bucket_leaves(leaves, n_frames=2)
        # leaf_total / 2 = 0.040 ms per frame
        self.assertAlmostEqual(s["leaf_total_ms_per_frame"], 0.040)


class TestVerdict(unittest.TestCase):
    def test_many_small_fires(self):
        leaves = [_leaf("x", 0.001)] * 7 + [_leaf("y", 0.1)] * 3
        s = q._bucket_leaves(leaves, n_frames=1)
        v = q._verdict(s, frame_ms=10.0)
        tags = {item["tag"]: item["severity"] for item in v}
        self.assertEqual(tags["many_small_leaves"], "high")

    def test_state_change_heavy(self):
        leaves = [_leaf("Clear", 2.0), _leaf("Resolve", 2.0), _leaf("Draw", 6.0)]
        s = q._bucket_leaves(leaves, n_frames=1)
        v = q._verdict(s, frame_ms=10.0)
        tags = {item["tag"]: item["severity"] for item in v}
        # 4 ms state / 10 ms frame = 40% → high
        self.assertEqual(tags["state_change_heavy"], "high")

    def test_state_change_not_visible_when_zero_matches(self):
        leaves = [_leaf("CustomEngineMarker", 1.0)] * 3
        s = q._bucket_leaves(leaves, n_frames=1)
        v = q._verdict(s, frame_ms=10.0)
        tags = [item["tag"] for item in v]
        self.assertIn("state_change_not_visible", tags)


class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = sample_bundle_dir()
        cls.fake_trace = cls.bundle.parent / "fake.ngfx-gputrace"
        cls.fake_trace.write_bytes(b"")

    @classmethod
    def tearDownClass(cls):
        cls.fake_trace.unlink(missing_ok=True)

    def test_full_run_against_sample(self):
        r = q.query(self.fake_trace)
        self.assertEqual(r["schema_version"], 1)
        self.assertGreater(r["signals"]["leaf_count_per_frame"], 0)
        self.assertTrue(r["verdict"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
