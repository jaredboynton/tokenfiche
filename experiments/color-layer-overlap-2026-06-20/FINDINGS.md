# Color-layer overlap: can two text layers share the same patches?

Hypothesis (user): render one text in blue, another in red, purple where they
intersect; a vision model separates by color and reads BOTH, doubling source
tokens at the same patch cost.

## Result: no. Overlap destroys retrieval (100% -> 0-12%).

Tested on the real target, GPT-5.5 via the Codex backend, `detail:"original"`
(native 32x32 patches, no downscale), `reasoning.effort=medium`. Each layer
carried 8 high-entropy codes (`PREFIX::GGGG-GGGG-GGGG-GGGG`, alphabet A-Z + 2-9,
unguessable). Inter SemiBold 18px, 2400x3000 page, 3 columns. Metric: exact code
recovery. Raw scores in `scores.json`, SSE transcripts in `probe_*.sse`.

| Variant | Encoding | Codes recovered |
|---|---|---|
| single_blue_baseline | one layer, blue text on white | 7-8 / 8 (~100%) |
| stereo_overlay | blue 50% + red 50% over white (user's spec) | 0 / 16 |
| chan_overlap | pure-channel blue(0,0,255)/red(255,0,0), magenta overlap, zero crosstalk | 0 / 16 |
| chan_offset | channel-separated, red shifted half a line down | 2 / 16 |

The single layer at this font is trivially perfect. Stacking a second layer in
the same pixels takes it to zero. The maximally separable encoding (each layer in
its own RGB channel, no crosstalk) does no better than the washed 50/50 blend at
full overlap. A half-line offset is the only variant that recovered anything (2/16).

## Why it fails

1. **Overlapping glyphs are physically ambiguous.** Where a blue stroke and a red
   stroke cross, the pixel is magenta and belongs to both letters. Reading either
   layer means reconstructing two occluded glyph shapes from fragments. Color
   labels the fragments; it does not un-occlude them.
2. **The model cannot bind fragments to the right layer.** In `chan_offset` it
   returned 12 codes but put 6 in the WRONG color bucket (AX codes tagged red, BY
   codes tagged blue), on top of character errors (`BY0`->`BYO`, `LS5X`->`L55X`,
   `WWRN`->`WWWN`). Partial legibility did not become layer separation.
3. **Patch resolution is already near the OCR edge.** At 18px a single layer sits
   close to the limit; doubling the ink in the same 32px patches pushes it past.

## The patch-budget point is real but moot

Patches are spatial 32x32 tiles, channel-agnostic: an RGB 3000x3000 page costs the
same 8836 patches as grayscale (verified: `ceil(3000/32)^2 = 8836` for both). So IF
color separation worked, the second layer would be free under Gate 1. It does not
work, so the free-second-layer upside never materializes. Color overlap trades the
existing ~100% single-layer retrieval for ~0%; it is strictly worse than the
density lever the project already uses (one legible layer, small font, zero margins
-> 2.55x source-to-billed tokens at full retrieval).

## Caveat / untested crossover

Not tested: very large glyphs (e.g. 30px+) where overlap might separate. But to make
overlap legible you must enlarge glyphs, which gives back more page area than the 2x
you bought -> net-negative density. The lever that works is "one layer, maximally
dense," not "two layers stacked."
