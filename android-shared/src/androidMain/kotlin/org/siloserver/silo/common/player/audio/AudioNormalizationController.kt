package org.siloserver.silo.common.player.audio

import android.os.Handler
import android.util.Log
import androidx.media3.common.C
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.common.Player
import androidx.media3.common.TrackSelectionParameters.AudioOffloadPreferences
import androidx.media3.common.Tracks
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.analytics.AnalyticsListener
import androidx.media3.exoplayer.audio.AudioSink
import androidx.media3.exoplayer.trackselection.DefaultTrackSelector

/** Owns the session effect and keeps normalization on decoded, non-tunneled PCM. */
@UnstableApi
class AudioNormalizationController : AnalyticsListener {
    @Volatile
    var enabled: Boolean = false
        private set

    private val effect = AudioNormalizationEffect { level, _, message ->
        if (level == "warn") Log.w(TAG, message) else Log.i(TAG, message)
    }
    private var player: ExoPlayer? = null
    private var preferredTunneling = false
    private var preferredOffload = AudioOffloadPreferences.DEFAULT
    private var outputChannels: Int? = null
    private var pcmOutput = false
    private var restoringAudio = false
    private var handler: Handler? = null
    private val restoreAudioTimeout = Runnable { restoreAudio() }

    fun bind(player: ExoPlayer) {
        check(this.player == null) { "Normalization already belongs to a player" }
        this.player = player
        handler = Handler(player.applicationLooper)
        player.addAnalyticsListener(this)
        val parameters = player.trackSelectionParameters as DefaultTrackSelector.Parameters
        player.trackSelectionParameters = outputParameters(parameters)
    }

    fun unbind(player: Player) {
        if (this.player !== player) return
        handler?.removeCallbacks(restoreAudioTimeout)
        handler = null
        this.player?.removeAnalyticsListener(this)
        this.player = null
        restoringAudio = false
        pcmOutput = false
        outputChannels = null
        effect.release()
    }

    /** The sink must reject encoded bypass while continuing to accept raw PCM. */
    fun requiresPcm(format: Format): Boolean =
        enabled && MimeTypes.isAudio(format.sampleMimeType) && format.sampleMimeType != MimeTypes.AUDIO_RAW

    /** Re-applied after capability/HDMI changes so presets cannot bypass the effect. */
    fun outputParameters(parameters: DefaultTrackSelector.Parameters): DefaultTrackSelector.Parameters {
        preferredTunneling = parameters.tunnelingEnabled
        preferredOffload = parameters.audioOffloadPreferences
        return constrainedParameters(parameters)
    }

    private fun constrainedParameters(parameters: DefaultTrackSelector.Parameters): DefaultTrackSelector.Parameters =
        parameters.buildUpon()
            .setTunnelingEnabled(preferredTunneling && !enabled)
            .setAudioOffloadPreferences(
                if (enabled) AudioOffloadPreferences.Builder()
                    .setAudioOffloadMode(AudioOffloadPreferences.AUDIO_OFFLOAD_MODE_DISABLED)
                    .build()
                else preferredOffload,
            )
            .build()

    fun setEnabled(enabled: Boolean) {
        if (this.enabled == enabled) return
        this.enabled = enabled
        effect.release()
        val player = player ?: return
        val parameters = player.trackSelectionParameters as DefaultTrackSelector.Parameters
        val next = constrainedParameters(parameters)
        // Sink support is latched by the renderer. A no-op seek or a synchronous
        // disable/enable can keep passthrough alive. Like Plezy, wait until the
        // playback thread confirms audio is disabled before enabling it again.
        // This leaves video, position, pause intent and subtitle selection alone.
        if (!restoringAudio && player.currentTracks.isTypeSelected(C.TRACK_TYPE_AUDIO)) {
            restoringAudio = true
            pcmOutput = false
            player.trackSelectionParameters = next.buildUpon()
                .setTrackTypeDisabled(C.TRACK_TYPE_AUDIO, true)
                .build()
            // Plezy also restores after one second if the track callback is lost.
            handler?.postDelayed(restoreAudioTimeout, 1_000L)
        } else {
            player.trackSelectionParameters = next
        }
    }

    override fun onTracksChanged(eventTime: AnalyticsListener.EventTime, tracks: Tracks) {
        if (!restoringAudio || tracks.isTypeSelected(C.TRACK_TYPE_AUDIO)) return
        restoreAudio()
    }

    private fun restoreAudio() {
        if (!restoringAudio) return
        restoringAudio = false
        handler?.removeCallbacks(restoreAudioTimeout)
        val player = player ?: return
        player.trackSelectionParameters = constrainedParameters(
            player.trackSelectionParameters as DefaultTrackSelector.Parameters,
        ).buildUpon().setTrackTypeDisabled(C.TRACK_TYPE_AUDIO, false).build()
    }

    override fun onAudioTrackInitialized(
        eventTime: AnalyticsListener.EventTime,
        audioTrackConfig: AudioSink.AudioTrackConfig,
    ) {
        pcmOutput = audioTrackConfig.encoding in PCM_ENCODINGS &&
            !audioTrackConfig.tunneling && !audioTrackConfig.offload
        outputChannels = Integer.bitCount(audioTrackConfig.channelConfig).takeIf { it > 0 }
        if (enabled) {
            Log.i(TAG, "Night mode output: encoding=${audioTrackConfig.encoding}, " +
                "channels=$outputChannels, tunneling=${audioTrackConfig.tunneling}, " +
                "offload=${audioTrackConfig.offload}")
        }
        attachEffect()
    }

    override fun onAudioSessionIdChanged(eventTime: AnalyticsListener.EventTime, audioSessionId: Int) {
        attachEffect()
    }

    private fun attachEffect() {
        if (enabled && pcmOutput) {
            effect.attach(player?.audioSessionId ?: C.AUDIO_SESSION_ID_UNSET, outputChannels)
        } else {
            effect.release()
        }
    }

    private companion object {
        const val TAG = "AudioNormalization"
        val PCM_ENCODINGS = setOf(
            C.ENCODING_PCM_8BIT,
            C.ENCODING_PCM_16BIT,
            C.ENCODING_PCM_24BIT,
            C.ENCODING_PCM_32BIT,
            C.ENCODING_PCM_FLOAT,
        )
    }
}
