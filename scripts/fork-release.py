#!/usr/bin/env python3
"""Stamp and package the SigmaStreams fork without the upstream Play workflow."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from zoneinfo import ZoneInfo


def metadata(now, run_number, source_sha, upstream_sha):
    if run_number < 1:
        raise ValueError("run number must be positive")
    for sha in (source_sha, upstream_sha):
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("source commits must be full Git SHAs")
    day = now.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
    # Above the upstream release range, increasing with time even if this
    # workflow is recreated and GitHub resets its run counter.
    base = 400_000_000 + int((now - dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)).total_seconds())
    if not 0 < base <= 1_049_999_999:
        raise ValueError("version code is outside the Android build's allowed range")
    return {
        "tag": f"daily-{day}.{run_number}",
        "title": f"SigmaStreams Player daily {day} #{run_number}",
        "version_name": f"{day.replace('-', '.')}-daily.{run_number}",
        "version_code_base": base,
        # The upstream About-row build field is limited to 1..999. The full
        # run counter stays in version_name and this provenance file.
        "build_number": (run_number - 1) % 999 + 1,
        "run_number": run_number,
        "source_sha": source_sha,
        "upstream_checked_sha": upstream_sha,
        "built_at": now.isoformat(),
    }


def prepare():
    info = metadata(dt.datetime.now(dt.timezone.utc), int(os.environ["GITHUB_RUN_NUMBER"]),
                    os.environ["SOURCE_SHA"], os.environ["UPSTREAM_SHA"])
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
        "sigmastreams-player-phone.apk": root / "androidApp/build/outputs/apk/release/androidApp-universal-release.apk",
        "sigmastreams-player-tv.apk": root / "androidTvApp/build/outputs/apk/release/androidTvApp-universal-release.apk",
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
        "Unofficial, optimized release builds of SigmaStreams Player, a fork of the Silo Android clients. "
        "Includes the fork's HEVC level override, defaulting to 6.2.\n\n"
        "- `sigmastreams-player-phone.apk`: Android phones and tablets.\n"
        "- `sigmastreams-player-tv.apk`: Android TV / Google TV.\n"
        "- Both APKs are universal and signed with the persistent SigmaStreams key.\n"
        "- These are GitHub prereleases; the APKs are release builds, not debug builds.\n\n"
        "The initial switch from an official or locally debug-signed app requires an uninstall because "
        "the signing keys differ; uninstalling removes local app data and downloads. "
        "Later SigmaStreams builds can update in place.\n\n"
        f"Source: https://github.com/SigmaStreams/silo-android/tree/{info['source_sha']}\n\n"
        f"Upstream checked: https://github.com/Silo-Server/silo-android/commit/{info['upstream_checked_sha']}\n\n"
        "Verify downloads with `sha256sum --check SHA256SUMS`. "
        "Source code is available under AGPL-3.0-or-later; third-party notices remain in the repository.\n")


if __name__ == "__main__":
    if sys.argv[1:] == ["prepare"]:
        prepare()
    elif sys.argv[1:] == ["package"]:
        package(Path.cwd(), json.loads(Path(os.environ["FORK_BUILD_INFO"]).read_text()), Path("dist"))
    else:
        raise SystemExit("usage: fork-release.py prepare|package")
