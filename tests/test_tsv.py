"""tsv.iter_lines + parse_floats sanity."""
from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from tests import _path  # noqa: F401  (sys.path side effect)
from nsight.parse import tsv


class TestParseFloats(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(tsv.parse_floats("1.0\t2.0\t3.0"), [1.0, 2.0, 3.0])

    def test_skips_empty_cells(self):
        self.assertEqual(tsv.parse_floats("1\t\t2"), [1.0, 2.0])

    def test_drops_nan_inf(self):
        out = tsv.parse_floats("1\tnan\tinf\t-inf\t2")
        self.assertEqual(out, [1.0, 2.0])
        for v in out:
            self.assertFalse(math.isnan(v))
            self.assertFalse(math.isinf(v))

    def test_ignores_unparseable(self):
        self.assertEqual(tsv.parse_floats("1\tabc\t2"), [1.0, 2.0])

    def test_empty_input(self):
        self.assertEqual(tsv.parse_floats(""), [])


class TestIterLines(unittest.TestCase):
    def test_crlf_and_bom(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".xls", delete=False) as fh:
            # UTF-8 BOM + CRLF line endings (mirrors the real ngfx output)
            fh.write(b"\xef\xbb\xbfhello\tworld\r\n42\t99\r\n")
            tmp = Path(fh.name)
        try:
            lines = list(tsv.iter_lines(tmp))
        finally:
            tmp.unlink()
        self.assertEqual(lines, ["hello\tworld", "42\t99"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
