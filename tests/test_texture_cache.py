"""gputrace-texture-cache query: signals, verdict, end-to-end."""
from __future__ import annotations

import unittest

from tests import _path  # noqa: F401
from tests._path import sample_bundle_dir
from nsight.queries import texture_cache as q


class TestSignals(unittest.TestCase):
    def test_miss_to_dram_math(self):
        s = q._compute_signals({"l1_hit_rate": 80.0, "l2_hit_rate": 50.0,
                                "l1tex_throughput": 30.0, "dram_pct": 40.0})
        # P(L1 miss) = 0.2, P(L2 miss | L1 miss) = 0.5, so 0.1 of all → DRAM
        self.assertAlmostEqual(s["miss_to_dram"], 0.1)

    def test_no_data(self):
        s = q._compute_signals({})
        self.assertIsNone(s["miss_to_dram"])


class TestVerdict(unittest.TestCase):
    def test_thrashing_high(self):
        s = q._compute_signals({"l1_hit_rate": 50.0, "l2_hit_rate": 30.0,
                                "l1tex_throughput": 75.0, "dram_pct": 50.0})
        v = q._verdict("global", s)
        tags = {item["tag"]: item["severity"] for item in v}
        self.assertEqual(tags["l1_hit_low"], "high")
        self.assertIn("miss_to_dram_high", tags)

    def test_healthy(self):
        s = q._compute_signals({"l1_hit_rate": 92.0, "l2_hit_rate": 95.0,
                                "l1tex_throughput": 20.0, "dram_pct": 15.0})
        v = q._verdict("global", s)
        tags = [item["tag"] for item in v]
        self.assertIn("l1_hit_healthy", tags)
        self.assertNotIn("miss_to_dram_high", tags)

    def test_data_missing(self):
        v = q._verdict("global", q._compute_signals({}))
        self.assertEqual(v[0]["tag"], "data_missing")


class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = sample_bundle_dir()
        cls.fake_trace = cls.bundle.parent / "fake.ngfx-gputrace"
        cls.fake_trace.write_bytes(b"")

    @classmethod
    def tearDownClass(cls):
        cls.fake_trace.unlink(missing_ok=True)

    def test_global_shape(self):
        r = q.query(self.fake_trace, in_marker_re=None)
        self.assertEqual(r["schema_version"], 1)
        self.assertIn("l1_hit_rate", r["global_signals"])
        self.assertTrue(r["verdict"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
