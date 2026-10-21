#!/usr/bin/env python3
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("fork_release", Path(__file__).with_name("fork-release.py"))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ForkReleaseTest(unittest.TestCase):
    def info(self, now=None, run=1):
        return release.metadata(now or dt.datetime(2026, 10, 22, 1, tzinfo=dt.timezone.utc), run, "a" * 40, "b" * 40)

    def test_pacific_day_and_monotonic_codes(self):
        first = self.info()
        later = self.info(dt.datetime(2026, 10, 22, 2, tzinfo=dt.timezone.utc), run=2)
        self.assertEqual(first["tag"], "daily-2026-10-21.1")
        self.assertGreater(later["version_code_base"], first["version_code_base"])
        self.assertLess(first["version_code_base"] * 2 + 1, 2_100_000_000)

    def test_clock_keeps_codes_increasing_when_run_counter_resets(self):
        first = self.info(run=999)
        later = self.info(dt.datetime(2026, 10, 23, 1, tzinfo=dt.timezone.utc), run=1)
        self.assertGreater(later["version_code_base"], first["version_code_base"])
        self.assertEqual(self.info(run=1000)["build_number"], 1)

    def test_rejects_invalid_provenance(self):
        with self.assertRaises(ValueError):
            self.info(run=0)
        with self.assertRaises(ValueError):
            release.metadata(dt.datetime.now(dt.timezone.utc), 1, "main", "b" * 40)

    def test_requires_both_apks_before_packaging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                release.package(root, self.info(), root / "dist")
            self.assertFalse((root / "dist").exists())

    def test_checksums_cover_actual_apks_and_source_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for module in ("androidApp", "androidTvApp"):
                path = root / module / "build/outputs/apk/release" / f"{module}-universal-release.apk"
                path.parent.mkdir(parents=True)
                path.write_bytes(module.encode())
            out = root / "dist"
            release.package(root, self.info(), out)
            self.assertEqual(json.loads((out / "build-info.json").read_text())["source_sha"], "a" * 40)
            for line in (out / "SHA256SUMS").read_text().splitlines():
                digest, name = line.split("  ")
                self.assertEqual(digest, hashlib.sha256((out / name).read_bytes()).hexdigest())
            self.assertEqual(len((out / "SHA256SUMS").read_text().splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
