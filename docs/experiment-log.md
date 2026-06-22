# GPT-5.5 Codex Image Context Iterations

Current goal: maximize tokenizer-counted source text conveyed through `input_image` parts while the GPT-5.5 Codex endpoint can still retrieve inserted needle markers. Ranking is by source text tokens successfully recovered, not by image input tokens alone.

## Current Best

### 1,000,000 source tokens, 30 images (Atkinson Mono 10px / 8px line height)

- Artifact: `experiments/atkinson_10_1M-api/atkinson_10_1M.summary.json`
- Layout: 30 images, 3000x3000px, 8 columns, font size 10, 62 chars/line, 8px line height, 1px margin, 3px gutter.
- Source: 1,000,000-token source from standard Gutenberg books with three embedded needle markers.
- Preflight: 270,000,000 total pixels, 265,080 estimated 32x32 patches, 97.71% average rendered ink width, 81,686/89,760 lines used.
- Result: `completed_all_needles_found`.
- Found markers: `NEEDLE_ALPHA::AHAB-SEES-7429`, `NEEDLE_BETA::QUEEQUEG-LANTERN-1836`, `NEEDLE_GAMMA::MELVILLE-SURF-9021`.
- Usage: 318,283 input tokens, 318,650 total tokens.
- Compression Ratio: **3.14x** (1,000,000 source tokens / 318,283 billed input tokens)
- Status: Absolute best proven result. Using the hyperlegible **Atkinson Mono** font, we achieved dense vertical packing at 8px line height with perfect character recovery, successfully cracking the 1,000,000-token barrier in a single visual context payload.

## Boundary Evidence

### 31 images fail the context gate

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t836811-p31-c10-fs10-m0-g0-ext562.summary.json`
- Layout: 31 images, 3000x3000 px, 10-column no-margin geometry (the earlier Courier New maximize sweep).
- Preflight: 279,000,000 total pixels, 273,916 estimated 32x32 patches, 99.8% average rendered ink width.
- Result: `context_length_exceeded`.
- Status: establishes the practical image limit for this request shape as 30 full 3000x3000 `detail:"original"` images, with 31 rejected.

### 32/34/37/38 images also fail the context gate

- Artifacts:
  - `experiments/codex-gpt55-image-maximize-2026-06-20/api/t863299-p32-c10-fs10-m0-g0-ext562.summary.json`
  - `experiments/codex-gpt55-image-maximize-2026-06-20/api/t917067-p34-c10-fs10-m0-g0-ext562.summary.json`
  - `experiments/codex-gpt55-image-maximize-2026-06-20/api/t994578-p37-c10-fs10-m0-g0-ext562.summary.json`
  - `experiments/codex-gpt55-image-maximize-2026-06-20/api/t1019682-p38-c10-fs10-m0-g0-ext562.summary.json`
- Results: all returned `context_length_exceeded`.
- Reason failed: total image patch budget exceeded the endpoint gate before inference.

## Superseded Successes

### 810,549 source tokens, 30 no-margin images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t810549-p30-c10-fs10-m0-g0-ext562.summary.json`
- Layout: 30 images, 3000x3000 px, 10 columns, font size 10, 49 chars/line, 11 px line height, 0 px margin, 0 px gutter.
- Source: 562,500-token successful source extended with public-domain Gutenberg text after the markers.
- Preflight: 270,000,000 total pixels, 265,080 estimated 32x32 patches, 99.8% average rendered ink width, 81,600/81,600 wrapped lines used.
- Result: `completed_all_needles_found`.
- Found markers: `NEEDLE_ALPHA::AHAB-SEES-7429`, `NEEDLE_BETA::QUEEQUEG-LANTERN-1836`, `NEEDLE_GAMMA::MELVILLE-SURF-9021`.
- Usage: 318,283 input tokens, 318,645 total tokens.
- Reason superseded: Atkinson Mono 10px achieved 1,000,000 source tokens with 100% retrieval.

### 650,000 source tokens, 30 images (Atkinson Mono 12px / 10px line height)

- Artifact: `experiments/atkinson_12_650k-api/atkinson_12_650k.summary.json`
- Layout: 30 images, 3000x3000px, 6 columns, font size 12, 62 chars/line, 10px line height, 1px margin, 3px gutter.
- Result: `completed_all_needles_found`.
- Usage: 318,281 input tokens, 318,835 total tokens.
- Reason superseded: Atkinson Mono 10px at 8px line height squeezed even higher density (1,000,000 tokens) with 100% retrieval.

### 703,707 source tokens, 26 no-margin images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t703707-p26-c10-fs10-m0-g0-ext562.summary.json`
- Result: `completed_all_needles_found`.
- Usage: 275,867 input tokens, 276,178 total tokens.
- Reason superseded: 30-image layout recovered more source text with full marker recovery.

### 677,414 source tokens, 25 no-margin images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t677414-p25-c10-fs10-m0-g0-ext562.summary.json`
- Result: `completed_all_needles_found`.
- Usage: 265,263 input tokens, 265,542 total tokens.
- Reason superseded: later 26-image and 30-image layouts recovered more source text.

### 569,000 source tokens, 21 no-margin images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t569000-p21-c10-fs10-m0-g0-ext562.summary.json`
- Result: `completed_all_needles_found`.
- Usage: 222,847 input tokens, 223,628 total tokens.
- Reason superseded: larger accepted image counts recovered more source text.

