#!/usr/bin/env python3
"""Fail an upstream merge if it changes night mode or disconnects its controls."""
import argparse
import hashlib
from pathlib import Path
import re
import sys

COMMON = "android-shared/src/androidMain/kotlin/org/siloserver/silo/common/"
PHONE = "androidApp/src/androidMain/kotlin/org/siloserver/silo/android/"
TV = "androidTvApp/src/androidMain/kotlin/org/siloserver/silo/tv/"

# These fork-owned files contain the Plezy parameters, fallback, resource
# lifecycle, PCM gating and renderer transition. Logic changes require review
# and an intentional fingerprint update; formatting and comments may change.
SOURCE_HASHES = {
    COMMON + "player/audio/AudioNormalizationEffect.kt": "7825aa314117abcb5903e6162ce67f292cc8d12019c0436061ffd3983ae23cd0",
    COMMON + "player/audio/AudioNormalizationController.kt": "14e0309df12317cdb16364aba9f86245d196dbd527452077aefc58ad72fe5c60",
}
REQUIRED = {
    COMMON + "player/SiloPlayerFactory.kt": [
        "audioNormalization.requiresPcm(format) ||",
        "audioNormalization.bind(player)",
        "audioNormalization.unbind(player)",
        "player.trackSelectionParameters = audioNormalization.outputParameters(next)",
    ],
    COMMON + "player/SiloPlaybackService.kt": [
        "playerSettingsStore.audioNormalizationEnabledFlow.distinctUntilChanged().collect(audioNormalization::setEnabled)",
    ],
    COMMON + "di/PlayerModule.kt": ["single { org.siloserver.silo.common.player.audio.AudioNormalizationController() }"],
    COMMON + "settings/PlayerSettingsStore.kt": [
        "val audioNormalizationEnabledFlow: Flow<Boolean>",
        "suspend fun setAudioNormalizationEnabled(value: Boolean)",
    ],
    COMMON + "settings/AndroidPlayerSettingsStore.kt": [
        "override val audioNormalizationEnabledFlow: Flow<Boolean> = profileScopedFlow(false) { p, s -> p.boolFor(s, AUDIO_NORMALIZATION_ENABLED, false) }",
        "override suspend fun setAudioNormalizationEnabled(value: Boolean) = writeBoolLocal(AUDIO_NORMALIZATION_ENABLED, value)",
        'const val AUDIO_NORMALIZATION_ENABLED = "audio_normalization_enabled"',
        "it.remove(booleanPreferencesKey(scope.keyPrefix + AUDIO_NORMALIZATION_ENABLED))",
    ],
    PHONE + "di/AndroidModule.kt": ["playbackAnalytics = get(), audioNormalization = get(),"],
    TV + "di/AndroidTvModule.kt": ["playbackAnalytics = get(), audioNormalization = get(),"],
    PHONE + "ui/screens/player/PlayerViewModel.kt": [
        "val audioNormalizationEnabled: StateFlow<Boolean> = playerSettingsStore.audioNormalizationEnabledFlow.stateIn(viewModelScope, SharingStarted.Eagerly, false)",
        "fun setAudioNormalizationEnabled(value: Boolean) { viewModelScope.launch { playerSettingsStore.setAudioNormalizationEnabled(value) } }",
    ],
    TV + "ui/screens/player/TvPlayerViewModel.kt": [
        "val audioNormalizationEnabled: StateFlow<Boolean> = playerSettingsStore.audioNormalizationEnabledFlow.stateIn(viewModelScope, SharingStarted.Eagerly, false)",
        "fun setAudioNormalizationEnabled(value: Boolean) { viewModelScope.launch { playerSettingsStore.setAudioNormalizationEnabled(value) } }",
    ],
    PHONE + "ui/screens/player/PlayerOverlay.kt": [
        "audioNormalizationEnabled = viewModel.audioNormalizationEnabled.collectAsState().value, onSetAudioNormalizationEnabled = viewModel::setAudioNormalizationEnabled,",
    ],
    PHONE + "ui/screens/player/PlayerSettingsSheet.kt": [
        'PlayerSwitchRow(label = "Night mode", checked = audioNormalizationEnabled, onCheckedChange = onSetAudioNormalizationEnabled, separator = true,)',
    ],
    TV + "ui/screens/player/TvPlayerScreen.kt": [
        "val audioNormalizationEnabled by viewModel.audioNormalizationEnabled.collectAsState()",
        "audioNormalizationEnabled = audioNormalizationEnabled, onAudioNormalizationChanged = viewModel::setAudioNormalizationEnabled,",
    ],
    TV + "ui/screens/player/TvPlayerHud.kt": [
        "audioNormalizationEnabled = audioNormalizationEnabled, onAudioNormalizationChanged = onAudioNormalizationChanged,",
        '''HudFocusedSettingRow(label = "Night mode", value = onOffLabel(audioNormalizationEnabled),
            enabled = enabled, showsChevron = false,
            entryFocusRequester = entryFocusRequester.takeIf { !trackSelectable },
            onActivate = { onAudioNormalizationChanged(!audioNormalizationEnabled) },)''',
    ],
}


def compact(source):
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    return re.sub(r"\s+", "", source)


def check(root):
    failures = []
    for relative, expected in SOURCE_HASHES.items():
        path = root / relative
        actual = hashlib.sha256(compact(path.read_text()).encode()).hexdigest() if path.is_file() else None
        if actual != expected:
            failures.append(relative + ": night mode implementation changed")
    for relative, fragments in REQUIRED.items():
        path = root / relative
        source = compact(path.read_text()) if path.is_file() else ""
        for fragment in fragments:
            if compact(fragment) not in source:
                failures.append(relative + ": " + fragment.splitlines()[0])
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    failures = check(parser.parse_args().root)
    if failures:
        print("Night mode changed; review the upstream merge before updating main:", file=sys.stderr)
        for failure in failures:
            print("  " + failure, file=sys.stderr)
        return 1
    print("Night mode effects, playback integration, saved setting and phone/TV toggles are intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
