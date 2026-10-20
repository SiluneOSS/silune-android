package org.siloserver.silo.common.settings

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch
import org.siloserver.silo.common.player.MediaCodecCapabilitiesProbe

/**
 * Mirrors the active profile's HEVC level override into
 * [MediaCodecCapabilitiesProbe], the single source every capability report
 * (playback, downloads, diagnostics) reads, so no call site needs the setting
 * threaded through it.
 */
object HevcLevelOverrideBinder {
    fun start(scope: CoroutineScope, store: PlayerSettingsStore) {
        scope.launch {
            store.hevcLevelOverrideFlow.distinctUntilChanged().collect { level ->
                MediaCodecCapabilitiesProbe.hevcLevelOverride = level
            }
        }
    }
}
