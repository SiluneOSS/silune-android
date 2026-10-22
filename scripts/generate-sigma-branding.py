#!/usr/bin/env python3
"""Render the original Sigma Player SVGs. Requires rsvg-convert and Pillow.

The wordmark uses DejaVu Sans Bold; install that font before regenerating.
Run from any directory with: python3 scripts/generate-sigma-branding.py
"""

from io import BytesIO
from pathlib import Path
import subprocess

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BACKGROUND = "#010D9F"


def render(name, width, height):
    return Image.open(BytesIO(subprocess.check_output([
        "rsvg-convert", "--width", str(width), "--height", str(height),
        str(ROOT / "branding" / name),
    ]))).convert("RGBA")


def generate():
    foreground = render("sigma-mark.svg", 512, 512)
    icon = Image.new("RGB", (512, 512), BACKGROUND)
    icon.paste(foreground, (0, 0), foreground)
    wordmark = render("sigma-wordmark.svg", 1200, 400)
    banner_wordmark = render("sigma-wordmark.svg", 170, 57)
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


if __name__ == "__main__":
    generate()
