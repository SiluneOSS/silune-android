# Σ Player daily releases

The fork publishes optimized, signed phone and TV APKs on
[GitHub Releases](https://github.com/SigmaStreams/silo-android/releases).
These are unofficial builds of the Silo Android clients, with Σ Player
branding and Ignore HEVC Level Limits enabled by default. The playback setting
is an On/Off switch: On removes HEVC level bounds from capability reports, while
Off uses the decoder's reported levels. Other compatibility checks still apply.
Existing saved numeric levels become On; a saved Off stays Off.

## Schedule and manual builds

The **Σ Player Daily** workflow runs every day at 15:37 UTC:
08:37 Pacific during daylight saving time and 07:37 during standard time.
GitHub can delay scheduled jobs. The workflow must stay on the default branch,
`main`. It can also be started from Actions → Σ Player Daily →
Run workflow, selecting `main`. Leave **Force build** unchecked to use the same
change check, or check it to compile and publish even when nothing changed.

Each run uses GitHub's branch-merge API to merge the exact current
`Silo-Server/silo-android` `main` commit into this fork's `main`. The explicit
source is important because the fork's immediate parent is `edrock200/silo-android`;
GitHub's ordinary fork-sync API would follow that parent instead. The merge
preserves the fork's commits and fails on conflicts, without resetting
or force-pushing the branch. After syncing, it compares the merged source's Git
tree (all tracked file contents) with the source tag of the most recently
published complete SigmaStreams release. Matching contents skip compilation
and publishing, even if commit history changed. The daily sync still completes,
and the run summary explains the decision. Drafts, prereleases and releases
missing either APK or the verification files do not advance this baseline.
Failed builds therefore retry on the next daily run until those changes ship.
Changes in this fork also trigger a build, even when upstream is unchanged.
API errors fail the check instead of silently skipping it. This comparison
includes documentation and workflow files as well as app code.

When a build is needed, it reserves the dated tag while that commit is the
head of `main`, then checks out the exact tagged commit and runs
release unit tests and lint, and builds both APKs with JDK 21 and R8 optimization.
The inherited Google Play and Discord workflows are disabled in the fork's
Actions settings; their source files stay unchanged to reduce merge conflicts.
The fork workflow never invokes Play publishing or Discord posting.

Each dated release includes:

- `sigmastreams-player-phone.apk`: universal phone/tablet build.
- `sigmastreams-player-tv.apk`: universal Android TV / Google TV build.
- `build-info.json`: exact source SHA, checked upstream SHA, timestamp, version
  code base, and workflow run counter.
- `SHA256SUMS`: checksums covering both APKs and the provenance file.

Each successful daily build is published as a regular GitHub release and
explicitly marked **Latest**. These permanent links follow that release:

- [Latest phone APK](https://github.com/SigmaStreams/silo-android/releases/latest/download/sigmastreams-player-phone.apk)
- [Latest TV APK](https://github.com/SigmaStreams/silo-android/releases/latest/download/sigmastreams-player-tv.apk)

The APKs are optimized release builds. Nothing is published until signature checks pass and downloaded
release assets match the locally calculated checksums. A failed run leaves the
previous public releases intact. A failed upload can leave an unpublished draft;
rerunning the failed publish job completes it without replacing a public release.
Published tags and assets are never overwritten by this workflow.

## Persistent signing

Repository Actions secrets:

- `SILO_RELEASE_KEYSTORE_B64`: base64-encoded private signing keystore.
- `SILO_RELEASE_KEYSTORE_PASSWORD`: keystore password.
- `SILO_RELEASE_KEY_ALIAS`: signing alias.
- `SILO_RELEASE_KEY_PASSWORD`: optional separate key password; defaults to the
  keystore password.
- `SILO_GOOGLE_SERVICES_JSON_B64`: optional Firebase configuration. Without it,
  phone push notifications are unavailable; the rest of the app still builds.

The first three secrets are required before compilation starts. Daily upstream
synchronization and the change check do not depend on signing secrets.
The key must remain the same for future APKs to install as updates. Keep a
private backup of the key and passwords outside Git. Signing material is decoded
only on the temporary build runner and removed after the build. The public
certificate fingerprint can be checked with `apksigner verify --print-certs`.

The existing application/package IDs remain unchanged for protocol compatibility.
An official or locally debug-signed APK uses a different signing identity and
must be uninstalled before installing this fork; that clears the app's local data.
Later daily builds signed with the SigmaStreams key update in place.

The APK version, in-app version label, and GitHub release title preserve Silo's
version and build number, then append the Sigma build date:
`1.0.0 (26) (sigma:10212026)`. The date is **MMDDYYYY in Pacific time** and is
fixed when the workflow reserves its tag, even if compilation crosses midnight.
Multiple builds on the same day share this visible date.

The base version comes from the official Silo build tag with the highest
repository-wide build number included in the checked upstream snapshot, such as
`v1.0.0-beta.26`. Tags are fetched into a separate namespace; fork tags and newer
upstream tags outside that snapshot cannot change its version. Main can contain
changes after that tagged release, so `build-info.json` and the release notes
retain both the base tag and exact checked source SHAs. A missing official build
tag stops publication rather than inventing a version. The upstream build number
is also preserved in the client build header reported to Silo.

Android's internal version codes still use elapsed UTC seconds since 2026 plus a
fork-specific base, remaining monotonic even if the workflow run counter resets.
They control update ordering independently of the visible date. Phone and TV
retain distinct version codes. The workflow counter remains in provenance and
the unique `daily-YYYY-MM-DD.RUN` Git tag used for publication and recovery;
previously published releases are unchanged.

## Branding sources

The app is named **Σ Player**. Accessibility descriptions and HTTP client-name
headers use **Sigma Player** so screen readers pronounce the name clearly and
network headers remain ASCII. The mark is an original Greek uppercase sigma,
using Silo's blue (`#0034FB`), pink (`#F50B4F`), and orange (`#FA7604`) on the
original deep blue icon field (`#010D9F`). It retains the upstream color scheme
and mark-plus-name layout without incorporating Silo's logo or wordmark.

The editable sources are `branding/sigma-mark.svg` and
`branding/sigma-wordmark.svg`. Regenerate the checked-in PNGs with
`python3 scripts/generate-sigma-branding.py` (requires `rsvg-convert`, Pillow,
and DejaVu Sans Bold). The in-app wordmark has a transparent background.
Android's adaptive launcher insets the transparent sigma mark; the 320×180 TV
banner centers a 170-pixel-wide wordmark inside Fire TV's square crop.
Resource IDs and Kotlin symbol names remain stable to reduce merge conflicts.
The original Sigma Player artwork is licensed under AGPL-3.0-or-later.

APK asset filenames retain `sigmastreams-player-` so existing permanent download
links continue to work. The repository owner and persistent signing key stay the
same; the displayed app and release names are Σ Player.

The local `unbranded` branch restores the original Silo name, artwork, notices,
and logo sizing while retaining the fork's playback and release tooling.
It is prepared for use after written trademark permission is received.

## Failures and maintenance

- Merge conflict: fetch upstream and resolve it locally on a branch, review the
  retained fork behavior, and merge the fix into `main`. Never resolve by
  discarding the fork commits. Start a new daily workflow after resolving it.
- Failed test, lint, or build: inspect the failing job, fix the source, and start
  a new run. The sync may already have updated `main`; a merge is not evidence
  that a release was built successfully. A reserved tag can exist without a
  published release after a failed build; leave it in place and start a new run.
- Failed upload: use Re-run failed jobs. Draft assets can be replaced while the
  draft is unpublished; public releases stay immutable.
- Disabled schedule: re-enable the workflow in Actions. GitHub can disable
  scheduled workflows after 60 days without repository activity.
- Missing Firebase setup: configure your own Firebase app if phone push is
  needed. Do not copy another project's private service credentials.
- Re-run the checks after editing the workflow:
  `python3 scripts/test-fork-release.py`, `scripts/check-build-supply-chain.sh`,
  and `actionlint .github/workflows/fork-daily-release.yml` when available.

No personal access token is stored by this automation. The built-in repository
`GITHUB_TOKEN` performs fork synchronization and release publishing; signing
secrets are supplied only to the build job. GitHub suppresses follow-on push
workflows for changes made with this token, so the daily workflow performs its
own validation rather than depending on a second CI run.

Tag reservation avoids GitHub's workflow-scope guard when `main` advances during
compilation. Publication requires the existing tag to match the tested source;
it never retargets a built APK to whatever happens to be on `main` later.
The release call uses `--verify-tag` and omits `--target`, which is ignored for
existing tags but can still trigger GitHub's workflow-file permission guard.
