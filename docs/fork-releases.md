# SigmaStreams Player daily releases

The fork publishes optimized, signed phone and TV APKs on
[GitHub Releases](https://github.com/SigmaStreams/silo-android/releases).
These are unofficial builds of the Silo Android clients, with SigmaStreams
branding and the fork's HEVC level override defaulting to 6.2.

## Schedule and manual builds

The **SigmaStreams Player Daily** workflow runs every day at 15:37 UTC:
08:37 Pacific during daylight saving time and 07:37 during standard time.
GitHub can delay scheduled jobs. The workflow must stay on the default branch,
`main`. It can also be started from Actions → SigmaStreams Player Daily →
Run workflow, selecting `main`.

Each run uses GitHub's branch-merge API to merge the exact current
`Silo-Server/silo-android` `main` commit into this fork's `main`. The explicit
source is important because the fork's immediate parent is `edrock200/silo-android`;
GitHub's ordinary fork-sync API would follow that parent instead. The merge
preserves the fork's commits and fails on conflicts, without resetting
or force-pushing the branch. It reserves the dated tag while that commit is the
head of `main`, then checks out the exact tagged commit and runs
release unit tests and lint, and builds both APKs with JDK 21 and R8 optimization.
The inherited Google Play and Discord workflows are disabled in the fork's
Actions settings; their source files stay unchanged to reduce merge conflicts.
The fork workflow never invokes Play publishing or Discord posting.

Each dated prerelease includes:

- `sigmastreams-player-phone.apk`: universal phone/tablet build.
- `sigmastreams-player-tv.apk`: universal Android TV / Google TV build.
- `build-info.json`: exact source SHA, checked upstream SHA, timestamp, version
  code base, and workflow run counter.
- `SHA256SUMS`: checksums covering both APKs and the provenance file.

The APKs are release builds even though GitHub labels the daily builds as
prereleases. Nothing is published until signature checks pass and downloaded
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

The first three secrets are required before upstream synchronization starts.
The key must remain the same for future APKs to install as updates. Keep a
private backup of the key and passwords outside Git. Signing material is decoded
only on the temporary build runner and removed after the build. The public
certificate fingerprint can be checked with `apksigner verify --print-certs`.

The existing application/package IDs remain unchanged for protocol compatibility.
An official or locally debug-signed APK uses a different signing identity and
must be uninstalled before installing this fork; that clears the app's local data.
Later daily builds signed with the SigmaStreams key update in place.

Version codes use elapsed UTC seconds since 2026 plus a fork-specific base,
remaining monotonic even if GitHub's workflow run counter resets. The full run
counter appears in the version name and provenance. The upstream About-row build
field has a 999 limit, so that display field cycles through 1..999; it does not
control Android update ordering. Phone and TV retain distinct version codes.

## Branding sources

The launcher icons reuse the approved SigmaStreams glossy appearance v2 assets.
The in-app wordmark uses a transparent-background derivative of the glossy
wordmark so it blends into login and header surfaces. Android's adaptive launcher
applies an inset around the transparent emblem so device icon masks do not clip it. The TV
banner centers a 170-pixel-wide wordmark on a 320×180 dark field so it also fits
Fire TV's centered square crop. Original upstream brand
assets are replaced. Resource IDs and Kotlin symbol names remain stable to
reduce conflicts; those identifiers are not the displayed app identity.

The original files are maintained outside this repository under the SigmaStreams
Operations branding collection. Builds require only the checked-in copies.
The AGPL source license and third-party notices are preserved; SigmaStreams
artwork does not grant a separate trademark or artwork license.

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
