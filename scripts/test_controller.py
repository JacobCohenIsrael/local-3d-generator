"""Offline controller checks; no models, GPU kernels, or server requests."""

import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

from native_process import OwnedProcess
from strata_plan import validate_plan


class ControllerTests(unittest.TestCase):
    def test_plan_validation(self):
        good = dict(seed=42, steps=30, octree_resolution=256, guidance_scale=5.0, num_chunks=4096)
        self.assertEqual(validate_plan(good), good)
        self.assertEqual(validate_plan(dict(good, octree_resolution=384))["octree_resolution"], 384)
        invalid = [dict(good, steps=True), dict(good, steps=100), dict(good, seed=-1),
                   dict(good, octree_resolution=512), dict(good, guidance_scale=float("nan")),
                   dict(good, num_chunks=999999), dict(good, command="anything")]
        for plan in invalid:
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                validate_plan(plan)

    def test_natural_exit(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "work") as folder:
            process = OwnedProcess([sys.executable, "-B", "-c", "print('owned child completed')"], Path(folder) / "out.log")
            self.assertEqual(process.wait(10), 0)
            self.assertTrue(process.shutdown_confirmed)

    def test_timeout_kills_descendants(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "work") as folder:
            code = "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print(p.pid,flush=True); time.sleep(60)"
            process = OwnedProcess([sys.executable, "-B", "-c", code], Path(folder) / "out.log")
            with self.assertRaises(TimeoutError):
                process.wait(2)
            self.assertTrue(process.shutdown_confirmed)
            self.assertIsNotNone(process.proc.poll())
            import psutil
            child_pid = int((Path(folder) / "out.log").read_text().strip())
            self.assertFalse(psutil.pid_exists(child_pid))

    def test_cancellation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "work") as folder:
            cancel = Path(folder) / "CANCEL"
            cancel.touch()
            process = OwnedProcess([sys.executable, "-B", "-c", "import time; time.sleep(60)"], Path(folder) / "out.log")
            with self.assertRaises(InterruptedError):
                process.wait(10, cancel=cancel)
            self.assertTrue(process.shutdown_confirmed)


if __name__ == "__main__":
    unittest.main()
