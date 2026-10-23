package org.siloserver.silo.common.player

import androidx.annotation.Dimension
import androidx.media3.ui.SubtitleView
import org.siloserver.silo.model.settings.SubtitleFontSizePreset

internal sealed interface AndroidSubtitleTextSize {
    data class Fractional(val fraction: Float) : AndroidSubtitleTextSize
    data class FixedSp(val sp: Float) : AndroidSubtitleTextSize
}

internal fun androidSubtitleTextSize(
    presentation: AndroidSubtitlePresentation,
    preset: SubtitleFontSizePreset,
): AndroidSubtitleTextSize = when (presentation) {
    AndroidSubtitlePresentation.Phone -> AndroidSubtitleTextSize.Fractional(
        when (preset) {
            // Extra small is offered only on TV; keep the phone's minimum unchanged.
            SubtitleFontSizePreset.XSmall -> 22.5f
            SubtitleFontSizePreset.Small -> 22.5f
            SubtitleFontSizePreset.Medium -> 29.25f
            SubtitleFontSizePreset.Large -> 36f
            SubtitleFontSizePreset.XLarge -> 45f
            SubtitleFontSizePreset.XXLarge -> 54f
        } / 720f,
    )
    AndroidSubtitlePresentation.Television -> AndroidSubtitleTextSize.FixedSp(
        when (preset) {
            SubtitleFontSizePreset.XSmall -> 14f
            SubtitleFontSizePreset.Small -> 18f
            SubtitleFontSizePreset.Medium -> 22f
            SubtitleFontSizePreset.Large -> 26f
            SubtitleFontSizePreset.XLarge -> 32f
            SubtitleFontSizePreset.XXLarge -> 40f
        },
    )
}

/** Applies a policy result through the corresponding Media3 subtitle-size API. */
internal fun applyAndroidSubtitleTextSize(
    subtitleView: SubtitleView,
    textSize: AndroidSubtitleTextSize,
) {
    when (textSize) {
        is AndroidSubtitleTextSize.Fractional -> subtitleView.setFractionalTextSize(
            textSize.fraction,
            /* fractionalRelativeToTextSize = */ false,
        )
        is AndroidSubtitleTextSize.FixedSp -> subtitleView.setFixedTextSize(
            Dimension.SP,
            textSize.sp,
        )
    }
}
