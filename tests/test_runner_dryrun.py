"""Dry-run argv assertions for runner.gpu_trace + mutex enforcement."""
from __future__ import annotations

import unittest

from tests import _path  # noqa: F401
from nsight.runner import cpp, gpu_trace, graphics


_FAKE_NGFX = "/path/to/ngfx.exe"


class TestGpuTraceArgv(unittest.TestCase):
    def test_basic_argv_has_auto_export(self):
        argv = gpu_trace.build_argv(
            _FAKE_NGFX,
            exe="C:/apps/TestApp.exe",
            start_after_ms=1000,
            limit_to_frames=5,
            architecture="Ada",
            metric_set_name="Throughput Metrics",
        )
        self.assertIn("--auto-export", argv)
        self.assertIn("--start-after-ms", argv)
        self.assertIn("--max-duration-ms", argv)
        self.assertIn("--limit-to-frames", argv)
        self.assertIn("--architecture", argv)
        self.assertIn("--metric-set-name", argv)
        self.assertIn("--no-timeout", argv)

    def test_two_start_triggers_rejected(self):
        with self.assertRaises(gpu_trace.GpuTraceConfigError):
            gpu_trace.build_argv(
                _FAKE_NGFX,
                exe="C:/apps/TestApp.exe",
                start_after_ms=1000,
                start_after_frames=10,
                architecture="Ada",
            )

    def test_two_stop_limits_rejected(self):
        with self.assertRaises(gpu_trace.GpuTraceConfigError):
            gpu_trace.build_argv(
                _FAKE_NGFX,
                exe="C:/apps/TestApp.exe",
                start_after_ms=1000,
                limit_to_frames=5,
                limit_to_submits=10,
                architecture="Ada",
            )

    def test_metric_set_mutex(self):
        with self.assertRaises(gpu_trace.GpuTraceConfigError):
            gpu_trace.build_argv(
                _FAKE_NGFX,
                exe="C:/apps/TestApp.exe",
                start_after_ms=1000,
                metric_set_name="Throughput Metrics",
                metric_set_id=0,
                architecture="Ada",
            )

    def test_invalid_architecture(self):
        with self.assertRaises(gpu_trace.GpuTraceConfigError):
            gpu_trace.build_argv(
                _FAKE_NGFX,
                exe="C:/apps/TestApp.exe",
                start_after_ms=1000,
                architecture="Lovelace GH100",  # not a real ngfx arch
            )

    def test_attach_pid_argv(self):
        argv = gpu_trace.build_argv(
            _FAKE_NGFX,
            attach_pid=12345,
            start_after_ms=1000,
            architecture="Ada",
        )
        self.assertIn("--attach-pid", argv)
        idx = argv.index("--attach-pid")
        self.assertEqual(argv[idx + 1], "12345")
        self.assertNotIn("--exe", argv)

    def test_exe_and_attach_pid_mutex(self):
        with self.assertRaises(gpu_trace.GpuTraceConfigError):
            gpu_trace.build_argv(
                _FAKE_NGFX,
                exe="C:/apps/TestApp.exe",
                attach_pid=12345,
                start_after_ms=1000,
                architecture="Ada",
            )


class TestGraphicsCaptureArgv(unittest.TestCase):
    def test_unified_frame_index(self):
        argv = graphics.build_unified_argv(
            _FAKE_NGFX,
            exe="C:/apps/TestApp.exe",
            frame_index=100,
            frame_count=2,
        )
        self.assertIn("--activity=Graphics Capture", argv)
        self.assertIn("--frame-index", argv)
        self.assertIn("--frame-count", argv)

    def test_unified_trigger_mutex(self):
        with self.assertRaises(graphics.GraphicsCaptureConfigError):
            graphics.build_unified_argv(
                _FAKE_NGFX,
                exe="C:/apps/TestApp.exe",
                frame_index=100,
                hotkey_capture=True,
            )


class TestCppCaptureArgv(unittest.TestCase):
    def test_basic_wait_seconds(self):
        argv = cpp.build_argv(
            _FAKE_NGFX,
            exe="C:/apps/TestApp.exe",
            wait_seconds=10,
        )
        self.assertIn("--activity=Generate C++ Capture", argv)
        self.assertIn("--wait-seconds", argv)

    def test_trigger_mutex(self):
        with self.assertRaises(cpp.CppCaptureConfigError):
            cpp.build_argv(
                _FAKE_NGFX,
                exe="C:/apps/TestApp.exe",
                wait_frames=5,
                wait_seconds=10,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
