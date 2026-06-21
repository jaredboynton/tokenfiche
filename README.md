# tokenfiche

**A picture is worth a thousand words. We made each one worth about 27,000 tokens, and GPT-5.5 read them back.**

What is a token, really? A model's text window stops at a hard number, 272,000 tokens for GPT-5.5 through the Codex endpoint. So we asked a simple question: if you render the text as images instead of sending it as text, does that number still apply? The vision path reads pixels, and pixels are cheap. How much text can you actually get a model to read by photographing it?

The answer, for this one proven run: **810,549 tokens of source text, packed into 30 page images, every fact recovered exactly.** That is 2.5 tokens of source text carried for every input token the API billed.

## TL;DR

We took 810,549 tokenizer-counted tokens of text (the source is Herman Melville, fittingly), hid three exact "needle" markers inside it, rendered the whole thing as 30 dense grayscale page images, and sent the images to GPT-5.5. The model found all three needles, character for character.

| Metric | Value |
| --- | --- |
| Source text rendered | **810,549 tokens** |
| Page images | **30** (3000x3000 px) |
| Source tokens per image | ~27,000 |
| Billed input tokens | **318,283** |
| Source-to-billed ratio | **2.55x** |
| Needles recovered | **3 / 3 exact** |
| One image more (31) | rejected: `context_length_exceeded` |

Evidence: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t810549-p30-c10-fs10-m0-g0-ext562.summary.json`.

This is the vision path used as a lossy, OCR-like transport layer. Images carry far more source text than the text window would normally hold, as long as the text is rendered densely, legibly, and verified with retrieval probes.

## The two gates

The interesting result is that "the endpoint accepted it" and "the model read it correctly" are two separate things, and they fail for different reasons.

**Gate 1, the context gate, counts image patches.** The endpoint slices each 3000x3000 image into 32x32 patches: 94 x 94 = 8,836 patches per page. The context limit is enforced on that patch count, near 272,000, and the billed `input_tokens` figure (318,283) is a separate billing number that is allowed to exceed it. The boundary is clean:

| Pages | Patches | Result |
| --- | --- | --- |
| 30 | 265,080 | accepted |
| 31 | 273,916 | `context_length_exceeded` |

272,000 sits exactly between them. Thirty pages is the wall for this page size. Evidence: `...api/t836811-p31-...summary.json`.

**Gate 2, the retrieval gate, is OCR.** Passing the context gate only means the bytes fit. The model still has to read pixels. We pushed denser 30-image layouts to 892k and 909k source tokens, and they were accepted and completed, but the model misread the beta needle:

```text
expected: NEEDLE_BETA::QUEEQUEG-LANTERN-1836
got:      NEEDLE_BETA::QUEQUEG-LANTERN-1836
```

One dropped `E`. That run does not count. A configuration is only a success if it passes the retrieval task you actually care about. Evidence: `docs/experiment-log.md` "Failed Retrieval Attempts."

## How it works

Four scripts, run in order:

```text
render_token_images.py   text -> dense page PNGs + manifest
build_codex_request.py   PNGs -> base64 Codex request with a strict-JSON output schema
send_codex_request.py    request -> SSE stream -> classified summary
verify_repo.py           sanity-check the packaged evidence
```

The renderer trims text to an exact token budget with tiktoken, inserts the three needle markers at 20% / 50% / 90% offsets, reflows paragraphs, and packs them into multi-column pages. It computes layout capacity and fails preflight if the text would overflow, so you never pay for an image that dropped characters off the page.

The winning layout is intentionally plain:

- 3000x3000 grayscale PNG pages
- 10 columns, 0 px margins, 0 px gutters
- Courier New at 10 px, 49 characters per line, 11 px line height
- 30 pages, 81,600 wrapped lines, 99.8% average rendered ink width

The zero-margin part is the whole trick. Early attempts preserved Project Gutenberg's hard wraps, which left text in a narrow strip down the left side and wasted most of the page. Reflowing first is what turned 375k tokens of wasted whitespace into 810k tokens of dense, readable text.

## Reproduce it

You need `uv`. Nothing else installs globally.

Verify the packaged evidence:

```bash
uv run --with pillow --with tiktoken python scripts/verify_repo.py
```

Re-render the proven best source:

```bash
uv run --with pillow --with tiktoken python scripts/render_token_images.py \
  --source-text experiments/codex-gpt55-image-maximize-2026-06-20/t810549-p30-c10-fs10-m0-g0-ext562/source-810549-tokens.txt \
  --target-tokens 810549 \
  --pages 30 --columns 10 --font-size 10 \
  --chars-per-line 49 --line-height 11 \
  --out runs/repro-810549
```

Build the request, then send it with your Codex auth:

```bash
python scripts/build_codex_request.py \
  --render-dir runs/repro-810549 \
  --output runs/repro-810549.request.json \
  --redacted-output runs/repro-810549.request.redacted.json

python scripts/send_codex_request.py \
  --request runs/repro-810549.request.json \
  --manifest runs/repro-810549/manifest.json \
  --out-dir runs/repro-810549-api
```

`send_codex_request.py` reads `~/.codex/auth.json` by default, or accepts `CODEX_ACCESS_TOKEN` and `CHATGPT_ACCOUNT_ID`.

## When this is worth it

Good fits:

- Long-document triage where finding anchored evidence matters more than perfect transcription.
- Retrieval evals with inserted needles across huge payloads.
- Agent-memory or compaction experiments comparing text transport against image transport.
- Stress-testing multimodal context windows and billing behavior.

Bad fits:

- Anything where one wrong character is dangerous.
- Legal, medical, or financial work without a second verifier.
- Code execution or patch generation from image text.
- Private data, unless you are comfortable with the endpoint and its retention behavior.

## Repo map

```text
scripts/render_token_images.py   render source text into page PNGs
scripts/build_codex_request.py   build a Responses-style Codex request body
scripts/send_codex_request.py    send the request and summarize the SSE result
scripts/verify_repo.py           check the packaged evidence and scripts
docs/experiment-log.md           best result first, then superseded and failed runs
docs/request-shape.md            observed Codex request shape and limits
docs/blob-context-probe.md       earlier blob / base64 / image probes
experiments/                     preserved summaries and the best run's images
examples/gutenberg-cache/        public-domain source texts
```

## Status

This is an experiment package, not an official SDK. The Codex endpoint, headers, model behavior, and limits can change. Treat the numbers here as grounded evidence for the recorded run, not a contract. Always test with needles, always inspect the marker crops, and only trust a layout that passes the retrieval task you actually care about.
