#!/usr/bin/env python3
"""Send a stereo/single image to GPT-5.5 (native patches) and score code recovery."""
from __future__ import annotations

import base64
import json
import ssl
import sys
import time
import uuid
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from send_codex_request import load_auth, parse_sse  # reuse auth + SSE parsing

OUT = Path(__file__).resolve().parent
URL = "https://chatgpt.com/backend-api/codex/responses"

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["blue_codes", "red_codes", "notes"],
    "properties": {
        "blue_codes": {"type": "array", "items": {"type": "string"}},
        "red_codes": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
}

STEREO_PROMPT = (
    "This single image overlays TWO different texts distinguished ONLY by color, "
    "each drawn at 50% opacity over white: a BLUE text and a RED text occupying the "
    "same space; where they cross, pixels turn purple. Blue+purple pixels are the "
    "BLUE text; red+purple pixels are the RED text. Each text contains high-entropy "
    "codes formatted exactly like PREFIX::GGGG-GGGG-GGGG-GGGG (PREFIX 2-3 chars; each "
    "GGGG is 4 chars from A-Z and digits 2-9), about 8 per color. Separate the two "
    "colors and transcribe every code you can read, character for character, into "
    "blue_codes and red_codes. Do not guess or autocomplete."
)
SINGLE_PROMPT = (
    "This image is dense blue text on white. It contains high-entropy codes formatted "
    "exactly like PREFIX::GGGG-GGGG-GGGG-GGGG (PREFIX 2-3 chars; each GGGG is 4 chars "
    "from A-Z and digits 2-9), about 8 of them. Transcribe every code you can read, "
    "character for character, into blue_codes (leave red_codes empty). Do not guess."
)


def send(image: Path, prompt: str, effort: str) -> dict:
    encoded = base64.b64encode(image.read_bytes()).decode("ascii")
    body = {
        "model": "gpt-5.5",
        "instructions": "Return strict JSON only. Transcribe exact codes from the image. Do not invent codes.",
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}", "detail": "original"},
        ]}],
        "text": {"format": {"type": "json_schema", "strict": True, "name": "stereo_probe", "schema": SCHEMA}},
        "reasoning": {"effort": effort},
        "stream": True, "include": ["reasoning.encrypted_content"], "tools": [],
        "tool_choice": "auto", "parallel_tool_calls": False, "store": False,
        "service_tier": "priority", "prompt_cache_key": f"stereo-{image.stem}-{uuid.uuid4()}",
    }
    access, account = load_auth(Path.home() / ".codex" / "auth.json")
    headers = {
        "Authorization": f"Bearer {access}", "originator": "codex_cli_rs",
        "User-Agent": "codex_cli_rs/0.142.0-alpha.7 (Mac OS 15.7.3; arm64) reqwest/0.12.28",
        "Accept": "text/event-stream", "Content-Type": "application/json",
        "session-id": str(uuid.uuid4()), "thread-id": str(uuid.uuid4()),
        "x-client-request-id": str(uuid.uuid4()), "x-codex-installation-id": str(uuid.uuid4()),
        "x-codex-window-id": str(uuid.uuid4()),
    }
    if account:
        headers["ChatGPT-Account-Id"] = account
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=headers, method="POST")
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600, context=ssl.create_default_context()) as r:
            status = f"HTTP {r.status} {r.reason}"; payload = r.read()
    except urllib.error.HTTPError as e:  # type: ignore
        status = f"HTTP error {e.code} {e.reason}"; payload = e.read()
    text = payload.decode("utf-8", errors="replace")
    (OUT / f"probe_{image.stem}.sse").write_text(text)
    parsed = parse_sse(text, {})
    return {"status": status, "elapsed": round(time.time() - t, 1),
            "request_bytes": len(json.dumps(body)), "parsed_output": parsed.get("parsed_output"),
            "response_status": parsed.get("response_status"), "usage": parsed.get("usage"),
            "error": parsed.get("error"), "raw_output_text": parsed.get("output_text")}


def score(found: list[str], truth: list[str]) -> dict:
    f = set(found or [])
    exact = [t for t in truth if t in f]
    # near = right structure, <=2 char edits
    def cer(a, b):
        import difflib
        return 1 - difflib.SequenceMatcher(None, a, b).ratio()
    near = []
    for t in truth:
        if t in f:
            continue
        best = min((cer(t, x) for x in f), default=1.0)
        if best <= 0.15:
            near.append(t)
    return {"truth": len(truth), "exact": len(exact), "near_miss": len(near),
            "exact_codes": exact, "missed": [t for t in truth if t not in f and t not in near]}


def main() -> None:
    gt = json.loads((OUT / "stereo_ground_truth.json").read_text())
    a_truth = gt["layer_A_blue"]["needles"]
    b_truth = gt["layer_B_red"]["needles"]
    effort = sys.argv[1] if len(sys.argv) > 1 else "medium"

    results = {}
    # baseline: single blue layer
    r1 = send(OUT / "single_full.png", SINGLE_PROMPT, effort)
    p1 = r1.get("parsed_output") or {}
    results["single_blue_baseline"] = {
        "meta": {k: r1[k] for k in ("status", "elapsed", "response_status", "usage")},
        "blue": score(p1.get("blue_codes", []), a_truth),
        "raw": r1.get("raw_output_text"),
    }
    # stereo: blue + red overlay (50/50 opacity)
    r2 = send(OUT / "stereo_full.png", STEREO_PROMPT, effort)
    p2 = r2.get("parsed_output") or {}
    results["stereo_overlay"] = {
        "meta": {k: r2[k] for k in ("status", "elapsed", "response_status", "usage")},
        "blue": score(p2.get("blue_codes", []), a_truth),
        "red": score(p2.get("red_codes", []), b_truth),
        "raw": r2.get("raw_output_text"),
    }
    # channel-separated max-separability variants
    for tag, fname in (("chan_overlap", "chan_overlap.png"), ("chan_offset", "chan_offset.png")):
        r = send(OUT / fname, STEREO_PROMPT, effort)
        p = r.get("parsed_output") or {}
        results[tag] = {
            "meta": {k: r[k] for k in ("status", "elapsed", "response_status", "usage")},
            "blue": score(p.get("blue_codes", []), a_truth),
            "red": score(p.get("red_codes", []), b_truth),
            "raw": r.get("raw_output_text"),
        }
    (OUT / "scores.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
