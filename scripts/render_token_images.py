#!/usr/bin/env python3
"""Render tokenizer-counted text into dense page images."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import textwrap
from pathlib import Path

import tiktoken
from PIL import Image, ImageDraw, ImageFont


DEFAULT_MARKERS = [
    ("alpha", "NEEDLE_ALPHA::AHAB-SEES-7429", 0.20),
    ("beta", "NEEDLE_BETA::QUEEQUEG-LANTERN-1836", 0.50),
    ("gamma", "NEEDLE_GAMMA::MELVILLE-SURF-9021", 0.90),
]


def existing_font() -> str | None:
    candidates = [
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/Library/Fonts/Courier New.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def exact_token_text(encoding: tiktoken.Encoding, text: str, target_tokens: int) -> str:
    ids = encoding.encode(text)
    if len(ids) < target_tokens:
        raise ValueError(f"source has {len(ids)} tokens, need {target_tokens}")
    trimmed = encoding.decode(ids[:target_tokens])
    actual = len(encoding.encode(trimmed))
    if actual != target_tokens:
        trimmed = encoding.decode(encoding.encode(trimmed)[:target_tokens])
    actual = len(encoding.encode(trimmed))
    if actual != target_tokens:
        raise ValueError(f"could not trim exactly: got {actual}, need {target_tokens}")
    return trimmed


def source_from_inputs(
    encoding: tiktoken.Encoding,
    files: list[Path],
    target_tokens: int,
    repeat_corpus: int,
    insert_needles: bool,
) -> str:
    corpus = "\n\n".join(path.read_text(errors="replace") for path in files)
    if repeat_corpus > 1:
        corpus = ("\n\n" + corpus) * repeat_corpus
    ids = encoding.encode(corpus)
    if len(ids) < target_tokens:
        raise ValueError(f"corpus has {len(ids)} tokens, need {target_tokens}")

    if not insert_needles:
        return exact_token_text(encoding, corpus, target_tokens)

    pieces: list[str] = []
    cursor = 0
    for _name, marker, frac in DEFAULT_MARKERS:
        offset = min(max(int(target_tokens * frac), cursor), len(ids))
        pieces.append(encoding.decode(ids[cursor:offset]))
        pieces.append(f"\n\n{marker}\n\n")
        cursor = offset
    pieces.append(encoding.decode(ids[cursor : target_tokens + 512]))
    with_markers = "".join(pieces)
    if len(encoding.encode(with_markers)) < target_tokens:
        with_markers += encoding.decode(ids[target_tokens : target_tokens + 4096])
    return exact_token_text(encoding, with_markers, target_tokens)


def reflow_lines(text: str, chars_per_line: int) -> list[str]:
    paragraphs = [
        re.sub(r"\s+", " ", paragraph).strip()
        for paragraph in re.split(r"\n\s*\n+", text)
        if paragraph.strip()
    ]
    lines: list[str] = []
    for paragraph in paragraphs:
        lines.extend(
            textwrap.wrap(
                paragraph,
                width=chars_per_line,
                break_long_words=True,
                break_on_hyphens=False,
            )
            or [""]
        )
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-text", type=Path)
    source.add_argument("--input", type=Path, nargs="+")
    parser.add_argument("--target-tokens", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--encoding", default="o200k_base")
    parser.add_argument("--repeat-corpus", type=int, default=1)
    parser.add_argument("--insert-needles", action="store_true")
    parser.add_argument("--width", type=int, default=3000)
    parser.add_argument("--height", type=int, default=3000)
    parser.add_argument("--pages", type=int, default=30)
    parser.add_argument("--columns", type=int, default=10)
    parser.add_argument("--font-size", type=int, default=10)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--chars-per-line", type=int)
    parser.add_argument("--line-height", type=int)
    parser.add_argument("--margin", type=int, default=0)
    parser.add_argument("--gutter", type=int, default=0)
    parser.add_argument("--fail-on-overflow", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    encoding = tiktoken.get_encoding(args.encoding)

    source_paths = [args.source_text] if args.source_text else args.input
    text = source_from_inputs(
        encoding,
        source_paths,
        args.target_tokens,
        args.repeat_corpus if args.input else 1,
        args.insert_needles,
    )
    source_files = [str(path) for path in source_paths]

    args.out.mkdir(parents=True, exist_ok=True)
    source_path = args.out / f"source-{args.target_tokens}-tokens.txt"
    source_path.write_text(text)

    font_path = str(args.font) if args.font else existing_font()
    if font_path:
        font = ImageFont.truetype(font_path, args.font_size)
    else:
        font = ImageFont.load_default()

    probe = Image.new("L", (args.width, args.height), 255)
    draw = ImageDraw.Draw(probe)
    char_width = max(1, math.ceil(draw.textlength("M", font=font)))
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    measured_line_height = max(1, bbox[3] - bbox[1] + 2)
    line_height = args.line_height or measured_line_height

    column_width = (args.width - 2 * args.margin - args.gutter * (args.columns - 1)) / args.columns
    chars_per_line = args.chars_per_line or max(1, int(column_width // char_width))
    lines_per_col = max(1, (args.height - 2 * args.margin) // line_height)
    lines_per_page = lines_per_col * args.columns
    capacity = lines_per_page * args.pages
    lines = reflow_lines(text, chars_per_line)

    if args.fail_on_overflow and len(lines) > capacity:
        raise SystemExit(f"render would overflow: {len(lines)} lines > {capacity} capacity")

    markers = [
        {"name": name, "marker": marker, "actual_token_offset": None}
        for name, marker, _frac in DEFAULT_MARKERS
    ]
    for marker in markers:
        if marker["marker"] in text:
            before = text.split(marker["marker"], 1)[0]
            marker["actual_token_offset"] = len(encoding.encode(before))

    marker_positions: dict[str, dict[str, int | str]] = {}
    ink_widths: list[float] = []
    ink_bboxes: list[tuple[int, int, int, int] | None] = []

    for page in range(args.pages):
        image = Image.new("L", (args.width, args.height), 255)
        draw = ImageDraw.Draw(image)
        start = page * lines_per_page
        for index, line in enumerate(lines[start : start + lines_per_page]):
            col = index // lines_per_col
            row = index % lines_per_col
            x = int(round(args.margin + col * (column_width + args.gutter)))
            y = int(args.margin + row * line_height)
            draw.text((x, y), line, fill=0, font=font)
            for marker in markers:
                if marker["marker"] in line:
                    marker_positions[marker["name"]] = {
                        "page": page + 1,
                        "column": col + 1,
                        "row": row,
                        "line": line,
                    }
        image.save(args.out / f"page-{page + 1:03d}.png", optimize=True)
        ink_bbox = Image.eval(image, lambda px: 255 - px).getbbox()
        ink_bboxes.append(ink_bbox)
        if ink_bbox:
            ink_widths.append(round((ink_bbox[2] - ink_bbox[0]) / args.width * 100, 2))

    for marker in markers:
        position = marker_positions.get(marker["name"])
        if not position:
            continue
        page_image = Image.open(args.out / f"page-{position['page']:03d}.png")
        col = int(position["column"]) - 1
        row = int(position["row"])
        x = int(round(args.margin + col * (column_width + args.gutter)))
        y = int(args.margin + row * line_height)
        crop = page_image.crop(
            (
                max(0, x - 20),
                max(0, y - 70),
                min(args.width, x + int(column_width) + 80),
                min(args.height, y + 220),
            )
        )
        crop.save(args.out / f"needle-{marker['name']}-crop.png", optimize=True)

    capacity_pass = len(lines) <= capacity
    markers_placed = all(marker["name"] in marker_positions for marker in markers)
    preflight_pass = capacity_pass and markers_placed

    manifest = {
        "variant": args.out.name,
        "source_tokens": args.target_tokens,
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "source_files": source_files,
        "layout": {
            "page_count": args.pages,
            "columns": args.columns,
            "font_size": args.font_size,
            "font_path": font_path,
            "margin": args.margin,
            "gutter": args.gutter,
            "image_width": args.width,
            "image_height": args.height,
            "column_width": round(column_width, 2),
            "char_width": char_width,
            "chars_per_line": chars_per_line,
            "line_height": line_height,
            "lines_per_col": lines_per_col,
            "lines_per_page": lines_per_page,
        },
        "line_count": len(lines),
        "capacity": capacity,
        "capacity_pass": capacity_pass,
        "markers_placed": markers_placed,
        "preflight_pass": preflight_pass,
        "markers": markers,
        "marker_positions": marker_positions,
        "estimated_total_patches": args.pages
        * math.ceil(args.width / 32)
        * math.ceil(args.height / 32),
        "pixels": args.pages * args.width * args.height,
        "ink_width_pct_avg_rendered": round(sum(ink_widths) / len(ink_widths), 2)
        if ink_widths
        else 0,
        "ink_width_pct_min_rendered": min(ink_widths) if ink_widths else 0,
        "ink_width_pct_by_page": ink_widths,
        "ink_bboxes": ink_bboxes,
        "total_image_bytes": sum(path.stat().st_size for path in args.out.glob("page-*.png")),
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    return 0 if preflight_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
