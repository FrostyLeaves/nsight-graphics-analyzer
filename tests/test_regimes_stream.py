"""Streaming + memory bound for parse.regimes — opt-in via NSIGHT_SKILL_REGIMES_SAMPLE."""
from __future__ import annotations

import tracemalloc
import unittest

from tests import _path  # noqa: F401
from tests._path import sample_regimes_path
from nsight.parse import regimes as regimes_parser


class TestRegimesStream(unittest.TestCase):
    def setUp(self):
        path = sample_regimes_path()
        if path is None:
            self.skipTest(
                "Set NSIGHT_SKILL_REGIMES_SAMPLE=<path/to/GPUTRACE_REGIMES.xls> "
                "to enable streaming-bound assertions."
            )
        self.regimes_path = path

    def test_header_columns_have_metrics(self):
        cells, metric_first_idx = regimes_parser.header_columns(self.regimes_path)
        self.assertGreater(len(cells), 1)
        self.assertGreater(len(metric_first_idx), 0)

    def test_streaming_bounded_memory(self):
        cells, metric_first_idx = regimes_parser.header_columns(self.regimes_path)
        # Pick at most 1 metric to project; we just want to confirm the streaming
        # path stays bounded regardless of file size.
        metric = next(iter(metric_first_idx))
        tracemalloc.start()
        rows_seen = 0
        # Hard-coded n_frames=40 matches the sample bundle — adjust via env if you
        # point this test at a trace with a different frame count.
        for _ in regimes_parser.iter_rows(self.regimes_path, n_frames=40, wanted_metrics=[metric]):
            rows_seen += 1
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertGreater(rows_seen, 0)
        self.assertLess(peak, 50 * 1024 * 1024,
                        f"streaming peak {peak} bytes > 50 MB")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
