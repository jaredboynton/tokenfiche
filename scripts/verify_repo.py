#!/usr/bin/env python3
"""Verify that the packaged repo contains the expected evidence and scripts."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BEST = ROOT / "experiments" / "atkinson_10_1M"
API = ROOT / "experiments" / "atkinson_10_1M-api"


def check(condition: bool, message: str, failures: list[str]) -> None:
    if condition:
        print(f"ok - {message}")
    else:
        print(f"not ok - {message}")
        failures.append(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> int:
    failures: list[str] = []

    for path in [
        ROOT / "README.md",
        ROOT / "pyproject.toml",
        ROOT / "docs" / "experiment-log.md",
        ROOT / "docs" / "request-shape.md",
        ROOT / "scripts" / "render_token_images.py",
        ROOT / "scripts" / "build_codex_request.py",
        ROOT / "scripts" / "send_codex_request.py",
    ]:
        check(path.exists(), f"{path.relative_to(ROOT)} exists", failures)

    for script in (ROOT / "scripts").glob("*.py"):
        try:
            ast.parse(script.read_text())
            parsed = True
        except SyntaxError:
            parsed = False
        check(parsed, f"{script.relative_to(ROOT)} parses", failures)

    best_summary = load_json(API / "atkinson_10_1M.summary.json")
    fail_summary = load_json(ROOT / "experiments" / "codex-gpt55-image-maximize-2026-06-20" / "api" / "t836811-p31-c10-fs10-m0-g0-ext562.summary.json")
    manifest = load_json(BEST / "manifest.json")

    check(best_summary["classification"] == "completed_all_needles_found", "best run found all needles", failures)
    check(best_summary["source_tokens"] == 1000000, "best run source token count is 1,000,000", failures)
    check(best_summary["usage"]["input_tokens"] == 318283, "best run input tokens are recorded", failures)
    check(manifest["pixels"] == 270000000, "best run records 270M pixels", failures)
    check(manifest["estimated_total_patches"] == 265080, "best run records 265,080 patches", failures)
    check(manifest["preflight_pass"] is True, "best run passed render preflight", failures)
    check(manifest["capacity_pass"] is True, "best run capacity check passed", failures)
    check(manifest["markers_placed"] is True, "best run marker placement check passed", failures)
    check(fail_summary["error"]["code"] == "context_length_exceeded", "31-image failure is recorded", failures)

    pages = sorted(BEST.glob("page-*.png"))
    crops = sorted(BEST.glob("needle-*-crop.png"))
    all_pngs = sorted(ROOT.glob("**/*.png"))
    check(len(pages) == 30, "best run has 30 page images", failures)
    check(len(crops) == 3, "best run has 3 needle crops", failures)
    check(len(all_pngs) == 43, "only best-run and color-layer-overlap PNGs are kept", failures)

    if (ROOT / ".git").exists():
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        check(result.returncode == 0, "git status works", failures)
    else:
        check(False, "repo is initialized with git", failures)

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("\nAll package checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
