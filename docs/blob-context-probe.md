# Codex GPT-5.5 Blob Context Probe

Date: 2026-06-20

Question: can the ChatGPT Codex Responses endpoint for `gpt-5.5` use more than the normal `context_window` if the payload is sent as `input_file` or disguised as an image instead of `input_text`?

Conclusion: no, not in the tested Codex endpoint/client-version combination. `input_file` is accepted and readable, but it fails at the same practical context boundary as text. The 375k-target `input_file` request failed with `context_length_exceeded`.

## Sources

- Live artifacts: `experiments/codex-gpt55-blob-context-probe-2026-06-20/`
- OpenAI file-input docs: https://developers.openai.com/api/docs/guides/file-inputs
- Responses create reference: https://developers.openai.com/api/reference/resources/responses/methods/create
- Codex model metadata type: https://github.com/openai/codex/blob/main/codex-rs/protocol/src/openai_models.rs
- Codex Responses request type: https://github.com/openai/codex/blob/main/codex-rs/codex-api/src/common.rs
- Codex content item type: https://github.com/openai/codex/blob/main/codex-rs/protocol/src/models.rs

## Capability Snapshot

Artifact: `experiments/codex-gpt55-blob-context-probe-2026-06-20/models-summary.json`

Using `client_version=0.142.0-alpha.7`, the live Codex models endpoint returned:

| Model | `context_window` | `max_context_window` | Input modalities |
|---|---:|---:|---|
| `gpt-5.5` | 272,000 | 272,000 | `text`, `image` |
| `gpt-5.4` | 272,000 | 1,000,000 | `text`, `image` |

I did not reproduce a live `gpt-5.5` `max_context_window` of 400,000 with the current local Codex client version.

## Accepted Shapes

Artifact: `experiments/codex-gpt55-blob-context-probe-2026-06-20/probe-summary.json`

| Probe | Result | Evidence |
|---|---|---|
| `input_text` | Accepted | Completed and returned the marker. |
| `input_file` with `data:text/plain;base64,...` | Accepted | Completed and returned the marker. |
| `input_file` with raw base64 only | Rejected | HTTP 400. |

This matches the OpenAI file-input docs: Base64 file inputs are sent as `input_file` with `file_data` as a data URL.

## Token Accounting

Artifact: `experiments/codex-gpt55-blob-context-probe-2026-06-20/size-probe-summary.json`

The same 20k-word payload was visible and token-accounted almost identically:

| Probe | Input tokens | Result |
|---|---:|---|
| `text-20000w` | 60,112 | Completed |
| `file-20000w` | 60,120 | Completed |

## Window Boundary

Artifacts:

- `experiments/codex-gpt55-blob-context-probe-2026-06-20/threshold-probe-summary.json`
- `experiments/codex-gpt55-blob-context-probe-2026-06-20/target-375k-probe-summary.json`

Both text and `input_file` worked below the advertised `context_window` and failed above it:

| Probe | Estimated/observed input size | Result |
|---|---:|---|
| `text-85000w` | 255,105 observed input tokens | Completed |
| `file-85000w` | 255,113 observed input tokens | Completed |
| `text-100000w` | above 272k by calibration | `context_length_exceeded` |
| `file-100000w` | above 272k by calibration | `context_length_exceeded` |
| `target-375k-text-125000w` | ~375,154 calibrated input tokens | `context_length_exceeded` |
| `target-375k-file-125000w` | ~375,154 calibrated input tokens | `context_length_exceeded` |

The decisive 375k-target error for both request shapes was:

```text
Your input exceeds the context window of this model. Please adjust your input and try again.
```

## Image/Base64 Text Probe

Artifacts:

- `experiments/codex-gpt55-blob-context-probe-2026-06-20/image-base64-text-probe-summary.json`
- `experiments/codex-gpt55-blob-context-probe-2026-06-20/valid-input-image-marker-summary.json`

Sending base64 text bytes as `input_image` did not reach model inference:

| Probe | Result | Error |
|---|---|---|
| `data:image/png;base64,<text bytes>` | HTTP 400 | The bytes did not represent a valid image. |
| `data:text/plain;base64,<text bytes>` | HTTP 400 | `input_image` requires an image MIME type. |

This was a probe bug, not evidence that `input_image` itself is unusable.
Exa and Octocode examples both show that `input_image.image_url` must be a data
URL containing valid encoded image bytes, such as
`data:image/png;base64,<png bytes>`, not arbitrary base64 text with an image MIME
label. The official Python SDK type also describes `image_url` as a URL or
base64 encoded image in a data URL.

Fixed probe:

| Probe | Result | Input tokens | Evidence |
|---|---|---:|---|
| Valid PNG with rendered marker text | Completed | 1,044 | The model returned `VALID_IMAGE_MARKER_828EBEA2DB`. |

## Implication

For this harness, do not change the Codex `gpt-5.5` request path to use `input_file` as a context-window bypass. It can carry text files, but the extracted text appears to consume the same model context and is rejected above the same boundary.
