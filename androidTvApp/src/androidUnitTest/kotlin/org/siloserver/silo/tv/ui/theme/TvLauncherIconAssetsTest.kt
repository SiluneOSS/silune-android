package org.siloserver.silo.tv.ui.theme

import java.io.File
import javax.imageio.ImageIO
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class TvLauncherIconAssetsTest {

    @Test
    fun adaptiveForegroundUsesMarkOnlySafeZoneInsteadOfBakedSquareTile() {
        val foreground = ImageIO.read(
            File("src/androidMain/res/mipmap-xxxhdpi/ic_launcher_foreground.png"),
        )

        assertEquals(432, foreground.width)
        assertEquals(432, foreground.height)
        assertTrue(
            foreground.colorModel.hasAlpha(),
            "Adaptive foreground must use transparency so Google TV can own the launcher mask.",
        )
        assertEquals(0, foreground.alphaAt(0, 0), "Top-left corner should be transparent.")
        assertEquals(0, foreground.alphaAt(foreground.width - 1, 0), "Top-right corner should be transparent.")
        assertEquals(0, foreground.alphaAt(0, foreground.height - 1), "Bottom-left corner should be transparent.")
        assertEquals(0, foreground.alphaAt(foreground.width - 1, foreground.height - 1), "Bottom-right corner should be transparent.")
        assertEquals(0, foreground.alphaAt(foreground.width / 2, 0), "Top edge should be transparent.")
        assertEquals(0, foreground.alphaAt(foreground.width / 2, foreground.height - 1), "Bottom edge should be transparent.")
        assertEquals(0, foreground.alphaAt(0, foreground.height / 2), "Left edge should be transparent.")
        assertEquals(0, foreground.alphaAt(foreground.width - 1, foreground.height / 2), "Right edge should be transparent.")
        assertEquals(
            0,
            foreground.alphaAt(foreground.width / 2, foreground.height / 2),
            "The adaptive foreground should be mark-only, not a centered opaque square tile.",
        )

        val bounds = foreground.opaqueBounds()
        assertTrue(
            bounds.minX in 170..185 && bounds.maxX in 245..265,
            "Opaque mark should stay centered horizontally inside the adaptive safe zone: $bounds",
        )
        assertTrue(
            bounds.minY in 80..100 && bounds.maxY in 330..355,
            "Opaque mark should stay vertically inset inside the adaptive safe zone: $bounds",
        )
        assertTrue(
            bounds.width in 70..100 && bounds.height in 240..275,
            "Adaptive foreground should contain a tall Silo mark, not a full tile: $bounds",
        )
    }

    @Test
    fun legacyTvLauncherIconsAreOpaqueSquaresAtRequiredDensities() {
        val expected = mapOf(
            "mipmap-mdpi/ic_launcher.png" to 80,
            "mipmap-hdpi/ic_launcher.png" to 120,
            "mipmap-xhdpi/ic_launcher.png" to 160,
            "mipmap-xxhdpi/ic_launcher.png" to 240,
            "mipmap-xxxhdpi/ic_launcher.png" to 320,
        )

        expected.forEach { (path, size) ->
            val image = ImageIO.read(File("src/androidMain/res/$path"))
            assertEquals(size, image.width, path)
            assertEquals(size, image.height, path)
            assertFalse(image.colorModel.hasAlpha(), "$path must be opaque for legacy TV launchers.")
            assertEquals(255, image.alphaAt(0, 0), "$path top-left corner must be opaque.")
            assertEquals(255, image.alphaAt(size - 1, size - 1), "$path bottom-right corner must be opaque.")
        }
    }

    @Test
    fun legacyTvLauncherIconContainsCenteredColorSiloMark() {
        val icon = ImageIO.read(File("src/androidMain/res/mipmap-xxxhdpi/ic_launcher.png"))
        val accentPixels = buildList {
            for (y in 0 until icon.height) {
                for (x in 0 until icon.width) {
                    val rgb = icon.getRGB(x, y)
                    if (rgb.red() > 180 && rgb.red() > rgb.blue() * 1.15 && rgb.green() < 180) {
                        add(x to y)
                    }
                }
            }
        }

        assertTrue(accentPixels.size > icon.width * icon.height / 100)
        val averageX = accentPixels.sumOf { it.first }.toDouble() / accentPixels.size
        assertTrue(
            averageX in icon.width * 0.42..icon.width * 0.58,
            "Brand accent must remain centered: $averageX",
        )

        var nearWhitePixels = 0
        for (y in 0 until icon.height) {
            for (x in 0 until icon.width) {
                val rgb = icon.getRGB(x, y)
                if (rgb.red() > 230 && rgb.green() > 230 && rgb.blue() > 230) nearWhitePixels++
            }
        }
        assertTrue(
            nearWhitePixels < icon.width * icon.height / 50,
            "Square launcher icon must not bake in the white banner wordmark: $nearWhitePixels pixels",
        )
    }

    @Test
    fun tvBannerRemainsOpaqueWordmarkAtRequiredDimensions() {
        val banner = ImageIO.read(File("src/androidMain/res/drawable/tv_banner.png"))
        assertEquals(320, banner.width)
        assertEquals(180, banner.height)
        assertFalse(banner.colorModel.hasAlpha())

        val wordmarkPixels = buildList {
            for (y in 0 until banner.height) {
                for (x in 0 until banner.width) {
                    val rgb = banner.getRGB(x, y)
                    if (rgb.red() > 230 && rgb.green() > 230 && rgb.blue() > 230) {
                        add(x to y)
                    }
                }
            }
        }
        assertTrue(wordmarkPixels.size > 500, "TV banner must retain the white Silo wordmark.")
        val wordmarkBounds = wordmarkPixels.pixelBounds()
        assertTrue(
            wordmarkBounds.minX >= 70 && wordmarkBounds.maxX <= 249,
            "White wordmark must remain inside Fire TV's centered square crop: $wordmarkBounds",
        )
        assertTrue(
            wordmarkBounds.width in 40..180 && wordmarkBounds.height in 10..90,
            "White wordmark must retain a complete, readable shape: $wordmarkBounds",
        )
        assertTrue(
            wordmarkBounds.width * wordmarkBounds.height >= 500,
            "White wordmark bounds must not collapse to a small or fragmented mark: $wordmarkBounds",
        )
    }

    @Test
    fun tvBannerKeepsColorMarkInsideTheFireTvSquareSafeArea() {
        val banner = ImageIO.read(File("src/androidMain/res/drawable/tv_banner.png"))
        val accentPixels = buildList {
            for (y in 0 until banner.height) {
                for (x in 0 until banner.width) {
                    val rgb = banner.getRGB(x, y)
                    if (rgb.red() > 180 && rgb.red() > rgb.blue() * 1.15 && rgb.green() < 180) {
                        add(x to y)
                    }
                }
            }
        }

        assertTrue(accentPixels.size > 100, "TV banner must retain the colorful Silo mark.")
        val minX = accentPixels.minOf { it.first }
        val maxX = accentPixels.maxOf { it.first }
        assertTrue(minX >= 70 && maxX <= 250, "Color mark must fit inside Fire TV's centered square crop.")
    }
}

