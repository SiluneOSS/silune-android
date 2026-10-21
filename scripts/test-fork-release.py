#!/usr/bin/env python3
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
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

    def test_reserved_tag_survives_a_build_crossing_pacific_midnight(self):
        now = dt.datetime(2026, 10, 23, 8, tzinfo=dt.timezone.utc)
        info = release.metadata(now, 7, "a" * 40, "b" * 40, "daily-2026-10-22.7")
        self.assertEqual(info["tag"], "daily-2026-10-22.7")
        self.assertEqual(info["version_name"], "2026.10.22-daily.7")
        with self.assertRaises(ValueError):
            release.metadata(now, 7, "a" * 40, "b" * 40, "daily-2026-10-22.8")

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


class PublishRecoveryTest(unittest.TestCase):
    def run_publish(self, state):
        workflow = Path(__file__).resolve().parents[1] / ".github/workflows/fork-daily-release.yml"
        publish = workflow.read_text().split("      - name: Publish the GitHub prerelease\n", 1)[1]
        script = textwrap.dedent(publish.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "dist"
            dist.mkdir()
            (dist / "phone.apk").write_bytes(b"signed-apk")
            (dist / "build-info.json").write_text('{}\n')
            (dist / "RELEASE_NOTES.md").write_text('Daily build\n')
            (dist / "SHA256SUMS").write_text(
                f"{hashlib.sha256(b'signed-apk').hexdigest()}  phone.apk\n")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            gh = bin_dir / "gh"
            gh.write_text('''#!/usr/bin/python3
import json, os, pathlib, shutil, sys
args = sys.argv[1:]
root = pathlib.Path(os.environ['RUNNER_TEMP'])
with (root / 'calls').open('a') as out:
    print(' '.join(args), file=out)
state = os.environ['TEST_STATE']
if args[:2] == ['release', 'view']:
    if '--jq' in args:
        print('https://example.test/release')
    elif state == 'new':
        sys.exit(1)
    else:
        print(json.dumps({'isDraft': state != 'published',
                          'targetCommitish': 'main' if state == 'default-target' else 'a' * 40}))
elif args[0] == 'api':
    # A snapshot tag is reserved before the expensive build starts.
    print(('b' if state == 'wrong-tag' else 'a') * 40)
elif args[:2] == ['release', 'download']:
    destination = pathlib.Path(args[args.index('--dir') + 1])
    shutil.copytree(root / 'dist', destination)
    if state == 'corrupt':
        (destination / 'phone.apk').write_bytes(b'corrupted')
''')
            gh.chmod(0o755)
            env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", RUNNER_TEMP=str(root),
                       TEST_STATE=state, TAG="daily-test.1", SOURCE_SHA="a" * 40,
                       GH_REPO="example/repo", TITLE="Daily build", GITHUB_STEP_SUMMARY=str(root / "summary"))
            result = subprocess.run(["bash", "-c", script], cwd=root, env=env, capture_output=True, text=True)
            calls = (root / "calls").read_text()
            return result.returncode, calls, result.stdout + result.stderr

    def test_new_and_interrupted_draft_publish_after_readback(self):
        for state in ("new", "draft"):
            with self.subTest(state=state):
                code, calls, output = self.run_publish(state)
                self.assertEqual(code, 0, output)
                self.assertIn("release upload", calls)
                self.assertLess(calls.index("release download"), calls.index("release edit"))
                self.assertIn("--draft=false", calls)
                if state == "new":
                    self.assertIn("--verify-tag", calls)
                    self.assertNotIn("--target", calls)

    def test_tag_for_a_different_source_blocks_release_creation(self):
        code, calls, _ = self.run_publish("wrong-tag")
        self.assertNotEqual(code, 0)
        self.assertNotIn("release create", calls)
        self.assertNotIn("release upload", calls)

    def test_published_assets_are_not_replaced(self):
        code, calls, output = self.run_publish("published")
        self.assertEqual(code, 0, output)
        self.assertNotIn("release upload", calls)
        self.assertNotIn("release edit", calls)

    def test_draft_with_unused_default_target_can_resume_from_verified_tag(self):
        code, calls, output = self.run_publish("default-target")
        self.assertEqual(code, 0, output)
        self.assertIn("release upload", calls)
        self.assertIn("--draft=false", calls)

    def test_failed_download_checksum_blocks_publication(self):
        code, calls, _ = self.run_publish("corrupt")
        self.assertNotEqual(code, 0)
        self.assertNotIn("release edit", calls)


if __name__ == "__main__":
    unittest.main()
