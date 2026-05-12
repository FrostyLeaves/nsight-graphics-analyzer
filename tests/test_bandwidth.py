"""gputrace-bandwidth query: concept resolution, signals, verdict, end-to-end."""
from __future__ import annotations

import unittest

from tests import _path  # noqa: F401
from tests._path import sample_bundle_dir
from nsight.queries import bandwidth as bandwidth_query


class TestResolveConcepts(unittest.TestCase):
    def test_all_five_tiers_resolve(self):
        names = [
            "FBSP.TriageSCG.dramc__throughput.avg.pct_of_peak_sustained_elapsed",
            "LTS.TriageSCG.lts__throughput.avg.pct_of_peak_sustained_elapsed",
            "SM_A.TriageSCG.l1tex__throughput.avg.pct_of_peak_sustained_elapsed",
            "PCI.TriageSCG.pcie__throughput.avg.pct_of_peak_sustained_elapsed",
            "GPUTrace.sm__throughput.avg.pct_of_peak_sustained_elapsed",
        ]
        resolved, missing = bandwidth_query._resolve_concepts(names)
        self.assertEqual(missing, [])
        for key in ("dram_pct", "l2_pct", "l1tex_pct", "pcie_pct", "sm_pct"):
            self.assertIn(key, resolved)


class TestSignals(unittest.TestCase):
    def test_memory_bound_signal(self):
        sigs = bandwidth_query._compute_signals({
            "dram_pct": 85.0, "l2_pct": 30.0, "l1tex_pct": 25.0,
            "pcie_pct": 5.0, "sm_pct": 40.0,
        })
        self.assertEqual(sigs["dominant_tier"], "dram_pct")
        self.assertAlmostEqual(sigs["memory_vs_compute"], 45.0)

    def test_compute_bound_signal(self):
        sigs = bandwidth_query._compute_signals({
            "dram_pct": 20.0, "l2_pct": 25.0, "l1tex_pct": 30.0,
            "pcie_pct": 5.0, "sm_pct": 90.0,
        })
        self.assertEqual(sigs["dominant_tier"], "l1tex_pct")
        self.assertAlmostEqual(sigs["memory_vs_compute"], -60.0)

    def test_partial_resolution_still_works(self):
        sigs = bandwidth_query._compute_signals({
            "dram_pct": 70.0, "l2_pct": None, "l1tex_pct": None,
            "pcie_pct": None, "sm_pct": None,
        })
        self.assertEqual(sigs["dominant_tier"], "dram_pct")
        self.assertIsNone(sigs["memory_vs_compute"])  # SM missing → can't compare


class TestVerdict(unittest.TestCase):
    def test_saturated_dram_emits_high(self):
        values = {"dram_pct": 85.0, "l2_pct": 30.0, "l1tex_pct": 20.0,
                  "pcie_pct": 5.0, "sm_pct": 40.0}
        sigs = bandwidth_query._compute_signals(values)
        v = bandwidth_query._verdict("global", values, sigs)
        tags = {item["tag"]: item["severity"] for item in v}
        self.assertEqual(tags["dram_saturated"], "high")

    def test_pcie_alert_at_30(self):
        values = {"dram_pct": 20.0, "l2_pct": 20.0, "l1tex_pct": 20.0,
                  "pcie_pct": 35.0, "sm_pct": 30.0}
        sigs = bandwidth_query._compute_signals(values)
        v = bandwidth_query._verdict("global", values, sigs)
        tags = [item["tag"] for item in v]
        self.assertIn("pcie_pressure", tags)


class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = sample_bundle_dir()
        cls.fake_trace = cls.bundle.parent / "fake.ngfx-gputrace"
        cls.fake_trace.write_bytes(b"")

    @classmethod
    def tearDownClass(cls):
        cls.fake_trace.unlink(missing_ok=True)

    def test_global_query_returns_full_structure(self):
        result = bandwidth_query.query(self.fake_trace, in_marker_re=None)
        self.assertEqual(result["schema_version"], 1)
        self.assertIsNone(result["in_marker_values"])
        self.assertEqual(result["metrics_missing"], [])
        self.assertIn("dominant_tier", result["global_signals"])
        self.assertTrue(result["verdict"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
