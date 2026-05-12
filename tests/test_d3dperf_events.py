"""D3DPERF_EVENTS marker-tree parser + naive-vs-paired heuristic."""
from __future__ import annotations

import unittest

from tests import _path  # noqa: F401
from tests._path import sample_bundle_dir
from nsight.parse import d3dperf_events, frame as frame_parser


class TestD3DPerfEvents(unittest.TestCase):
    def test_parses_marker_tree_with_correct_paths(self):
        frames = frame_parser.parse(sample_bundle_dir() / "FRAME.xls")
        trace_span_ms = sum(frames)
        result = d3dperf_events.parse(
            sample_bundle_dir() / "D3DPERF_EVENTS.xls",
            trace_span_ms=trace_span_ms,
        )
        self.assertGreater(result["marker_count"], 100)
        markers = result["markers"]

        # Roots (depth 0) — ngfx uses FrameTime.GPU as the conventional root.
        roots = [m for m in markers if m["depth"] == 0]
        self.assertTrue(roots, "expected at least one depth-0 marker")
        self.assertIn("FrameTime.GPU", {r["name"] for r in roots})

        # Path reconstruction: every non-root marker's parent_path is the
        # slash-joined ancestor names.
        for marker in markers:
            if marker["depth"] == 0:
                self.assertEqual(marker["parent_path"], "")
            else:
                self.assertTrue(marker["parent_path"], f"missing parent: {marker['name']}")
                expected_path = f"{marker['parent_path']}/{marker['name']}"
                self.assertEqual(marker["path"], expected_path)

    def test_total_durations_within_trace_span(self):
        frames = frame_parser.parse(sample_bundle_dir() / "FRAME.xls")
        trace_span_ms = sum(frames)
        result = d3dperf_events.parse(
            sample_bundle_dir() / "D3DPERF_EVENTS.xls",
            trace_span_ms=trace_span_ms,
        )
        # Durations are clamped to the trace span; suspect rows are flagged.
        for marker in result["markers"]:
            self.assertLessEqual(
                marker["total_duration_ms"], trace_span_ms + 1e-6,
                f"{marker['name']} exceeds trace span"
            )

    def test_leaf_annotation(self):
        frames = frame_parser.parse(sample_bundle_dir() / "FRAME.xls")
        result = d3dperf_events.parse(
            sample_bundle_dir() / "D3DPERF_EVENTS.xls",
            trace_span_ms=sum(frames),
        )
        leaves = [m for m in result["markers"] if m.get("is_leaf")]
        non_leaves = [m for m in result["markers"] if not m.get("is_leaf")]
        self.assertTrue(leaves, "expected leaves")
        self.assertTrue(non_leaves, "expected non-leaves (internal nodes)")
        # FrameTime.GPU is at depth 0 and has descendants.
        for marker in non_leaves:
            if marker["name"] == "FrameTime.GPU":
                self.assertFalse(marker["is_leaf"])
                break


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
