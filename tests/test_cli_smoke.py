"""End-to-end CLI: gputrace rebuild + drill subcommands all exit 0 on the sample."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import _path  # noqa: F401
from tests._path import sample_bundle_dir


_SCRIPTS_NSIGHT_PY = _path._SCRIPTS_DIR / "nsight.py"


def _run_cli(*args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS_NSIGHT_PY), *args],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


class TestCliSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Materialize a temporary "trace" + BASE/ that mirrors a real session
        # layout, so commands that look for trace.parent/BASE/ can find files.
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="nsight-graphics-analyzer-cli-"))
        cls.fake_trace = cls.tmpdir / "fake.ngfx-gputrace"
        cls.fake_trace.write_bytes(b"")
        for src in sample_bundle_dir().iterdir():
            (cls.tmpdir / "BASE").mkdir(exist_ok=True)
            shutil.copy(src, cls.tmpdir / "BASE" / src.name)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_help(self):
        rc, stdout, _ = _run_cli("--help")
        self.assertEqual(rc, 0)
        self.assertIn("gputrace-capture", stdout)
        self.assertIn("gputrace-stages", stdout)

    def test_gputrace_rebuild(self):
        rc, _, stderr = _run_cli("gputrace", str(self.fake_trace))
        self.assertEqual(rc, 0, msg=stderr)
        for suffix in ("summary.json", "stages.json", "actions.json"):
            path = self.tmpdir / f"fake.gputrace.{suffix}"
            self.assertTrue(path.exists(), f"{path} missing")
            self.assertGreater(path.stat().st_size, 100)

    def test_gputrace_stages_drill(self):
        rc, stdout, stderr = _run_cli(
            "gputrace-stages", str(self.fake_trace), "--top", "3",
        )
        self.assertEqual(rc, 0, msg=stderr)
        doc = json.loads(stdout)
        self.assertEqual(doc["scope"], "depth_1")
        self.assertLessEqual(len(doc["stages"]), 3)

    def test_gputrace_actions_drill(self):
        rc, stdout, stderr = _run_cli(
            "gputrace-actions", str(self.fake_trace), "--top", "3",
        )
        self.assertEqual(rc, 0, msg=stderr)
        doc = json.loads(stdout)
        self.assertLessEqual(doc["count"], 3)

    def test_gputrace_metric_unique_match(self):
        rc, stdout, stderr = _run_cli(
            "gputrace-metric", str(self.fake_trace),
            "--name", "GPUTrace.sm__throughput.avg.pct_of_peak_sustained_elapsed",
        )
        self.assertEqual(rc, 0, msg=stderr)
        doc = json.loads(stdout)
        self.assertEqual(doc["sample_count"], 40)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
