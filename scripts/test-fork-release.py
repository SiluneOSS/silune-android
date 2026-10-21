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
from unittest import mock

spec = importlib.util.spec_from_file_location("fork_release", Path(__file__).with_name("fork-release.py"))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
UPSTREAM = {"version": "1.0.0", "build": 26, "tag": "v1.0.0-beta.26"}


class ForkReleaseTest(unittest.TestCase):
    def info(self, now=None, run=1):
        return release.metadata(now or dt.datetime(2026, 10, 22, 1, tzinfo=dt.timezone.utc), run,
                                "a" * 40, "b" * 40, upstream=UPSTREAM)

    def test_pacific_day_and_monotonic_codes(self):
        first = self.info()
        later = self.info(dt.datetime(2026, 10, 22, 2, tzinfo=dt.timezone.utc), run=2)
        self.assertEqual(first["tag"], "daily-2026-10-21.1")
        self.assertEqual(first["version_name"], "1.0.0 (26) (silune:10212026)")
        self.assertEqual(first["title"], "Silune 1.0.0 (26) (silune:10212026)")
        self.assertEqual(first["upstream_version_tag"], "v1.0.0-beta.26")
        self.assertGreater(later["version_code_base"], first["version_code_base"])
        self.assertLess(first["version_code_base"] * 2 + 1, 2_100_000_000)

    def test_clock_keeps_codes_increasing_when_run_counter_resets(self):
        first = self.info(run=999)
        later = self.info(dt.datetime(2026, 10, 23, 1, tzinfo=dt.timezone.utc), run=1)
        self.assertGreater(later["version_code_base"], first["version_code_base"])
        self.assertEqual(self.info(run=1000)["build_number"], 26)
        self.assertEqual(first["version_name"], self.info(run=1000)["version_name"])

    def test_rejects_invalid_provenance(self):
        with self.assertRaises(ValueError):
            self.info(run=0)
        with self.assertRaises(ValueError):
            release.metadata(dt.datetime.now(dt.timezone.utc), 1, "main", "b" * 40, upstream=UPSTREAM)

    def test_reserved_tag_survives_a_build_crossing_pacific_midnight(self):
        now = dt.datetime(2026, 10, 23, 8, tzinfo=dt.timezone.utc)
        info = release.metadata(now, 7, "a" * 40, "b" * 40, "daily-2026-10-22.7", upstream=UPSTREAM)
        self.assertEqual(info["tag"], "daily-2026-10-22.7")
        self.assertEqual(info["version_name"], "1.0.0 (26) (silune:10222026)")
        with self.assertRaises(ValueError):
            release.metadata(now, 7, "a" * 40, "b" * 40, "daily-2026-10-22.8", upstream=UPSTREAM)

    def test_official_tag_selection_is_bound_to_the_upstream_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True,
                                      capture_output=True, text=True).stdout.strip()

            git("init", "--quiet")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                "commit", "--allow-empty", "--quiet", "-m", "first")
            snapshot = git("rev-parse", "HEAD")
            # A fork-only tag and a lexically higher legacy version must not win.
            git("tag", "v9.9.9-beta.999")
            git("update-ref", "refs/silo-upstream/tags/v1.0.1-rc.2+3", snapshot)
            git("update-ref", "refs/silo-upstream/tags/v1.0.0+21", snapshot)
            self.assertEqual(release.upstream_version(root, snapshot),
                             {"version": "1.0.0", "build": 21, "tag": "v1.0.0+21"})
            # Exercise an annotated official tag as well as lightweight tags.
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                "tag", "-a", "v1.0.0-beta.26", "-m", "26")
            git("update-ref", "refs/silo-upstream/tags/v1.0.0-beta.26",
                git("rev-parse", "v1.0.0-beta.26"))
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                "commit", "--allow-empty", "--quiet", "-m", "future")
            git("update-ref", "refs/silo-upstream/tags/v1.1.0-beta.27", "HEAD")
            self.assertEqual(release.upstream_version(root, snapshot), UPSTREAM)
            self.assertEqual(release.upstream_version(root, "HEAD"),
                             {"version": "1.1.0", "build": 27, "tag": "v1.1.0-beta.27"})
            env = dict(os.environ, SOURCE_SHA="a" * 40, UPSTREAM_SHA=snapshot,
                       GITHUB_RUN_NUMBER="7", FORK_RELEASE_TAG="daily-2026-10-21.7",
                       RUNNER_TEMP=tmp, GITHUB_ENV=str(root / "env"), GITHUB_OUTPUT=str(root / "outputs"))
            subprocess.run(["python3", str(Path(release.__file__).resolve()), "prepare"],
                           cwd=root, env=env, check=True, capture_output=True, text=True)
            self.assertIn("SILO_VERSION_NAME=1.0.0 (26) (silune:10212026)\n", (root / "env").read_text())
            self.assertIn("SILO_BUILD_NUMBER=26\n", (root / "env").read_text())
            info = json.loads((root / "fork-build-info.json").read_text())
            self.assertEqual(info["upstream_version_tag"], "v1.0.0-beta.26")

    def test_missing_official_version_fails_instead_of_guessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "--quiet", tmp], check=True)
            # Simulate a successful Git lookup with no official release refs.
            with mock.patch.object(release.subprocess, "run") as run:
                run.return_value.stdout = ""
                with self.assertRaisesRegex(ValueError, "no official Silo build tag"):
                    release.upstream_version(Path(tmp), "a" * 40)

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
            self.assertEqual({path.name for path in out.iterdir()}, {
                "silune-phone.apk", "silune-tv.apk", "build-info.json", "SHA256SUMS", "RELEASE_NOTES.md",
            })
            self.assertEqual(json.loads((out / "build-info.json").read_text())["source_sha"], "a" * 40)
            for line in (out / "SHA256SUMS").read_text().splitlines():
                digest, name = line.split("  ")
                self.assertEqual(digest, hashlib.sha256((out / name).read_bytes()).hexdigest())
            self.assertEqual(len((out / "SHA256SUMS").read_text().splitlines()), 3)


