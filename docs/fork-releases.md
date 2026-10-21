# Silune daily releases

**Silune — your media, after dark.**

Silune is an unofficial fork of the Silo Android phone and TV clients. Its
fork changes are an OLED-focused visual identity and an HEVC compatibility
patch for NVIDIA Shield setups. The rest of the client feature set comes
from Silo.

The visual identity uses a purple split-prism mark, charcoal launcher
backgrounds, and matching wordmarks and TV artwork. The playback patch is
**Ignore HEVC Level Limits**, an On/Off switch enabled by default. On removes
HEVC level bounds from capability reports; Off uses the decoder's reported
levels. Other compatibility checks still apply. This does not increase the
hardware decoder's actual capabilities. Existing saved numeric levels become
On; a saved Off stays Off.

The release workflow publishes optimized, signed phone and TV APKs on
[GitHub Releases](https://github.com/SiluneOSS/silune-android/releases).

## Schedule and manual builds

The **Silune Daily** workflow runs every day at 15:37 UTC:
08:37 Pacific during daylight saving time and 07:37 during standard time.
GitHub can delay scheduled jobs. The workflow must stay on the default branch,
`main`. It can also be started from Actions → Silune Daily →
Run workflow, selecting `main`. Leave **Force build** unchecked to use the same
change check, or check it to compile and publish even when nothing changed.

Each run uses GitHub's branch-merge API to merge the exact current
`Silo-Server/silo-android` `main` commit into `SiluneOSS/silune-android` `main`.
The repository is a direct fork of official Silo Android. This API merge requires
both repositories to share a GitHub fork network. The merge preserves the fork's
commits and fails on conflicts, without resetting
or force-pushing the branch. After syncing, it compares the merged source's Git
tree (all tracked file contents) with the source tag of the most recently
published complete Silune release. Matching contents skip compilation
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

- `silune-phone.apk`: universal phone/tablet build.
- `silune-tv.apk`: universal Android TV / Google TV build.
- `build-info.json`: exact source SHA, checked upstream SHA, timestamp, version
  code base, and workflow run counter.
- `SHA256SUMS`: checksums covering both APKs and the provenance file.

Each successful daily build is published as a regular GitHub release and
explicitly marked **Latest**. These permanent links follow that release:

- [Latest phone APK](https://github.com/SiluneOSS/silune-android/releases/latest/download/silune-phone.apk)
- [Latest TV APK](https://github.com/SiluneOSS/silune-android/releases/latest/download/silune-tv.apk)

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

Both apps use the Silune application ID `org.silune.app`, so they install
separately from Silo and earlier forks with different application IDs. Later
Silune builds signed with the same persistent release key update in place.

The APK version, in-app version label, and GitHub release title preserve Silo's
version and build number, then append the Silune build date:
`1.0.0 (26) (silune:10212026)`. The date is **MMDDYYYY in Pacific time** and is
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

The app, accessibility descriptions, and HTTP client-name headers use **Silune**
(**Silune TV** for TV client headers). The mark uses two angular purple forms
separated by a diagonal cut, with three facets on the upper form. Violet
(`#5736B4`), lavender (`#B59AF4`), and muted purple (`#6856A3`) sit on a
charcoal (`#25252D`) launcher background. The wordmark pairs the mark with
white lettering; the brand line is "Your media, after dark."

The editable sources are `branding/silune-mark.svg` and
`branding/silune-wordmark.svg`. Regenerate the checked-in PNGs and startup videos
with `python3 scripts/generate-silune-branding.py` (requires `rsvg-convert`,
Pillow, and FFmpeg with `libx264`).
The DejaVu Sans Bold lettering is outlined for consistent rendering.
The in-app wordmark has a transparent background.
Android's adaptive launcher insets the transparent split-prism mark; the 320×180 TV
banner centers a 170-pixel-wide wordmark inside Fire TV's square crop.
Phone and TV share a 1.6-second Silune wordmark fade on pure black at cold launch.
The videos retain the 720p30 AVC 3.1 and 1080p60 AVC 4.2 decoder tiers.
Resource IDs and Kotlin symbol names remain stable to reduce merge conflicts.
The Silune artwork is licensed under AGPL-3.0-or-later.

New releases use `silune-phone.apk` and `silune-tv.apk`. Permanent download URLs
use those filenames once a Silune release is published. Previously published
releases retain their original asset names; existing links using `prism-*`
or earlier filenames will not follow new Silune releases. The repository is now
`SiluneOSS/silune-android`; the persistent signing key is retained. Builds with
the same application ID and signing key update in place with the matching phone
or TV build.

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
