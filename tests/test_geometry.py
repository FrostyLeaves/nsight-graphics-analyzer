"""gputrace-geometry query: resolve / signals / verdict / end-to-end."""
from __future__ import annotations

import unittest

from tests import _path  # noqa: F401
from tests._path import sample_bundle_dir
from nsight.queries import geometry as q


class TestResolveAndSignals(unittest.TestCase):
    def test_resolves_all(self):
        names = [
            "TPC.TriageSCG.vaf__throughput.avg.pct_of_peak_sustained_elapsed",
            "HUB_B.TriageSCG.pda__throughput.avg.pct_of_peak_sustained_elapsed",
            "GPC_A.TriageSCG.raster__throughput.avg.pct_of_peak_sustained_elapsed",
            "HUB_B.TriageSCG.pda__input_prims_realtime.sum",
            "GPC_A.TriageSCG.prop__input_pixels_type_3d_realtime.sum",
            "GPC_A.TriageSCG.raster__zcull_input_samples_realtime.sum",
        ]
        resolved, missing = q._resolve_concepts(names)
        self.assertEqual(missing, [])

    def test_pixels_per_prim_signal(self):
        s = q._compute_signals({
            "vaf_pct": 10.0, "pda_pct": 5.0, "raster_pct": 8.0,
            "prims_input": 1_000_000, "pixels_input": 10_000_000,
            "samples_to_zcull": 40_000_000,
        })
        self.assertAlmostEqual(s["pixels_per_prim"], 10.0)
        self.assertAlmostEqual(s["samples_per_pixel"], 4.0)


class TestVerdict(unittest.TestCase):
    def test_micro_triangles_high(self):
        s = q._compute_signals({"prims_input": 100_000_000, "pixels_input": 200_000_000})
        # 2 pixels/prim → micro
        v = q._verdict("global", s)
        tags = {item["tag"]: item["severity"] for item in v}
        self.assertEqual(tags["micro_triangles"], "high")

    def test_healthy_triangles(self):
        s = q._compute_signals({"prims_input": 1_000_000, "pixels_input": 100_000_000})
        v = q._verdict("global", s)
        tags = [item["tag"] for item in v]
        self.assertIn("triangle_size_healthy", tags)

    def test_vaf_pressure_fires(self):
        s = q._compute_signals({
            "vaf_pct": 85.0, "pda_pct": 30.0, "raster_pct": 30.0,
            "prims_input": 1_000_000, "pixels_input": 50_000_000,
        })
        v = q._verdict("global", s)
        tags = {item["tag"]: item["severity"] for item in v}
        self.assertEqual(tags["vaf_pressure"], "high")


class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = sample_bundle_dir()
        cls.fake_trace = cls.bundle.parent / "fake.ngfx-gputrace"
        cls.fake_trace.write_bytes(b"")

    @classmethod
    def tearDownClass(cls):
        cls.fake_trace.unlink(missing_ok=True)

    def test_global_query_shape(self):
        r = q.query(self.fake_trace, in_marker_re=None)
        self.assertEqual(r["schema_version"], 1)
        self.assertIn("pixels_per_prim", r["global_signals"])
        self.assertTrue(r["verdict"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
