# Benchmark: extraction-gym loop vs DSPy GEPA, same referee

Two optimizers, one deterministic referee: the frozen, human-verified gold set v1
(42 real pages, residual label error 0.159 stated in MANIFEST.json), scored by the
gym's deterministic per-field scorers with value-critical weighting.

## Fairness contract

| dimension | gym loop | DSPy GEPA |
|---|---|---|
| starting prompt | root artifact ce68bd4c4e | same text, as signature instructions |
| model under test | gpt-4o-mini | gpt-4o-mini |
| frontier model | gpt-5.5 (mutation) | gpt-5.5 (reflection) |
| training signal | adversarial pressure suite only | same suite only (train/val split) |
| gold access during search | none (aggregate gate scores only) | none |
| referee | gym scorers on frozen gold v1 | identical |

## Results

| configuration | gold composite | vs production root | gate verdict |
|---|---|---|---|
| root prompt, production runtime | **0.8920** | baseline | (incumbent) |
| root prompt, DSPy runtime | 0.8537 | -0.0383 | n/a (runtime tax) |
| GEPA-optimized, DSPy runtime | 0.8754 | -0.0166 | n/a |
| GEPA-optimized, transplanted to production | 0.8923 | +0.0003 | **FAIL** |
| gym loop best candidate (run1, 12 tried) | 0.8975 | +0.0055 | **FAIL** (all 12) |

GEPA run: auto=light, 412 rollouts, 26 iterations. Gym run1: 3 generations, 12
candidates, $4.16.

## The three findings

**1. GEPA works on its own terms, and that is precisely the problem.** Within the DSPy
runtime, GEPA improved gold composite by +0.0217 over its own baseline, and its internal
selection metric rated its winning program 0.9703 on the pressure-suite split. Deployed
into the production runtime, that same winner scores 0.8923: +0.0003 over the incumbent,
a bootstrap CI of (-0.020, +0.018) that brackets zero, and four critical-field
regressions (page_type 0.976 -> 0.929, process_method 0.920 -> 0.875, variety
0.948 -> 0.875, package_grams 0.950 -> 0.925). GEPA's own acceptance criterion would
have shipped it; the gym's gate refuses it.

**2. The runtime is part of the program.** The identical root prompt scores 0.8920 in
the production runtime and 0.8537 through DSPy's adapter formatting: a -3.8 point
runtime tax that exceeds everything GEPA's optimization earned back (+2.2). An optimizer
that requires adopting its runtime must first pay for its runtime.

**3. Both optimizers fail the same honest exam, in the same way.** The gym's own loop
proposed 12 candidates; all improved or held the adversarial suite and all regressed
critical gold fields (variety, listed_price systematically). GEPA's winner shows the
same signature (variety, package_grams, process_method). Against a strong hand-written
root prompt, with a mini-class model under test, automated prompt search reliably finds
candidates that look better on the visible metric and silently break value-critical
fields on real pages. The scarce artifact is not a better search algorithm; it is a
referee that cannot be fooled: frozen human-verified gold, variance-aware thresholds,
critical-field regression blocking, and a prompt-length cap (GEPA's winner is 17,459
chars, 3.0x root; the gym gate would refuse it on length alone before reading a single
score).

## Costs

Root baseline + noise band: ~$0.8. Gym run1: $4.16. GEPA (incl. one killed partial run,
disk-cache resume): ~$8-12 est. Transplant eval: ~$0.2. All within the $80 session cap.

## Reproduce

```text
gym eval ce68bd4c4e                # baseline
gym noise ce68bd4c4e --n 3         # noise band
gym loop --run-id run1 --target ce68bd4c4e --noise runs/noise-...json
gym gepa --root ce68bd4c4e --auto light
python scripts/gepa_transplant.py  # transplant + gated verdict
```
