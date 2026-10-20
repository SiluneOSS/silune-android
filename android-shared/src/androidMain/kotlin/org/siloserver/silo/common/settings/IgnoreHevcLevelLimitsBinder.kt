package org.siloserver.silo.common.settings

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch
import org.siloserver.silo.common.player.MediaCodecCapabilitiesProbe

/**
 * Mirrors the active profile's HEVC level-limit preference into
 * [MediaCodecCapabilitiesProbe], the single source every capability report
 * (playback, downloads, diagnostics) reads, so no call site needs the setting
 * threaded through it.
 */
object IgnoreHevcLevelLimitsBinder {
    fun start(scope: CoroutineScope, store: PlayerSettingsStore) {
        scope.launch {
            store.ignoreHevcLevelLimitsFlow.distinctUntilChanged().collect { enabled ->
                MediaCodecCapabilitiesProbe.ignoreHevcLevelLimits = enabled
            }
        }
    }
}
