package org.siloserver.silo.common.player.audio

import android.os.Looper
import androidx.media3.common.C
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.common.Player
import androidx.media3.common.Timeline
import androidx.media3.common.TrackGroup
import androidx.media3.common.TrackSelectionParameters.AudioOffloadPreferences
import androidx.media3.common.Tracks
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.analytics.AnalyticsListener
import androidx.media3.exoplayer.audio.AudioSink
import androidx.media3.exoplayer.trackselection.DefaultTrackSelector
import androidx.media3.test.utils.FakeClock
import androidx.media3.test.utils.FakeMediaSource
import androidx.media3.test.utils.FakeRenderer
import androidx.media3.test.utils.FakeTimeline
import androidx.media3.test.utils.TestExoPlayerBuilder
import androidx.media3.test.utils.robolectric.TestPlayerRunHelper
import androidx.test.core.app.ApplicationProvider
import java.util.concurrent.TimeUnit
import org.robolectric.Shadows.shadowOf
import java.lang.reflect.Proxy
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@UnstableApi
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class AudioNormalizationControllerTest {
    private val eventTime = AnalyticsListener.EventTime(
        0, Timeline.EMPTY, 0, null, 0, Timeline.EMPTY, 0, null, 0, 0,
    )
    private val offload = AudioOffloadPreferences.Builder()
        .setAudioOffloadMode(AudioOffloadPreferences.AUDIO_OFFLOAD_MODE_ENABLED)
        .build()
    private fun parameters(tunneling: Boolean = true) = DefaultTrackSelector.Parameters.Builder()
        .setTunnelingEnabled(tunneling)
        .setAudioOffloadPreferences(offload)
        .setPreferredTextLanguage("fr")
        .build()

    @Test
    fun normalizationBlocksEncodedBypassButKeepsPcmPlayable() {
        val controller = AudioNormalizationController()
        val delegate = Proxy.newProxyInstance(AudioSink::class.java.classLoader, arrayOf(AudioSink::class.java)) {
                _, method, _ ->
            when (method.name) {
                "getFormatSupport" -> AudioSink.SINK_FORMAT_SUPPORTED_DIRECTLY
                else -> null
            }
        } as AudioSink
        val sink = PassthroughSuppressingAudioSink(delegate, controller::requiresPcm)
        val encoded = Format.Builder().setSampleMimeType(MimeTypes.AUDIO_E_AC3).build()
        val pcm = Format.Builder().setSampleMimeType(MimeTypes.AUDIO_RAW).setPcmEncoding(C.ENCODING_PCM_16BIT).build()
        assertTrue(sink.supportsFormat(encoded))
        controller.setEnabled(true)
        assertFalse(sink.supportsFormat(encoded))
        assertTrue(sink.supportsFormat(pcm))
        controller.setEnabled(false)
        assertTrue(sink.supportsFormat(encoded))
    }

    @Test
    fun capabilityUpdatesCannotReenableTunnelingOrOffloadWhileNormalizing() {
        val controller = AudioNormalizationController()
        val player = RecordingPlayer(parameters())
        controller.bind(player.proxy)
        controller.setEnabled(true)
        assertFalse(player.parameters.tunnelingEnabled)
        assertEquals(AudioOffloadPreferences.AUDIO_OFFLOAD_MODE_DISABLED, player.parameters.audioOffloadPreferences.audioOffloadMode)
        player.parameters = controller.outputParameters(parameters(tunneling = false))
        assertFalse(player.parameters.tunnelingEnabled)
        assertEquals(AudioOffloadPreferences.AUDIO_OFFLOAD_MODE_DISABLED, player.parameters.audioOffloadPreferences.audioOffloadMode)
        controller.setEnabled(false)
        assertFalse(player.parameters.tunnelingEnabled, "Restore the latest HDMI/device policy")
        assertEquals(offload, player.parameters.audioOffloadPreferences)
        assertEquals(parameters().preferredTextLanguages, player.parameters.preferredTextLanguages)
        controller.unbind(player.proxy)
    }

    @Test
    fun changingModeDuringPlaybackWaitsForAudioDisabledAndKeepsTheLatestToggle() {
        val controller = AudioNormalizationController()
        val player = RecordingPlayer(parameters())
        player.tracks = Tracks(listOf(Tracks.Group(
            TrackGroup(Format.Builder().setSampleMimeType(MimeTypes.AUDIO_AC3).build()),
            false, intArrayOf(C.FORMAT_HANDLED), booleanArrayOf(true),
        )))
        controller.bind(player.proxy)
        controller.setEnabled(true)
        assertTrue(player.parameters.disabledTrackTypes.contains(C.TRACK_TYPE_AUDIO))
        controller.setEnabled(false)
        assertTrue(player.parameters.disabledTrackTypes.contains(C.TRACK_TYPE_AUDIO))
        player.tracks = Tracks.EMPTY
        controller.onTracksChanged(eventTime, player.tracks)
        assertFalse(player.parameters.disabledTrackTypes.contains(C.TRACK_TYPE_AUDIO))
        assertTrue(player.parameters.tunnelingEnabled)
        assertEquals(offload, player.parameters.audioOffloadPreferences)
        assertEquals(parameters().preferredTextLanguages, player.parameters.preferredTextLanguages)
        assertTrue(player.otherCalls.isEmpty(), "Do not seek, stop, prepare, or alter pause intent")
        controller.unbind(player.proxy)
        val changes = player.changes
        controller.onTracksChanged(eventTime, Tracks.EMPTY)
        assertEquals(changes, player.changes)
    }

    @Test
    fun missingTrackCallbackCannotLeaveAudioPermanentlyDisabled() {
        val controller = AudioNormalizationController()
        val player = RecordingPlayer(parameters())
        player.tracks = Tracks(listOf(Tracks.Group(
            TrackGroup(Format.Builder().setSampleMimeType(MimeTypes.AUDIO_AC3).build()),
            false, intArrayOf(C.FORMAT_HANDLED), booleanArrayOf(true),
        )))
        controller.bind(player.proxy)
        controller.setEnabled(true)
        assertTrue(player.parameters.disabledTrackTypes.contains(C.TRACK_TYPE_AUDIO))
        shadowOf(Looper.getMainLooper()).idleFor(1, TimeUnit.SECONDS)
        assertFalse(player.parameters.disabledTrackTypes.contains(C.TRACK_TYPE_AUDIO))
        assertFalse(player.parameters.tunnelingEnabled)
        controller.unbind(player.proxy)
    }

    @Test
    fun realExoPlayerReinitializesAudioAndRetainsPauseIntent() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val selector = DefaultTrackSelector(context)
        selector.parameters = parameters()
        val renderer = FakeRenderer(C.TRACK_TYPE_AUDIO)
        val player = TestExoPlayerBuilder(context)
            .setTrackSelector(selector)
            .setRenderers(renderer)
            .setClock(FakeClock(true))
            .build()
        val controller = AudioNormalizationController()
        try {
            controller.bind(player)
            player.setMediaSource(FakeMediaSource(
                FakeTimeline(1),
                Format.Builder().setSampleMimeType(MimeTypes.AUDIO_AAC)
                    .setSampleRate(48_000).setChannelCount(2).build(),
            ))
            player.prepare()
            TestPlayerRunHelper.runUntilPlaybackState(player, Player.STATE_READY)
            assertTrue(player.currentTracks.isTypeSelected(C.TRACK_TYPE_AUDIO))
            val position = player.currentPosition
            val initialEnables = renderer.enabledCount

            controller.setEnabled(true)
            repeat(2) { TestPlayerRunHelper.runUntilPendingCommandsAreFullyHandled(player) }
            assertTrue(renderer.enabledCount > initialEnables, "The actual renderer must re-evaluate sink support")
            assertTrue(player.currentTracks.isTypeSelected(C.TRACK_TYPE_AUDIO))
            assertFalse(player.trackSelectionParameters.disabledTrackTypes.contains(C.TRACK_TYPE_AUDIO))
            assertFalse(selector.parameters.tunnelingEnabled)
            assertEquals(AudioOffloadPreferences.AUDIO_OFFLOAD_MODE_DISABLED,
                player.trackSelectionParameters.audioOffloadPreferences.audioOffloadMode)
            assertEquals(position, player.currentPosition)
            assertFalse(player.playWhenReady)

            controller.setEnabled(false)
            repeat(2) { TestPlayerRunHelper.runUntilPendingCommandsAreFullyHandled(player) }
            assertTrue(player.currentTracks.isTypeSelected(C.TRACK_TYPE_AUDIO))
            assertTrue(selector.parameters.tunnelingEnabled)
            assertEquals(offload, player.trackSelectionParameters.audioOffloadPreferences)
            assertEquals(position, player.currentPosition)
            assertFalse(player.playWhenReady)
        } finally {
            controller.unbind(player)
            player.release()
        }
    }

    private class RecordingPlayer(var parameters: DefaultTrackSelector.Parameters) {
        var tracks = Tracks.EMPTY
        var changes = 0
        val otherCalls = mutableListOf<String>()
        val proxy = Proxy.newProxyInstance(ExoPlayer::class.java.classLoader, arrayOf(ExoPlayer::class.java)) {
                _, method, args ->
            when (method.name) {
                "getTrackSelectionParameters" -> parameters
                "setTrackSelectionParameters" -> {
                    parameters = args!![0] as DefaultTrackSelector.Parameters
                    changes++
                    null
                }
                "getApplicationLooper" -> Looper.getMainLooper()
                "getCurrentTracks" -> tracks
                "addAnalyticsListener", "removeAnalyticsListener" -> null
                else -> {
                    otherCalls += method.name
                    null
                }
            }
        } as ExoPlayer
    }
}
