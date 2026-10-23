#!/usr/bin/env python3
"""Stamp and package Silune without the upstream Play workflow."""
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo


spec = importlib.util.spec_from_file_location("release_version", Path(__file__).with_name("release-version.py"))
release_version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_version)


def build_decision(source_sha, releases, tree_for, force=False):
    """Compare source files with the last complete, published fork release."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("source commit must be a full Git SHA")
    if force:
        return True, "Manual force build requested."
    required = {"silune-phone.apk", "silune-tv.apk",
                "build-info.json", "SHA256SUMS"}
    published = [
        release for release in releases
        if release.get("draft") is False and release.get("prerelease") is False
        and release.get("published_at")
        and re.fullmatch(r"daily-\d{4}-\d{2}-\d{2}\.\d+", release.get("tag_name", ""))
        and required <= {asset["name"] for asset in release.get("assets", []) if asset.get("size", 0) > 0}
    ]
    if not published:
        return True, "No complete published fork release exists yet."
    previous = max(published, key=lambda release: release["published_at"])["tag_name"]
    current_tree, previous_tree = tree_for(source_sha), tree_for(previous)
    if not all(re.fullmatch(r"[0-9a-f]{40}", tree) for tree in (current_tree, previous_tree)):
        raise ValueError("GitHub returned an invalid source tree SHA")
    if current_tree == previous_tree:
        return False, f"Source files match the last published release ({previous}); skipping build."
    return True, f"Source files changed since the last published release ({previous})."


def decide():
    repo = os.environ["GITHUB_REPOSITORY"]

    def api(path, paginate=False):
        command = ["gh", "api", f"repos/{repo}/{path}"]
        if paginate:
            command += ["--paginate", "--slurp"]
        return json.loads(subprocess.run(command, check=True, capture_output=True, text=True).stdout)

    force = os.environ.get("FORCE_BUILD", "false") == "true"
    # A failed API request must fail the run, rather than silently skip work.
    pages = [] if force else api("releases?per_page=100", paginate=True)
    releases = [release for page in pages for release in page]
    needed, reason = build_decision(
        os.environ["SOURCE_SHA"], releases,
        lambda ref: api(f"commits/{ref}")["commit"]["tree"]["sha"], force=force,
    )
    with open(os.environ["GITHUB_OUTPUT"], "a") as out:
        print(f"should_build={str(needed).lower()}", file=out)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as out:
        print(reason, file=out)
    print(reason)


def upstream_version(root, upstream_sha):
    """Use only official release tags included in this upstream snapshot.

    The workflow fetches these into a separate namespace so inherited fork tags
    cannot mislabel the build. Silo's repository-wide build counter determines
    the newest build, including older +B tags and current -beta.B tags.
    """
    tags = subprocess.run(
        ["git", "for-each-ref", f"--merged={upstream_sha}",
         "--format=%(refname:strip=3)", "refs/silo-upstream/tags/"],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    builds = []
    for name in tags:
        parsed = release_version.parse_tag(name)
        if parsed and parsed[2] is not None and parsed[2] > 0:
            version, _, build = parsed
            builds.append((build, version, name))
    if not builds:
        raise ValueError("no official Silo build tag is included in this upstream snapshot")
    build, version, tag = max(builds)
    if build > 999:
        raise ValueError("upstream build exceeds the Android build number limit")
    return {"version": release_version.version_text(version), "build": build, "tag": tag}


def metadata(now, run_number, source_sha, upstream_sha, reserved_tag=None, *, upstream):
    if run_number < 1:
        raise ValueError("run number must be positive")
    for sha in (source_sha, upstream_sha):
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("source commits must be full Git SHAs")
    day = now.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
    if reserved_tag:
        match = re.fullmatch(rf"daily-(\d{{4}}-\d{{2}}-\d{{2}})\.{run_number}", reserved_tag)
        if not match:
            raise ValueError("reserved tag must match this workflow run")
        day = dt.date.fromisoformat(match[1]).isoformat()
    # Above the upstream release range, increasing with time even if this
    # workflow is recreated and GitHub resets its run counter.
    base = 400_000_000 + int((now - dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)).total_seconds())
    if not 0 < base <= 1_049_999_999:
        raise ValueError("version code is outside the Android build's allowed range")
    silune_date = dt.date.fromisoformat(day).strftime("%m%d%Y")
    version_name = f"{upstream['version']} ({upstream['build']}) (silune:{silune_date})"
    return {
        "tag": f"daily-{day}.{run_number}",
        "title": f"Silune {version_name}",
        "version_name": version_name,
        "version_code_base": base,
        "build_number": upstream["build"],
        "upstream_version": upstream["version"],
        "upstream_version_tag": upstream["tag"],
        "silune_date": silune_date,
        "run_number": run_number,
        "source_sha": source_sha,
        "upstream_checked_sha": upstream_sha,
        "built_at": now.isoformat(),
    }


def prepare():
    upstream = upstream_version(Path.cwd(), os.environ["UPSTREAM_SHA"])
    info = metadata(dt.datetime.now(dt.timezone.utc), int(os.environ["GITHUB_RUN_NUMBER"]),
                    os.environ["SOURCE_SHA"], os.environ["UPSTREAM_SHA"], os.environ.get("FORK_RELEASE_TAG"),
                    upstream=upstream)
    path = Path(os.environ["RUNNER_TEMP"]) / "fork-build-info.json"
    path.write_text(json.dumps(info, indent=2) + "\n")
    with open(os.environ["GITHUB_ENV"], "a") as out:
        for key, value in {
            "FORK_BUILD_INFO": str(path), "SILO_VERSION_NAME": info["version_name"],
            "SILO_VERSION_CODE": info["version_code_base"],
            "SILO_BUILD_NUMBER": info["build_number"], "SILO_RELEASE_CHANNEL": "sideload",
        }.items():
            print(f"{key}={value}", file=out)
    with open(os.environ["GITHUB_OUTPUT"], "a") as out:
        for key in ("tag", "title"):
            print(f"{key}={info[key]}", file=out)


def package(root, info, out):
    sources = {
        "silune-phone.apk": root / "androidApp/build/outputs/apk/release/androidApp-universal-release.apk",
        "silune-tv.apk": root / "androidTvApp/build/outputs/apk/release/androidTvApp-universal-release.apk",
    }
    # Fail before creating a partial distribution if either app is missing.
    for path in sources.values():
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"missing or empty release APK: {path}")
    out.mkdir(parents=True, exist_ok=True)
    for name, source in sources.items():
        shutil.copyfile(source, out / name)
    (out / "build-info.json").write_text(json.dumps(info, indent=2) + "\n")
    names = sorted([*sources, "build-info.json"])
    (out / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256((out / name).read_bytes()).hexdigest()}  {name}\n" for name in names))
    (out / "RELEASE_NOTES.md").write_text(
        f"{info['title']}\n\n"
        "Unofficial, optimized release builds of Silune, a fork of the Silo Android clients. "
        "Includes the fork's HEVC level override, defaulting to 6.2.\n\n"
        f"Version: **{info['version_name']}**. Based on Silo `{info['upstream_version_tag']}` "
        "plus the upstream changes included in the source snapshot below. "
        "The Silune date uses Pacific time (MMDDYYYY).\n\n"
        "- `silune-phone.apk`: Android phones and tablets.\n"
        "- `silune-tv.apk`: Android TV / Google TV.\n"
        "- Both APKs are universal and signed with the persistent release key.\n"
        "- These are optimized release APKs, published as regular GitHub releases.\n"
        "- Latest phone APK: https://github.com/SiluneOSS/silune-android/releases/latest/download/silune-phone.apk\n"
        "- Latest TV APK: https://github.com/SiluneOSS/silune-android/releases/latest/download/silune-tv.apk\n\n"
        "Silune uses its own application ID and installs separately from Silo. "
        "Later Silune builds signed with the same release key can update in place.\n\n"
        f"Source: https://github.com/SiluneOSS/silune-android/tree/{info['source_sha']}\n\n"
        f"Upstream checked: https://github.com/Silo-Server/silo-android/commit/{info['upstream_checked_sha']}\n\n"
        "Verify downloads with `sha256sum --check SHA256SUMS`. "
        "Source code is available under AGPL-3.0-or-later; third-party notices remain in the repository.\n")


if __name__ == "__main__":
    if sys.argv[1:] == ["decide"]:
        decide()
    elif sys.argv[1:] == ["prepare"]:
        prepare()
    elif sys.argv[1:] == ["package"]:
        package(Path.cwd(), json.loads(Path(os.environ["FORK_BUILD_INFO"]).read_text()), Path("dist"))
    else:
        raise SystemExit("usage: fork-release.py decide|prepare|package")
