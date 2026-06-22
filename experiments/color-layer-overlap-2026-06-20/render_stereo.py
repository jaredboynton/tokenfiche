#!/usr/bin/env python3
"""Stereoscopic two-layer text overlay: blue text A @50% + red text B @50%.

Two DIFFERENT texts share the same pixels. Blue layer and red layer each at 50%
opacity over white, so where they cross the blend goes purple. The bet: a vision
model separates the layers by color and reads BOTH, doubling text per image patch.
Readable sans (Inter SemiBold) per direction; full assembled page.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
FONT = ImageFont.truetype(str(OUT / "fonts/AtkinsonMono.ttf"), 18)
FONT.set_variation_by_name("SemiBold")
SIZE = 18
LINE_H = 16            # Atkinson Mono ink span 15px + 1px gap (true min, no clipping)
PAGE_W, PAGE_H = 3000, 3000
MARGIN = 1
COL_W = 747            # 4 cols * 747 + 3*3 gap + 2*1 margin = 2999 (fills 3000 width)
COL_GAP = 3
RULE = (0, 0, 0)       # 1px column separator drawn down the middle of each gutter
N_NEEDLES = 8
SEED = 20260620
BLUE = (0, 0, 255)
RED = (255, 0, 0)


def make_needle(rng: random.Random, tag: str) -> str:
    pool = "ABCDEFGHJKLMNPQRSTUVWXYZ" + "23456789"
    return f"{tag}::" + "-".join("".join(rng.choice(pool) for _ in range(4)) for _ in range(4))


def corpus_words(rng: random.Random) -> list[str]:
    raw = (OUT.parent.parent / "examples/gutenberg-cache/Moby-Dick.txt").read_text(errors="replace")
    words = [w for w in raw.split() if w.isalpha() and 2 <= len(w) <= 11]
    rng.shuffle(words)
    return words


def wrap_to_width(words: list[str], start: int, needles: list[str], font, col_w: int,
                  n_lines: int) -> tuple[list[str], int]:
    """Greedy word-wrap to pixel width; inject needles roughly evenly."""
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    lines: list[str] = []
    wi = start
    place_every = max(1, n_lines // (len(needles) + 1))
    ni = 0
    cur = ""
    while len(lines) < n_lines:
        if len(lines) > 0 and len(lines) % place_every == 0 and ni < len(needles):
            tok = needles[ni]; ni += 1
        else:
            tok = words[wi % len(words)]; wi += 1
        trial = (cur + " " + tok).strip()
        if draw.textlength(trial, font=font) <= col_w:
            cur = trial
        else:
            lines.append(cur)
            cur = tok
    return lines, wi


def render_layer(text_lines_by_col: list[list[str]], color: tuple[int, int, int],
                 dx: int = 0, dy: int = 0) -> Image.Image:
    """Draw solid-color text on transparent RGBA, full opacity (alpha applied later)."""
    layer = Image.new("RGBA", (PAGE_W, PAGE_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for ci, lines in enumerate(text_lines_by_col):
        x = MARGIN + dx + ci * (COL_W + COL_GAP)
        for li, line in enumerate(lines):
            draw.text((x, MARGIN + dy + li * LINE_H), line, fill=color + (255,), font=FONT)
    return layer


def channel_separate(layer_a: Image.Image, layer_b: Image.Image) -> Image.Image:
    """Max-separability: A->pure blue (0,0,255), B->pure red (255,0,0), overlap->magenta, bg white.
    Each layer lives in its own RGB channel with zero crosstalk."""
    from PIL import ImageChops
    ink_a = layer_a.split()[3]   # alpha = glyph coverage (255 = ink)
    ink_b = layer_b.split()[3]
    R = ImageChops.lighter(ImageChops.invert(ink_a), ink_b)
    B = ImageChops.lighter(ImageChops.invert(ink_b), ink_a)
    G = ImageChops.invert(ImageChops.lighter(ink_a, ink_b))
    return Image.merge("RGB", (R, G, B))


def draw_col_rules(img: Image.Image, n_cols: int) -> Image.Image:
    """Draw a 1px vertical rule down the middle of each inter-column gutter."""
    d = ImageDraw.Draw(img)
    for i in range(n_cols - 1):
        x = MARGIN + i * (COL_W + COL_GAP) + COL_W + COL_GAP // 2
        d.line([(x, 0), (x, PAGE_H)], fill=RULE, width=1)
    return img


def at_opacity(layer: Image.Image, frac: float) -> Image.Image:
    r, g, b, a = layer.split()
    a = a.point(lambda v: int(v * frac))
    return Image.merge("RGBA", (r, g, b, a))


def build_columns(words, needles_per_col, font):
    n_cols = (PAGE_W - 2 * MARGIN + COL_GAP) // (COL_W + COL_GAP)
    n_lines = (PAGE_H - 2 * MARGIN) // LINE_H
    cols, wi = [], 0
    for c in range(n_cols):
        lines, wi = wrap_to_width(words, wi, needles_per_col[c], font, COL_W, n_lines)
        cols.append(lines)
    return cols


def main() -> None:
    rng = random.Random(SEED)
    words_a = corpus_words(rng)
    words_b = corpus_words(random.Random(SEED + 1))

    n_cols = (PAGE_W - 2 * MARGIN + COL_GAP) // (COL_W + COL_GAP)
    needles_a = [make_needle(rng, f"AX{i}") for i in range(N_NEEDLES)]
    needles_b = [make_needle(rng, f"BY{i}") for i in range(N_NEEDLES)]
    # spread needles across columns
    a_by_col = [[] for _ in range(n_cols)]
    b_by_col = [[] for _ in range(n_cols)]
    for i, nd in enumerate(needles_a):
        a_by_col[i % n_cols].append(nd)
    for i, nd in enumerate(needles_b):
        b_by_col[i % n_cols].append(nd)

    cols_a = build_columns(words_a, a_by_col, FONT)
    cols_b = build_columns(words_b, b_by_col, FONT)

    layer_a = render_layer(cols_a, BLUE)
    layer_b = render_layer(cols_b, RED)

    # stereoscopic: white base, blue @50%, red @50%
    base = Image.new("RGBA", (PAGE_W, PAGE_H), (255, 255, 255, 255))
    base.alpha_composite(at_opacity(layer_a, 0.5))
    base.alpha_composite(at_opacity(layer_b, 0.5))
    stereo = draw_col_rules(base.convert("RGB"), n_cols)
    stereo.save(OUT / "stereo_full.png", optimize=True)

    # single-layer baseline (blue text A only, full opacity) at same geometry
    base1 = Image.new("RGBA", (PAGE_W, PAGE_H), (255, 255, 255, 255))
    base1.alpha_composite(layer_a)
    draw_col_rules(base1.convert("RGB"), n_cols).save(OUT / "single_full.png", optimize=True)

    # max-separability channel-coded variants (pure-channel, zero crosstalk)
    chan = draw_col_rules(channel_separate(layer_a, layer_b), n_cols)
    chan.save(OUT / "chan_overlap.png", optimize=True)
    layer_b_off = render_layer(cols_b, RED, dy=LINE_H // 2)   # red shifted half a line down
    draw_col_rules(channel_separate(layer_a, layer_b_off), n_cols).save(OUT / "chan_offset.png", optimize=True)

    # native-res readable crops for inspection (top-left)
    stereo.crop((0, 0, 820, 520)).save(OUT / "stereo_crop.png", optimize=True)
    chan.crop((0, 0, 820, 520)).save(OUT / "chan_crop.png", optimize=True)

    gt = {
        "config": {"font": "Inter SemiBold", "size": SIZE, "line_h": LINE_H,
                   "page": [PAGE_W, PAGE_H], "n_cols": n_cols, "col_w": COL_W, "seed": SEED},
        "layer_A_blue": {"needles": needles_a, "cols": cols_a},
        "layer_B_red": {"needles": needles_b, "cols": cols_b},
    }
    (OUT / "stereo_ground_truth.json").write_text(json.dumps(gt, indent=2))
    print(json.dumps({"page": [PAGE_W, PAGE_H], "n_cols": n_cols,
                      "lines_per_col": len(cols_a[0]),
                      "needles_A": needles_a, "needles_B": needles_b}, indent=2))


if __name__ == "__main__":
    main()
