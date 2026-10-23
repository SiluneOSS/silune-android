package org.siloserver.silo.common.player

import android.app.Activity
import androidx.annotation.OptIn
import androidx.media3.common.text.Cue
import androidx.media3.common.util.UnstableApi
import androidx.media3.ui.SubtitleView
import org.siloserver.silo.model.settings.SubtitleFontSizePreset
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import kotlin.test.Test
import kotlin.test.assertEquals

@OptIn(UnstableApi::class)
@RunWith(RobolectricTestRunner::class)
class AndroidSubtitleTextSizePolicyTest {
    @Test
    fun televisionUsesFixedCouchReadableSpLadder() {
        val expected = mapOf(
            SubtitleFontSizePreset.XSmall to 14f,
            SubtitleFontSizePreset.Small to 18f,
            SubtitleFontSizePreset.Medium to 22f,
            SubtitleFontSizePreset.Large to 26f,
            SubtitleFontSizePreset.XLarge to 32f,
            SubtitleFontSizePreset.XXLarge to 40f,
        )

        expected.forEach { (preset, sp) ->
            assertEquals(
                AndroidSubtitleTextSize.FixedSp(sp),
                androidSubtitleTextSize(AndroidSubtitlePresentation.Television, preset),
            )
        }
    }

    @Test
    fun phonePreservesExistingFractionalLadder() {
        val expected = mapOf(
            SubtitleFontSizePreset.Small to 22.5f / 720f,
            SubtitleFontSizePreset.Medium to 29.25f / 720f,
            SubtitleFontSizePreset.Large to 36f / 720f,
            SubtitleFontSizePreset.XLarge to 45f / 720f,
            SubtitleFontSizePreset.XXLarge to 54f / 720f,
        )

        expected.forEach { (preset, fraction) ->
            assertEquals(
                AndroidSubtitleTextSize.Fractional(fraction),
                androidSubtitleTextSize(AndroidSubtitlePresentation.Phone, preset),
            )
        }
    }

    @Test
    fun fixedSpTextSizeUsesMedia3AbsoluteSizing() {
        val subtitleView = SubtitleView(Robolectric.buildActivity(Activity::class.java).setup().get())

        applyAndroidSubtitleTextSize(subtitleView, AndroidSubtitleTextSize.FixedSp(32f))

        assertEquals(
            SubtitleViewTextSizeConfig(Cue.TEXT_SIZE_TYPE_ABSOLUTE, 32f),
            subtitleView.textSizeConfig(),
        )
    }

    @Test
    fun fractionalTextSizeUsesMedia3ViewHeightSizing() {
        val subtitleView = SubtitleView(Robolectric.buildActivity(Activity::class.java).setup().get())

        applyAndroidSubtitleTextSize(subtitleView, AndroidSubtitleTextSize.Fractional(0.05f))

        assertEquals(
            SubtitleViewTextSizeConfig(Cue.TEXT_SIZE_TYPE_FRACTIONAL, 0.05f),
            subtitleView.textSizeConfig(),
        )
    }
}

private data class SubtitleViewTextSizeConfig(
    val type: Int,
    val size: Float,
)

private fun SubtitleView.textSizeConfig(): SubtitleViewTextSizeConfig {
    val type = SubtitleView::class.java.getDeclaredField("defaultTextSizeType").apply {
        isAccessible = true
    }.getInt(this)
    val size = SubtitleView::class.java.getDeclaredField("defaultTextSize").apply {
        isAccessible = true
    }.getFloat(this)
    return SubtitleViewTextSizeConfig(type, size)
}
