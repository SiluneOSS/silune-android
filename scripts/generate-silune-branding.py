#!/usr/bin/env python3
"""Render the Silune artwork. Requires rsvg-convert, Pillow, and FFmpeg/libx264.

The wordmark contains outlined DejaVu Sans Bold lettering; no font install is needed.
Run from any directory with: python3 scripts/generate-silune-branding.py
"""

from io import BytesIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BACKGROUND = "#25252D"
SPLASH_DURATION = "1.6"


def render(name, width, height):
    return Image.open(BytesIO(subprocess.check_output([
        "rsvg-convert", "--width", str(width), "--height", str(height),
        str(ROOT / "branding" / name),
    ]))).convert("RGBA")


def generate_splash():
    # Keep the existing decoder tiers: 720p30 AVC 3.1 for weaker TV boxes,
    # and 1080p60 AVC 4.2 for devices that advertise support for it.
    raw = ROOT / "android-shared/src/androidMain/res/raw"
    with TemporaryDirectory(prefix="silune-splash-") as directory:
        wordmark_path = Path(directory) / "wordmark.png"
        for name, width, height, frame_rate, level in (
            ("startup_splash", 1280, 720, 30, "3.1"),
            ("startup_splash_hd", 1920, 1080, 60, "4.2"),
        ):
            wordmark_width = width * 9 // 10
            wordmark = render("silune-wordmark.svg", wordmark_width, wordmark_width // 3)
            # Composite transparency before encoding so the video and app
            # background share the same pure black.
            frame = Image.new("RGB", (width, height), "black")
            frame.paste(wordmark, ((width - wordmark.width) // 2,
                                  (height - wordmark.height) // 2), wordmark)
            frame.save(wordmark_path)
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-loop", "1", "-framerate", str(frame_rate), "-i", str(wordmark_path),
                "-vf", "fade=t=in:st=0:d=0.25,fade=t=out:st=1.3:d=0.25,format=yuv420p",
                "-t", SPLASH_DURATION, "-an", "-c:v", "libx264",
                "-profile:v", "high", "-level:v", level, "-crf", "18",
                "-preset", "medium", "-threads", "2", "-movflags", "+faststart",
                "-map_metadata", "-1", "-metadata", "title=Silune startup splash",
                str(raw / f"{name}.mp4"),
            ], check=True)


def generate():
    foreground = render("silune-mark.svg", 512, 512)
    icon = Image.new("RGB", (512, 512), BACKGROUND)
    icon.paste(foreground, (0, 0), foreground)
    icon.save(ROOT / "assets/icon.png", optimize=True)
    wordmark = render("silune-wordmark.svg", 1200, 400)
    banner_wordmark = render("silune-wordmark.svg", 170, 57)
    banner = Image.new("RGB", (320, 180), BACKGROUND)
    banner.paste(banner_wordmark, (75, 61), banner_wordmark)
    for module in ("androidApp", "androidTvApp"):
        res = ROOT / module / "src/androidMain/res"
        icon.save(res / "mipmap-nodpi/ic_launcher.png", optimize=True)
        foreground.save(res / "mipmap-nodpi/ic_launcher_foreground.png", optimize=True)
        wordmark.save(res / "drawable/silo_wordmark.png", optimize=True)
        if module == "androidTvApp":
            foreground.save(res / "drawable/silo_mark.png", optimize=True)
            banner.save(res / "drawable/tv_banner.png", optimize=True)
    generate_splash()


if __name__ == "__main__":
    generate()
