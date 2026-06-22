#!/usr/bin/env python3
"""Render two text layers in separable colors to test color-multiplexed density.

Layer A drawn blue, layer B drawn red, magenta where their ink coincides. This
probes the hypothesis: can a vision model separate two color-coded text layers
that occupy the SAME image patches, doubling source tokens at constant patch cost?

Tiles are kept small (native res) so a Claude vision reader does not downscale
them; this mirrors the 10px glyphs GPT-5.5 patchifies at detail:"original".
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

FONT_PATH = "/System/Library/Fonts/Supplemental/Courier New.ttf"
FONT_SIZE = 10
CHARS_PER_LINE = 49        # proven config
LINE_HEIGHT = 11           # proven config
N_LINES = 48               # tile height ~ 48*11 = 528px (under 1568 downscale cap)
N_NEEDLES_PER_LAYER = 8
OUT = Path(__file__).resolve().parent
SEED = 20260620


def make_needle(rng: random.Random, tag: str) -> str:
    alpha = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I/O to avoid 1/0 confusion
    dig = "23456789"
    pool = alpha + dig
    groups = ["".join(rng.choice(pool) for _ in range(4)) for _ in range(4)]
    return f"{tag}::" + "-".join(groups)


def words_from_corpus(path: Path, rng: random.Random) -> list[str]:
    raw = path.read_text(errors="replace")
    words = [w for w in raw.split() if w.isalpha() and 2 <= len(w) <= 11]
    rng.shuffle(words)
    return words


def build_layer(words: list[str], needles: list[str], needle_lines: set[int]) -> list[str]:
    """Build N_LINES lines, each exactly CHARS_PER_LINE wide, needles on given lines."""
    lines: list[str] = []
    wi = 0
    ni = 0
    for li in range(N_LINES):
        if li in needle_lines and ni < len(needles):
            needle = needles[ni]
            ni += 1
            line = needle
            while len(line) < CHARS_PER_LINE - 6:
                line = words[wi % len(words)] + " " + line
                wi += 1
            line = ("the " + line)[:CHARS_PER_LINE]
        else:
            line = ""
            while len(line) < CHARS_PER_LINE:
                w = words[wi % len(words)]
                wi += 1
                line = (line + " " + w) if line else w
            line = line[:CHARS_PER_LINE]
        lines.append(line.ljust(CHARS_PER_LINE))
    return lines


def render_gray(lines: list[str], font: ImageFont.FreeTypeFont, w: int, h: int,
                dx: int = 0, dy: int = 0) -> Image.Image:
    """Grayscale (L): ink=0 on white=255."""
    img = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((dx, dy + i * LINE_HEIGHT), line, fill=0, font=font)
    return img


def composite_color(gray_a: Image.Image, gray_b: Image.Image) -> Image.Image:
    """A->blue, B->red, magenta where both ink (smooth, AA-preserving).
    ink = 255 - gray (full ink = 255). Corners:
      A only -> (0,0,255) blue ; B only -> (255,0,0) red ; both -> (255,0,255) magenta.
    """
    ink_a = ImageChops.invert(gray_a)
    ink_b = ImageChops.invert(gray_b)
    # multiply(x,y) = x*y/255, so invert(multiply(ink_a, gray_b)) = 255 - ink_a*(255-ink_b)/255
    R = ImageChops.invert(ImageChops.multiply(ink_a, gray_b))
    B = ImageChops.invert(ImageChops.multiply(ink_b, gray_a))
    G = ImageChops.darker(gray_a, gray_b)
    return Image.merge("RGB", (R, G, B))


def main() -> None:
    rng = random.Random(SEED)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    probe = ImageDraw.Draw(Image.new("L", (10, 10)))
    char_w = max(1, math.ceil(probe.textlength("M", font=font)))
    width = CHARS_PER_LINE * char_w + 4
    height = N_LINES * LINE_HEIGHT + 4

    words = words_from_corpus(OUT.parent.parent / "examples/gutenberg-cache/Moby-Dick.txt", rng)

    needles_a = [make_needle(rng, f"AX{n}") for n in range(N_NEEDLES_PER_LAYER)]
    needles_b = [make_needle(rng, f"BY{n}") for n in range(N_NEEDLES_PER_LAYER)]
    lines_a_idx = set(list(range(3, N_LINES, 6))[:N_NEEDLES_PER_LAYER])
    lines_b_idx = set(list(range(6, N_LINES, 6))[:N_NEEDLES_PER_LAYER])

    lines_a = build_layer(words, needles_a, lines_a_idx)
    lines_b = build_layer(words[len(words) // 2:] + words[: len(words) // 2], needles_b, lines_b_idx)

    gray_a = render_gray(lines_a, font, width, height)
    gray_b = render_gray(lines_b, font, width, height)
    gray_b_off = render_gray(lines_b, font, width, height, dx=3, dy=5)

    gray_a.save(OUT / "v_A_gray.png", optimize=True)
    gray_b.save(OUT / "v_B_gray.png", optimize=True)
    composite_color(gray_a, gray_b).save(OUT / "v_overlap_color.png", optimize=True)
    composite_color(gray_a, gray_b_off).save(OUT / "v_offset_color.png", optimize=True)

    ground_truth = {
        "config": {
            "font": FONT_PATH, "font_size": FONT_SIZE, "chars_per_line": CHARS_PER_LINE,
            "line_height": LINE_HEIGHT, "n_lines": N_LINES, "char_width": char_w,
            "tile_w": width, "tile_h": height, "seed": SEED,
        },
        "layer_A": {"needles": needles_a, "lines": lines_a},
        "layer_B": {"needles": needles_b, "lines": lines_b},
        "variants": {
            "v_A_gray.png": "single layer A, grayscale (control)",
            "v_B_gray.png": "single layer B, grayscale (control)",
            "v_overlap_color.png": "A=blue + B=red, full overlap, magenta=both",
            "v_offset_color.png": "A=blue + B=red(+3,+5px), magenta=both",
        },
    }
    (OUT / "ground_truth.json").write_text(json.dumps(ground_truth, indent=2))
    print(json.dumps({
        "tile_size": [width, height],
        "char_width": char_w,
        "needles_A": needles_a,
        "needles_B": needles_b,
        "under_downscale_cap": max(width, height) < 1568,
    }, indent=2))


if __name__ == "__main__":
    main()
