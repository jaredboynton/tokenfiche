# token-image-compaction

Turn a very large text payload into readable page images, send those images to a multimodal model, and check whether the model can still pull exact facts back out.

This repo packages the experiment where GPT-5.5 through the Codex endpoint recovered three exact needle markers from **810,549 tokenizer-counted source tokens** rendered into **30 full-page images**. The same request shape failed at 31 images with `context_length_exceeded`, so the current proven limit for 3000x3000 `detail:"original"` pages is:

- **30 images**
- **270,000,000 total pixels**
- **265,080 estimated 32x32 image patches**
- **318,283 billed input tokens**
- **810,549 source-text tokens recovered with all needles found**

The short version: images can carry much more source text than the text window would normally allow, but only if the text is rendered densely, legibly, and tested with retrieval probes. This is not magic compression. It is using the vision path as a lossy, OCR-like transport layer.

## What This Enables

This is useful when you need a model to look across more text than a text-only prompt can hold, and the task can tolerate visual/OCR-style risk.

Good fits:

- Long-document triage where exact phrasing matters less than finding anchored evidence.
- Retrieval evals with inserted needles across huge payloads.
- Agent memory or compaction experiments where you want to compare text transport versus image transport.
- Shipping a giant static context snapshot to a model that can read page images.
- Stress-testing multimodal context windows and billing behavior.

Bad fits:

- Anything where one character wrong is dangerous.
- Legal, medical, or financial workflows without a second verifier.
- Code execution or patch generation from image text.
- Private data experiments unless you are comfortable with the endpoint and retention behavior you are using.

## Proven Result

The best run is preserved here:

```text
experiments/codex-gpt55-image-maximize-2026-06-20/
```

Key files:

```text
experiments/codex-gpt55-image-maximize-2026-06-20/t810549-p30-c10-fs10-m0-g0-ext562/
experiments/codex-gpt55-image-maximize-2026-06-20/api/t810549-p30-c10-fs10-m0-g0-ext562.summary.json
experiments/codex-gpt55-image-maximize-2026-06-20/api/t836811-p31-c10-fs10-m0-g0-ext562.summary.json
docs/experiment-log.md
```

The 810,549-token run succeeded. The 836,811-token / 31-image run failed with `context_length_exceeded`. Dense 30-image variants that tried to pack around 890k to 910k source tokens completed, but misread the beta needle, so they do not count as successful exact retrieval.

## Quick Start

Use `uv` so you do not have to install anything globally:

```bash
uv run --with pillow --with tiktoken python scripts/verify_repo.py
```

Render the preserved best source again:

```bash
uv run --with pillow --with tiktoken python scripts/render_token_images.py \
  --source-text experiments/codex-gpt55-image-maximize-2026-06-20/t810549-p30-c10-fs10-m0-g0-ext562/source-810549-tokens.txt \
  --target-tokens 810549 \
  --pages 30 \
  --columns 10 \
  --font-size 10 \
  --chars-per-line 49 \
  --line-height 11 \
  --out runs/repro-810549
```

Build a Codex request body from those images:

```bash
python scripts/build_codex_request.py \
  --render-dir runs/repro-810549 \
  --output runs/repro-810549.request.json \
  --redacted-output runs/repro-810549.request.redacted.json
```

Send it with your local Codex auth:

```bash
python scripts/send_codex_request.py \
  --request runs/repro-810549.request.json \
  --manifest runs/repro-810549/manifest.json \
  --out-dir runs/repro-810549-api
```

`send_codex_request.py` reads `~/.codex/auth.json` by default, or you can provide `CODEX_ACCESS_TOKEN` and `CHATGPT_ACCOUNT_ID`.

## Layout Notes

The winning layout is intentionally plain:

- 3000x3000 grayscale PNG pages.
- 10 columns per page.
- 0 px margins and 0 px gutters.
- Courier New at 10 px.
- 49 characters per line.
- 11 px line height.
- 30 pages.

The no-margin part matters. Earlier attempts wasted space by preserving Gutenberg hard wraps, which made text appear as a narrow strip on the left side of the image. The renderer in this repo reflows paragraphs before wrapping, measures the rendered ink box, and writes marker crops so you can inspect whether the result is actually legible before paying for an API call.

## A Note On Reliability

The model can read a lot from these pages, but it is still reading pixels. We saw two dense 30-image variants complete while misreading:

```text
NEEDLE_BETA::QUEEQUEG-LANTERN-1836
```

as:

```text
NEEDLE_BETA::QUEQUEG-LANTERN-1836
```

That is why the scripts and docs treat "accepted by the endpoint" and "usable by the model" as different outcomes. Always test with needles, always inspect crops, and only trust configurations that pass the retrieval task you actually care about.

## Repo Map

```text
scripts/render_token_images.py       render source text into page PNGs
scripts/build_codex_request.py       build a Responses-style Codex request body
scripts/send_codex_request.py        send the request and summarize the SSE result
scripts/verify_repo.py               check the packaged evidence and scripts
docs/experiment-log.md               best result first, then superseded and failed runs
docs/blob-context-probe.md           notes from earlier blob/base64/image probes
experiments/                         preserved experiment summaries and best images
examples/gutenberg-cache/            public-domain source texts used in the run
```

## Status

This is an experiment package, not an official SDK. The Codex endpoint, headers, model behavior, and limits can change. Treat the included numbers as grounded evidence for the recorded run, not a contract.
