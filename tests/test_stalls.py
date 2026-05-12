"""gputrace-stalls query: signals, verdict, end-to-end."""
from __future__ import annotations

import unittest

from tests import _path  # noqa: F401
from tests._path import sample_bundle_dir
from nsight.queries import stalls as q


class TestVerdict(unittest.TestCase):
    def test_gpu_well_fed(self):
        signals = {
            "gr_cycles_active": 95.0, "gr_idle_pct": 5.0,
            "gpu_syncce_active": 3.0, "frame_total_ms": 16.0, "depth1_total_ms": 15.4,
            "unaccounted_ms": 0.6, "marker_coverage_pct": 96.0, "depth1_marker_count": 8,
        }
        v = q._verdict(signals)
        tags = [item["tag"] for item in v]
        self.assertIn("gpu_busy", tags)

    def test_gpu_idle_within_markers(self):
        signals = {
            "gr_cycles_active": 50.0, "gr_idle_pct": 50.0,
            "gpu_syncce_active": 5.0, "frame_total_ms": 33.0, "depth1_total_ms": 31.5,
            "unaccounted_ms": 1.5, "marker_coverage_pct": 95.0, "depth1_marker_count": 8,
        }
        v = q._verdict(signals)
        tags = {item["tag"]: item["severity"] for item in v}
        self.assertEqual(tags["gpu_idle"], "high")
        # message mentions "WITHIN markers"
        self.assertTrue(any("WITHIN" in item["message"] for item in v))

    def test_gpu_idle_between_markers(self):
        signals = {
            "gr_cycles_active": 50.0, "gr_idle_pct": 50.0,
            "gpu_syncce_active": 5.0, "frame_total_ms": 33.0, "depth1_total_ms": 20.0,
            "unaccounted_ms": 13.0, "marker_coverage_pct": 60.0, "depth1_marker_count": 8,
        }
        v = q._verdict(signals)
        self.assertTrue(any("BETWEEN" in item["message"] for item in v))

    def test_dma_pressure(self):
        signals = {
            "gr_cycles_active": 90.0, "gr_idle_pct": 10.0,
            "gpu_syncce_active": 45.0, "frame_total_ms": 16.0, "depth1_total_ms": 15.0,
            "unaccounted_ms": 1.0, "marker_coverage_pct": 93.0, "depth1_marker_count": 8,
        }
        v = q._verdict(signals)
        tags = {item["tag"]: item["severity"] for item in v}
        self.assertEqual(tags["dma_pressure"], "high")


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
        r = q.query(self.fake_trace)
        self.assertEqual(r["schema_version"], 1)
        self.assertIn("marker_coverage_pct", r["signals"])
        self.assertTrue(r["verdict"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