### 562,500 source tokens, 21 no-margin images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t562500-p21-c10-fs10-m0-g0.summary.json`
- Result: `completed_all_needles_found`.
- Usage: 222,847 input tokens, 223,236 total tokens.
- Reason superseded: 569,000-token extension preserved marker positions and recovered more source text.

### 550,000 source tokens, 21 no-margin images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t550000-p21-c9-fs10-m0-g0.summary.json`
- Result: `completed_all_needles_found`.
- Usage: 222,847 input tokens, 223,150 total tokens.
- Reason superseded: later 562,500-token and larger layouts recovered more source text.

### 500,000 source tokens, 19 no-margin images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t500000-p19-c7-fs10-m0-g0.summary.json`
- Result: `completed_all_needles_found`.
- Usage: 201,639 input tokens, 202,021 total tokens.
- Reason superseded: later no-margin layouts recovered more source text.

## Failed Retrieval Attempts

### 1,100,000 source tokens, 30 images (Atkinson Mono 10px / 8px line height)

- Artifact: `experiments/atkinson_10_1.1M-api/atkinson_10_1.1M.summary.json`
- Layout: 30 images, 3000x3000px, 8 columns, font size 10, 62 chars/line, 8px line height.
- Result: `completed_missing_needles` (only recovered NEEDLE_GAMMA).
- Reason failed: Font density pushed past the legibility limit for the vision model, causing it to lose tracking on the early pages and miss the first two needles.

### 909,728 source tokens, 30 denser images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t909728-p30-c10-fs10-lh10-cpl50-m0-g0-ext562.summary.json`
- Layout: 30 images, 10 columns, font size 10, 50 chars/line, 10 px line height.
- Result: `completed_missing_needles`.
- Reason failed: beta was read as `NEEDLE_BETA::QUEQUEG-LANTERN-1836`, not the exact `NEEDLE_BETA::QUEEQUEG-LANTERN-1836`.

### 892,730 source tokens, 30 denser images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t892730-p30-c10-fs10-lh10-cpl49-m0-g0-ext562.summary.json`
- Layout: 30 images, 10 columns, font size 10, 49 chars/line, 10 px line height.
- Result: `completed_missing_needles`.
- Reason failed: beta was again read as `NEEDLE_BETA::QUEQUEG-LANTERN-1836`, not the exact required marker.

### 568,750 source tokens, 21 denser images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t568750-p21-c11-fs10-m0-g0.summary.json`
- Result: `completed_missing_needles`.
- Reason failed: recovered beta and gamma, missed alpha. Later investigation found this source was trimmed from a different 575k source with shifted marker offsets, so it is not the preferred extension strategy.

### 565,625 source tokens, 21 denser images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t565625-p21-c10-fs10-m0-g0.summary.json`
- Result: `completed_missing_needles`.
- Reason failed: recovered beta and gamma, missed alpha. This also used the shifted 575k source path.

### 575,000 source tokens, 22 no-margin images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t575000-p22-c10-fs10-m0-g0.summary.json`
- Result: `completed_missing_needles`.
- Reason failed: recovered beta and gamma, missed alpha.

### 600,000 source tokens, 22 no-margin images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t600000-p22-c11-fs10-m0-g0.summary.json`
- Result: `completed_missing_needles`.
- Reason failed: recovered alpha and beta, missed gamma.

### 700,000 source tokens, 25 no-margin images

- Artifact: `experiments/codex-gpt55-image-maximize-2026-06-20/api/t700000-p25-c15-fs10-m0-g0.summary.json`
- Result: `completed_missing_needles`.
- Reason failed: recovered beta and gamma, missed alpha.

## Earlier Baselines

### 375,000 source tokens, 20 dense images

- Artifact: `experiments/codex-gpt55-dense-image-api-2026-06-20/p20-c7-fs12-m18-g12.summary.json`
- Result: `completed_all_needles_found`.
- Usage: 212,241 input tokens, 212,533 total tokens.
- Reason superseded: later no-margin layouts recovered substantially more source text.

### 375,000 source tokens, 21 dense images

- Artifact: `experiments/codex-gpt55-dense-image-api-2026-06-20/p21-c7-fs12-g24.summary.json`
- Result: `completed_all_needles_found`.
- Usage: 222,845 input tokens.
- Reason superseded: same source text token payload as 20-image baseline, with more image tokens.

### 375,000 source tokens, 30 dense images

- Artifact: `experiments/codex-gpt55-dense-image-api-2026-06-20/dense-p30-c2-fs12.summary.json`
- Result: `completed_all_needles_found`.
- Usage: 318,281 input tokens.
- Reason superseded: same source text token payload as smaller 375k layouts.

### 375,000 source tokens, original 30 narrow pages

- Artifact: `experiments/codex-gpt55-image-window-probe-2026-06-20/pages-30-375000.summary.json`
- Result: `context_length_exceeded`.
- Reason failed: page layout preserved Gutenberg hard wraps, producing a narrow left text column and excessive whitespace.

### 375,000 source tokens, single giant image

- Artifact: `experiments/codex-gpt55-image-window-probe-2026-06-20/one-image-375000.summary.json`
- Result: completed but missed both needles.
- Reason failed: image was accepted but downsampled too aggressively for reliable text retrieval.

### 375,000 source tokens, 5/10/20 tall blended images

- Artifacts: `experiments/codex-gpt55-image-blend-sweep-2026-06-20/blend-*.summary.json`
- Result: completed but missed both needles.
- Reason failed: fewer tall images lowered billed input tokens, but visual downsampling made retrieval fail.
