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

Runtime caveat: DSPy wraps the prompt in its own message formatting (JSON adapter,
field markers), so its "root" score on gold differs from the production runtime's root
score. Each optimizer is therefore compared against root *within its own runtime*, and
the deployability difference is part of the result: the gym loop optimizes the actual
production system prompt; GEPA optimizes a DSPy program that would require porting.

## Results

| | root on gold | optimized on gold | delta | critical-field regressions |
|---|---|---|---|---|
| gym loop (run1) | 0.8920 | no candidate accepted | +0.0000 | n/a: 12/12 candidates REJECTED by gate |
| DSPy GEPA (light) | TBD | TBD | TBD | TBD (gym gate applied post-hoc) |

### What the gym loop did (run1, 3 generations, 12 candidates, $4.16)

Every candidate improved or held the pressure suite (up to +0.0084) while regressing
critical gold fields, coffee.variety and price.listed_price systematically. The gate
rejected all 12: a documented NOOP. The loop's value in this run is what it *prevented*:
generation 1's best candidate looked +0.8% better on the visible metric and silently
broke price extraction on real pages.

### What GEPA did

TBD after run completes.

## Reading

The claim under test is not "our search beats GEPA's search." It is that any optimizer,
GEPA included, needs this referee: variance-aware gates over a frozen human-verified
gold set with critical-field regression blocking. GEPA's own acceptance criterion is its
metric on its own validation split; whether its winner survives the gym's gate is
exactly the deployment question the harness exists to answer.
