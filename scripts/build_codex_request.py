#!/usr/bin/env python3
"""Build a Codex backend request JSON from rendered page images."""

from __future__ import annotations

import argparse
import base64
import json
import uuid
from pathlib import Path


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ok", "found_markers", "missing_markers", "notes"],
    "properties": {
        "ok": {"type": "boolean"},
        "found_markers": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["marker", "surrounding_context"],
                "properties": {
                    "marker": {"type": "string"},
                    "surrounding_context": {"type": "string"},
                },
            },
        },
        "missing_markers": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--redacted-output", type=Path)
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--service-tier", default="priority")
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--detail", default="original")
    parser.add_argument("--prompt")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.render_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    pages = sorted(args.render_dir.glob("page-*.png"))
    if not pages:
        raise SystemExit(f"no page-*.png files in {args.render_dir}")

    source_tokens = manifest.get("source_tokens", "unknown")
    prompt = args.prompt or (
        f"These {len(pages)} no-margin dense square images contain exactly "
        f"{source_tokens:,} tokenizer tokens of public-domain prose rendered as "
        "reflowed text. Three needle markers are embedded. Read across all images "
        "and return all exact marker strings if visible."
        if isinstance(source_tokens, int)
        else f"These {len(pages)} images contain dense reflowed text. "
        "Three needle markers may be embedded. Return all exact marker strings if visible."
    )

    content = [{"type": "input_text", "text": prompt}]
    for page in pages:
        encoded = base64.b64encode(page.read_bytes()).decode("ascii")
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{encoded}",
                "detail": args.detail,
            }
        )

    body = {
        "model": args.model,
        "instructions": (
            "Return strict JSON only. Inspect the image text and extract the exact "
            "needle marker strings if visible. Do not invent missing markers."
        ),
        "input": [{"role": "user", "content": content}],
        "text": {
            "format": {
                "type": "json_schema",
                "strict": True,
                "name": "tokenfiche_probe",
                "schema": SCHEMA,
            }
        },
        "reasoning": {"effort": args.reasoning_effort},
        "stream": True,
        "include": ["reasoning.encrypted_content"],
        "tools": [],
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "store": False,
        "service_tier": args.service_tier,
        "prompt_cache_key": f"tokenfiche-{args.render_dir.name}-{uuid.uuid4()}",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(body, separators=(",", ":")))

    if args.redacted_output:
        redacted = json.loads(json.dumps(body))
        for item in redacted["input"][0]["content"]:
            if item.get("type") == "input_image":
                item["image_url"] = item["image_url"][:120] + "...<truncated>"
        args.redacted_output.parent.mkdir(parents=True, exist_ok=True)
        args.redacted_output.write_text(json.dumps(redacted, indent=2))

    print(
        json.dumps(
            {
                "output": str(args.output),
                "redacted_output": str(args.redacted_output) if args.redacted_output else None,
                "images": len(pages),
                "bytes": args.output.stat().st_size,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

