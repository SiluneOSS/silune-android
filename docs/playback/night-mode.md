# Night mode

Night mode reduces the difference between quiet dialogue and loud scenes.
On phone and TV, toggle **Night mode** in Settings → Playback → Audio.
During playback, use the phone player's Settings → Audio & subtitles or the
TV player's Audio pane. Each device's settings and player controls use the
same saved preference. It defaults off and is saved locally for the
active server and profile on this device. It applies to local playback;
Cast receivers control their own audio.

The implementation follows [Plezy's Android audio effect](https://github.com/edde746/plezy/blob/cd0a2dff560d95410eb3896c4239d276568af66d/android/app/src/main/kotlin/com/edde746/plezy/exoplayer/AudioNormalizationEffect.kt).
`AudioNormalizationEffect.kt` is adapted from that GPL-3.0 source with attribution.
It uses the same Android platform effects and tuning:

- Android 9/API 28 and later: `DynamicsProcessing` with one full-range compressor
  band, 30 ms attack, 300 ms release, 4:1 ratio, −34 dB threshold, 6 dB knee,
  and +15 dB makeup gain. The linked limiter uses 1 ms attack, 60 ms release,
  10:1 ratio, and a −3 dB threshold. Preferred frame duration is 10 ms.
- Android 7–8/API 24–27, or devices without `DynamicsProcessing`:
  `LoudnessEnhancer` with +9 dB gain and the platform's built-in limiting.
- Devices supporting neither effect continue playback and log the failure.
  The saved toggle records the user's preference, not proof of device support.

Plezy 2.24.0 also uses these platform effects with its Android mpv backend,
through `audiotrack-normalize`; see its [versioned player implementation](https://github.com/edde746/plezy/blob/2.24.0/lib/mpv/player/player_base.dart#L1384).
Choosing mpv on Android therefore uses the same effect approach.

This is Plezy's Android approximation of its mpv loudness filter, rather than
an integrated LUFS measurement or an FFmpeg filter. The fallback provides a
fixed boost with limiting and has less control over dynamic range.

Audio effects require decoded PCM. While enabled, night mode blocks encoded
passthrough, audio offload, and tunneling; a receiver consequently loses the
original encoded surround/Atmos bitstream. Channel count is preserved when the
local decoder and output support it. Switching the setting briefly disables
and re-enables the audio renderer after the playback thread acknowledges the
change, as Plezy does. Video, playback position, and pause intent are retained.
Turning it off restores the latest output preferences, subject to the existing
codec and device guards.

The player checks that the platform accepted enablement and reports the effect
as enabled before logging a successful attachment. Logcat also records whether
the actual output is PCM, tunneled, or offloaded. These checks confirm the
configured path, not the audible result on a particular device.

The effect follows the actual AudioTrack session and output channel count,
including HDMI route changes and stereo/multichannel switches, and is released
with the player. The setting is client-local and is never sent as an unknown
server settings key.

## Upstream guard

`scripts/check-night-mode.py` protects the audio effect and controller logic,
including Plezy's parameters, fallback, session cleanup, PCM gating, tunneling
and offload restrictions. It checks saved-setting and player integration on
phone and TV. The daily sync runs it before pushing a merge; failures leave the
remote branch unchanged. Intentional logic changes require review and an
updated source fingerprint. Run `python3 scripts/test-check-night-mode.py`
after updating the guard.

## Device validation

Use release builds of both apps. With a running server, verify quiet dialogue
and loud passages with night mode off and on, then switch audio tracks, seek,
pause, resume, and play the next episode. Check stereo and multichannel output,
HDMI and Bluetooth route changes, and an initial passthrough/tunneled TV stream.
Confirm the receiver switches to decoded PCM and returns to its usual output
when night mode is off. Exercise the fallback on API 24–27 or a device without
the dynamics effect. Logcat tag `AudioNormalization` reports the effect used.

## NVIDIA Shield TV Pro 2019 qualification

This device has not yet been hardware-verified for this feature. Run the signed
TV release with the same dialogue/action passage twice, first off and then on.
Start with the Shield's own volume processing disabled so it does not mask the
comparison. Repeat with a track that normally uses passthrough and one that
already decodes to PCM.

With night mode on, check `adb logcat -s AudioNormalization` for decoded output,
`tunneling=false`, `offload=false`, and a successful effect attachment. Check
which engine attached: `DynamicsProcessing` provides the configured compressor
and limiter; the `LoudnessEnhancer` fallback provides boost and limiting. A
successful attachment alone is not proof that the Shield's HDMI path applies
the effect audibly. Compare quiet dialogue and loud effects at a fixed receiver
volume, including seeks and an audio-track change. With night mode off, verify
that normal audio routing returns. Keep the device unqualified until both the
runtime logs and listening comparison pass.
