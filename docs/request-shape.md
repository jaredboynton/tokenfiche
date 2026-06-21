# Request Shape Notes

The successful probes used the ChatGPT Codex backend endpoint:

```text
https://chatgpt.com/backend-api/codex/responses
```

The request body follows the Responses API shape closely enough to use `input_text`, `input_image`, `text.format`, `reasoning`, `service_tier`, and streaming. The endpoint is not the public platform Responses endpoint, so treat this as an observed request shape, not a published contract.

The successful request used:

```json
{
  "model": "gpt-5.5",
  "reasoning": { "effort": "low" },
  "service_tier": "priority",
  "stream": true,
  "include": ["reasoning.encrypted_content"],
  "tools": [],
  "tool_choice": "auto",
  "parallel_tool_calls": false,
  "store": false
}
```

Each page image was sent as:

```json
{
  "type": "input_image",
  "image_url": "data:image/png;base64,...",
  "detail": "original"
}
```

Headers used by the probes:

```text
Authorization: Bearer <access token>
ChatGPT-Account-Id: <account id>
originator: codex_cli_rs
User-Agent: codex_cli_rs/0.142.0-alpha.7 (Mac OS 15.7.3; arm64) reqwest/0.12.28
Accept: text/event-stream
Content-Type: application/json
session-id: <uuid>
thread-id: <uuid>
x-client-request-id: <uuid>
x-codex-installation-id: <uuid>
x-codex-window-id: <uuid>
```

`scripts/send_codex_request.py` recreates this without writing auth headers to disk.

## Observed Limits

For 3000x3000 `detail:"original"` PNG pages:

- 30 images succeeded.
- 31 images failed with `context_length_exceeded`.
- The successful 30-image request reported 318,283 input tokens.
- The failed 31-image request reached the context gate before returning usage.

The image path can exceed the nominal 272k window seen in some capability metadata, but it did not reach the advertised 400k context limit for this page size. The practical bracket from this run is 270M pixels accepted and 279M pixels rejected.
