#!/usr/bin/env python3
"""Send a Codex backend request and summarize the streaming result."""

from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_URL = "https://chatgpt.com/backend-api/codex/responses"


def decode_account_id(id_token: str) -> str | None:
    parts = id_token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None
    return data.get("chatgpt_account_id")


def load_auth(auth_file: Path) -> tuple[str, str | None]:
    access = os.environ.get("CODEX_ACCESS_TOKEN")
    account = os.environ.get("CHATGPT_ACCOUNT_ID")
    if access:
        return access, account

    data = json.loads(auth_file.read_text())
    tokens = data.get("tokens") or data
    access = tokens.get("access_token") or data.get("access_token")
    account = account or tokens.get("account_id") or data.get("account_id")
    if not account:
        account = decode_account_id(tokens.get("id_token") or data.get("id_token") or "")
    if not access:
        raise SystemExit("missing auth: set CODEX_ACCESS_TOKEN or provide ~/.codex/auth.json")
    return access, account


def parse_sse(text: str, manifest: dict[str, Any]) -> dict[str, Any]:
    status = None
    usage = None
    error = None
    output_text = ""
    events = 0

    for raw in text.splitlines():
        if not raw.startswith("data: "):
            continue
        data = raw[6:]
        if data == "[DONE]":
            continue
        events += 1
        try:
            obj = json.loads(data)
        except json.JSONDecodeError:
            continue
        event_type = obj.get("type")
        if event_type == "response.completed":
            response = obj.get("response") or {}
            status = response.get("status")
            usage = response.get("usage")
            for output in response.get("output") or []:
                for content in output.get("content") or []:
                    if content.get("type") in ("output_text", "text"):
                        output_text += content.get("text", "")
        elif event_type == "response.output_text.delta":
            output_text += obj.get("delta", "")
        elif event_type == "response.failed":
            response = obj.get("response") or {}
            status = response.get("status")
            error = response.get("error") or obj.get("error")
        elif event_type == "error":
            error = obj

    parsed = None
    if output_text:
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError:
            parsed = None

    expected = [item["marker"] for item in manifest.get("markers", []) if "marker" in item]
    found: list[str] = []
    if isinstance(parsed, dict):
        for item in parsed.get("found_markers") or []:
            if isinstance(item, dict) and item.get("marker"):
                found.append(item["marker"])

    missing = [marker for marker in expected if marker not in found]
    if error:
        classification = "errored"
    elif status == "failed":
        classification = "failed"
    else:
        classification = "completed_missing_needles" if missing else "completed_all_needles_found"

    return {
        "event_count": events,
        "response_status": status,
        "usage": usage,
        "error": error,
        "classification": classification,
        "expected_markers": expected,
        "found_marker_strings": found,
        "missing_marker_strings": missing,
        "output_text": output_text,
        "parsed_output": parsed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--auth-file", type=Path, default=Path.home() / ".codex" / "auth.json")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--name")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    name = args.name or args.request.stem.replace(".request", "")
    manifest = json.loads(args.manifest.read_text()) if args.manifest else {}
    access, account = load_auth(args.auth_file)
    body = args.request.read_bytes()

    headers = {
        "Authorization": f"Bearer {access}",
        "originator": "codex_cli_rs",
        "User-Agent": "codex_cli_rs/0.142.0-alpha.7 (Mac OS 15.7.3; arm64) reqwest/0.12.28",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "session-id": str(uuid.uuid4()),
        "thread-id": str(uuid.uuid4()),
        "x-client-request-id": str(uuid.uuid4()),
        "x-codex-installation-id": str(uuid.uuid4()),
        "x-codex-window-id": str(uuid.uuid4()),
    }
    if account:
        headers["ChatGPT-Account-Id"] = account

    request = urllib.request.Request(args.url, data=body, headers=headers, method="POST")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    headers_path = args.out_dir / f"{name}.headers.txt"
    sse_path = args.out_dir / f"{name}.sse"
    summary_path = args.out_dir / f"{name}.summary.json"

    start = time.time()
    status_line = ""
    try:
        context = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=args.timeout, context=context) as response:
            status_line = f"HTTP/{response.version / 10:.1f} {response.status} {response.reason}"
            headers_path.write_text(str(response.headers))
            payload = response.read()
    except urllib.error.HTTPError as exc:
        status_line = f"HTTP error {exc.code} {exc.reason}"
        headers_path.write_text(str(exc.headers))
        payload = exc.read()

    elapsed = round(time.time() - start, 3)
    text = payload.decode("utf-8", errors="replace")
    sse_path.write_text(text)
    parsed = parse_sse(text, manifest)

    summary = {
        "name": name,
        "layout_manifest": str(args.manifest) if args.manifest else None,
        "source_tokens": manifest.get("source_tokens"),
        "page_count": (manifest.get("layout") or {}).get("page_count"),
        "columns": (manifest.get("layout") or {}).get("columns"),
        "font_size": (manifest.get("layout") or {}).get("font_size"),
        "line_height": (manifest.get("layout") or {}).get("line_height"),
        "chars_per_line": (manifest.get("layout") or {}).get("chars_per_line"),
        "line_count": manifest.get("line_count"),
        "capacity": manifest.get("capacity"),
        "pixels": manifest.get("pixels"),
        "estimated_total_patches": manifest.get("estimated_total_patches"),
        "http_status_line": status_line,
        "elapsed_seconds": elapsed,
        "request_bytes": len(body),
        **parsed,
    }
    summary_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if summary["classification"] == "completed_all_needles_found" else 2


if __name__ == "__main__":
    raise SystemExit(main())