private fun java.awt.image.BufferedImage.alphaAt(x: Int, y: Int): Int =
    if (colorModel.hasAlpha()) {
        (getRGB(x, y) ushr 24) and 0xff
    } else {
        255
    }

private fun Int.red(): Int = (this ushr 16) and 0xff

private fun Int.green(): Int = (this ushr 8) and 0xff

private fun Int.blue(): Int = this and 0xff

private data class AlphaBounds(
    val minX: Int,
    val minY: Int,
    val maxX: Int,
    val maxY: Int,
) {
    val width: Int = maxX - minX + 1
    val height: Int = maxY - minY + 1
}

private data class PixelBounds(
    val minX: Int,
    val minY: Int,
    val maxX: Int,
    val maxY: Int,
) {
    val width: Int = maxX - minX + 1
    val height: Int = maxY - minY + 1
}

private fun List<Pair<Int, Int>>.pixelBounds(): PixelBounds = PixelBounds(
    minX = minOf { it.first },
    minY = minOf { it.second },
    maxX = maxOf { it.first },
    maxY = maxOf { it.second },
)

private fun java.awt.image.BufferedImage.opaqueBounds(): AlphaBounds {
    var minX = width
    var minY = height
    var maxX = -1
    var maxY = -1
    for (y in 0 until height) {
        for (x in 0 until width) {
            if (alphaAt(x, y) > 16) {
                if (x < minX) minX = x
                if (y < minY) minY = y
                if (x > maxX) maxX = x
                if (y > maxY) maxY = y
            }
        }
    }
    return AlphaBounds(minX = minX, minY = minY, maxX = maxX, maxY = maxY)
}