class BuildDecisionTest(unittest.TestCase):
    source = "a" * 40
    tag = "daily-2026-10-21.3"

    def published(self, **changes):
        result = {
            "tag_name": self.tag, "draft": False, "prerelease": False,
            "published_at": "2026-10-21T23:00:00Z",
            "assets": [{"name": name, "size": 1} for name in [
                "silune-phone.apk", "silune-tv.apk",
                "build-info.json", "SHA256SUMS"]],
        }
        return dict(result, **changes)

    def test_same_files_skip_even_when_commit_history_changed(self):
        tree = mock.Mock(return_value="b" * 40)
        needed, reason = release.build_decision(self.source, [self.published()], tree)
        self.assertFalse(needed)
        self.assertIn("skipping build", reason)
        self.assertEqual(tree.call_args_list, [mock.call(self.source), mock.call(self.tag)])

    def test_changed_files_build_and_failed_runs_do_not_advance_baseline(self):
        for unfinished in [[], [self.published(tag_name="daily-2026-10-22.4", draft=True,
                                              published_at="2026-10-22T23:00:00Z")]]:
            with self.subTest(unfinished=unfinished):
                tree = mock.Mock(side_effect=["a" * 40, "b" * 40])
                needed, _ = release.build_decision(self.source, [self.published(), *unfinished], tree)
                self.assertTrue(needed)
                self.assertEqual(tree.call_args_list[-1], mock.call(self.tag))

    def test_first_release_and_incomplete_releases_require_builds(self):
        candidates = [
            [], [self.published(draft=True)], [self.published(prerelease=True)],
            [self.published(assets=[])], [self.published(tag_name="v1.0.0")],
        ]
        for releases in candidates:
            with self.subTest(releases=releases):
                tree = mock.Mock(side_effect=AssertionError("no baseline should be compared"))
                self.assertTrue(release.build_decision(self.source, releases, tree)[0])

    def test_most_recent_publication_wins_over_api_order(self):
        previous = self.published(tag_name="daily-2026-10-20.2", published_at="2026-10-20T23:00:00Z")
        tree = mock.Mock(return_value="b" * 40)
        self.assertFalse(release.build_decision(self.source, [self.published(), previous], tree)[0])
        self.assertEqual(tree.call_args_list[-1], mock.call(self.tag))

    def test_force_build_does_not_need_release_or_tree_queries(self):
        tree = mock.Mock(side_effect=AssertionError("force must not compare trees"))
        self.assertTrue(release.build_decision(self.source, [self.published()], tree, force=True)[0])
        tree.assert_not_called()

    def test_lookup_errors_and_invalid_trees_do_not_silently_skip(self):
        with self.assertRaises(subprocess.CalledProcessError):
            release.build_decision(self.source, [self.published()],
                                   mock.Mock(side_effect=subprocess.CalledProcessError(1, "gh")))
        with self.assertRaisesRegex(ValueError, "tree SHA"):
            release.build_decision(self.source, [self.published()], lambda ref: "")

    def test_decide_reads_all_release_pages_and_writes_job_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, summary = Path(tmp) / "output", Path(tmp) / "summary"
            env = dict(GITHUB_REPOSITORY="SiluneOSS/silune-android", SOURCE_SHA=self.source,
                       FORCE_BUILD="false", GITHUB_OUTPUT=str(output), GITHUB_STEP_SUMMARY=str(summary))
            def run(command, **kwargs):
                if "releases?per_page=100" in command[2]:
                    self.assertIn("--paginate", command)
                    self.assertIn("--slurp", command)
                    body = [[], [self.published()]]
                else:
                    body = {"commit": {"tree": {"sha": "b" * 40}}}
                return subprocess.CompletedProcess(command, 0, stdout=json.dumps(body))
            with mock.patch.dict(os.environ, env), mock.patch.object(release.subprocess, "run", side_effect=run):
                release.decide()
            self.assertEqual(output.read_text(), "should_build=false\n")
            self.assertIn("skipping build", summary.read_text())


class PublishRecoveryTest(unittest.TestCase):
    def run_publish(self, state):
        workflow = Path(__file__).resolve().parents[1] / ".github/workflows/fork-daily-release.yml"
        publish = workflow.read_text().split("      - name: Publish the GitHub release\n", 1)[1]
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
                self.assertIn("--prerelease=false --latest", calls)
                self.assertNotIn("--draft --prerelease", calls)
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
