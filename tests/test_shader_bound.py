"""gputrace-shader-bound query: resolve / signals / verdict / end-to-end."""
from __future__ import annotations

import unittest

from tests import _path  # noqa: F401
from tests._path import sample_bundle_dir
from nsight.queries import shader_bound as q


class TestResolveAndSignals(unittest.TestCase):
    def test_resolves_all_eight(self):
        names = [
            "GPUTrace.sm__throughput.avg.pct_of_peak_sustained_elapsed",
            "FE_B.TriageSCG.gr__cycles_active.avg.pct_of_peak_sustained_elapsed",
            "FE_A.TriageSCG.gr__compute_cycles_active_queue_sync.avg.pct_of_peak_sustained_elapsed",
            "FE_A.TriageSCG.gr__compute_cycles_active_queue_async.avg.pct_of_peak_sustained_elapsed",
            "TPC.TriageSCG.tpc__warps_active_shader_ps_realtime.avg.pct_of_peak_sustained_elapsed",
            "SM_B.TriageSCG.tpc__warps_active_shader_vtg_realtime.avg.pct_of_peak_sustained_elapsed",
            "TPC.TriageSCG.tpc__warps_active_shader_cs_realtime.avg.pct_of_peak_sustained_elapsed",
            "TriageSCG.tpc__warps_inactive_sm_active_realtime.avg.pct_of_peak_sustained_elapsed",
        ]
        resolved, missing = q._resolve_concepts(names)
        self.assertEqual(missing, [])
        for key in q._CONCEPT_PATTERNS:
            self.assertIn(key, resolved)

    def test_signals_ps_dominant(self):
        s = q._compute_signals({
            "sm_throughput": 50.0, "gr_cycles_active": 95.0,
            "compute_sync": 30.0, "compute_async": 0.5,
            "ps_warps_active": 35.0, "vtg_warps_active": 5.0, "cs_warps_active": 10.0,
            "warps_inactive_sm_active": 20.0,
        })
        self.assertEqual(s["dominant_shader_stage"], "ps")
        self.assertAlmostEqual(s["sm_stall_ratio"], 0.4)
        self.assertAlmostEqual(s["compute_dominance"], 30.5 / 95.0)
        self.assertAlmostEqual(s["async_efficiency"], 0.5 / 30.5)


class TestVerdict(unittest.TestCase):
    def test_stall_high_fires_high_severity(self):
        s = q._compute_signals({
            "sm_throughput": 60.0, "gr_cycles_active": 90.0,
            "compute_sync": 20.0, "compute_async": 10.0,
            "ps_warps_active": 40.0, "vtg_warps_active": 5.0, "cs_warps_active": 5.0,
            "warps_inactive_sm_active": 35.0,   # stall_ratio = 35/60 = 0.58
        })
        v = q._verdict("global", s)
        tags = {item["tag"]: item["severity"] for item in v}
        self.assertEqual(tags["sm_stalls"], "high")

    def test_async_underused_fires(self):
        s = q._compute_signals({
            "sm_throughput": 50.0, "gr_cycles_active": 95.0,
            "compute_sync": 35.0, "compute_async": 0.5,
            "ps_warps_active": 30.0, "vtg_warps_active": 5.0, "cs_warps_active": 10.0,
            "warps_inactive_sm_active": 10.0,
        })
        v = q._verdict("global", s)
        tags = [item["tag"] for item in v]
        self.assertIn("async_underused", tags)

    def test_data_missing_when_no_metrics(self):
        s = q._compute_signals({})
        v = q._verdict("global", s)
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

    def test_global_query_returns_shape(self):
        r = q.query(self.fake_trace, in_marker_re=None)
        self.assertEqual(r["schema_version"], 1)
        self.assertIn("dominant_shader_stage", r["global_signals"])
        self.assertTrue(r["verdict"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
