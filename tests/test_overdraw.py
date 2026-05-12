"""gputrace-overdraw query: concept resolution, ratio math, global path."""
from __future__ import annotations

import unittest

from tests import _path  # noqa: F401
from tests._path import sample_bundle_dir
from nsight.queries import overdraw as overdraw_query


class TestResolveConcepts(unittest.TestCase):
    """Pure function: regex matching against a synthetic metric catalog."""

    def test_resolves_canonical_names(self):
        names = [
            "GPC_A.TriageSCG.prop__input_pixels_type_3d_realtime.sum",
            "GPC_A.TriageSCG.prop__prop2crop_pixels_realtime.sum",
            "GPC_A.TriageSCG.prop__prop2zrop_pixels_op_passed_realtime.sum",
            "GPC_A.TriageSCG.raster__zcull_input_samples_realtime.sum",
            "GPC_A.TriageSCG.raster__zcull_input_samples_op_accepted_realtime.sum",
            "crop__write_throughput.avg.pct_of_peak_sustained_elapsed",
            "zrop__write_throughput.avg.pct_of_peak_sustained_elapsed",
        ]
        resolved, missing = overdraw_query._resolve_concepts(names)
        self.assertEqual(missing, [])
        for key in overdraw_query._CONCEPT_PATTERNS:
            self.assertIn(key, resolved)

    def test_reports_missing_concepts(self):
        names = ["crop__write_throughput.avg.pct_of_peak_sustained_elapsed"]
        resolved, missing = overdraw_query._resolve_concepts(names)
        self.assertEqual(list(resolved.keys()), ["crop_write_pct"])
        # Everything else missing.
        self.assertEqual(set(missing), set(overdraw_query._CONCEPT_PATTERNS) - {"crop_write_pct"})

    def test_does_not_match_pct_variant_for_sum_concept(self):
        # Anchored `\.sum$` should reject the per-cycle / pct variants.
        names = [
            "GPC_A.TriageSCG.prop__input_pixels_type_3d_realtime.avg.pct_of_peak_sustained_elapsed",
            "GPC_A.TriageSCG.prop__input_pixels_type_3d_realtime.avg.per_cycle_elapsed",
        ]
        resolved, missing = overdraw_query._resolve_concepts(names)
        self.assertIn("pixels_input", missing)


class TestRatioMath(unittest.TestCase):
    """Pure function: compute ratios from a values dict."""

    def test_typical_inputs(self):
        ratios = overdraw_query._compute_ratios({
            "pixels_input":   3_000_000.0,
            "pixels_to_crop": 1_000_000.0,
            "pixels_passed_z": 500_000.0,
            "zcull_input":   10_000_000.0,
            "zcull_accepted": 4_000_000.0,
            "crop_write_pct": 72.0,
            "zrop_write_pct": 12.0,
        })
        self.assertAlmostEqual(ratios["overdraw_ratio"], 3.0)
        self.assertAlmostEqual(ratios["zcull_rejection_rate"], 0.6)
        self.assertAlmostEqual(ratios["late_z_pass_rate"], 1/6)
        self.assertAlmostEqual(ratios["late_z_attrition_rate"], 5/6)
        self.assertEqual(ratios["color_write_pct"], 72.0)
        self.assertEqual(ratios["depth_write_pct"], 12.0)

    def test_zero_denominators_yield_none(self):
        ratios = overdraw_query._compute_ratios({
            "pixels_input":   0.0,
            "pixels_to_crop": 0.0,
            "pixels_passed_z": 0.0,
            "zcull_input":   0.0,
            "zcull_accepted": 0.0,
            "crop_write_pct": None,
            "zrop_write_pct": None,
        })
        self.assertIsNone(ratios["overdraw_ratio"])
        self.assertIsNone(ratios["zcull_rejection_rate"])
        self.assertIsNone(ratios["late_z_pass_rate"])
        self.assertIsNone(ratios["color_write_pct"])

    def test_missing_inputs_yield_none(self):
        ratios = overdraw_query._compute_ratios({})
        for key in ("overdraw_ratio", "zcull_rejection_rate", "late_z_pass_rate",
                    "color_write_pct", "depth_write_pct"):
            self.assertIsNone(ratios[key])


class TestVerdict(unittest.TestCase):
    """Verdict thresholds turn ratios into severity-tagged messages."""

    def test_high_overdraw_emits_high_severity(self):
        v = overdraw_query._verdict("global", {"overdraw_ratio": 3.5,
                                               "zcull_rejection_rate": 0.5,
                                               "late_z_attrition_rate": 0.1,
                                               "color_write_pct": 50.0})
        tags = {item["tag"]: item["severity"] for item in v}
        self.assertEqual(tags["overdraw_high"], "high")

    def test_clean_frame_emits_low_overdraw(self):
        v = overdraw_query._verdict("global", {"overdraw_ratio": 1.05,
                                               "zcull_rejection_rate": 0.8,
                                               "late_z_attrition_rate": 0.05,
                                               "color_write_pct": 20.0})
        tags = {item["tag"]: item["severity"] for item in v}
        self.assertIn("overdraw_low", tags)
        # No high/medium warnings for the other dimensions.
        self.assertNotIn("zcull_underused", tags)
        self.assertNotIn("late_z_attrition_high", tags)
        self.assertNotIn("crop_bandwidth_pressure", tags)

    def test_data_missing_when_overdraw_unavailable(self):
        v = overdraw_query._verdict("global", {})
        tags = {item["tag"] for item in v}
        self.assertIn("data_missing", tags)


class TestGlobalQueryAgainstSample(unittest.TestCase):
    """End-to-end against the in-tree sample bundle (REGIMES not required for global path)."""

    @classmethod
    def setUpClass(cls):
        cls.bundle = sample_bundle_dir()
        cls.fake_trace = cls.bundle.parent / "fake.ngfx-gputrace"
        cls.fake_trace.write_bytes(b"")

    @classmethod
    def tearDownClass(cls):
        cls.fake_trace.unlink(missing_ok=True)

    def test_global_query_returns_full_structure(self):
        result = overdraw_query.query(self.fake_trace, in_marker_re=None)
        self.assertEqual(result["schema_version"], 1)
        self.assertIsNone(result["in_marker_values"])
        self.assertIsNone(result["in_marker_ratios"])
        # All 7 concepts resolve on the sample bundle (it was captured with
        # Throughput Metrics on Ada, same as TestApp).
        self.assertEqual(result["metrics_missing"], [])
        for key in overdraw_query._CONCEPT_PATTERNS:
            self.assertIn(key, result["global_values"])
        # Verdict is non-empty (either a real finding or `data_missing`).
        self.assertTrue(result["verdict"])
        for item in result["verdict"]:
            self.assertEqual(item["scope"], "global")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
