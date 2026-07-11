# I let three prompt optimizers improve my production prompt. All three declared victory. All three were wrong.

*(Draft for HN / blog. Numbers below are reproducible from the
[extraction-gym](https://github.com/jintaili/extraction-gym) repo; every result named
here is a committed artifact.)*

I run a small production app that extracts structured data (origin, variety, process,
price, package size) from specialty-coffee product pages. The extraction prompt is the
kind of thing prompt optimizers are supposed to improve automatically. So I tested
three of them - DSPy's GEPA, DSPy's MIPROv2, and my own adversarial mutation loop -
under one rule: the optimizer never gets to grade its own homework.

## The referee

The core of the project is not the optimizers. It is the referee they all had to face:

- **A frozen gold set of 42 real product pages** with human-verified labels. Not
  "human-glanced-at": two models pre-labeled every page, I cold-labeled a random audit
  sample before seeing any model output, and every disagreement was arbitrated against
  the frozen page text under written rules. The gold set ships with its own measured
  error rate (15.9% of audited fields changed between my cold pass and the final
  adjudication - most of that from labeling rules that were written mid-process).
- **Deterministic scorers.** No LLM anywhere in the grading path.
- **A measured noise band.** The same prompt evaluated three times varies; improvements
  must beat 2x that measured variance, not just be positive.
- **Critical-field vetoes.** A candidate that improves the average but regresses price
  or variety extraction is rejected regardless.
- **Cryptographic ship-gating.** The production repo's CI asserts that the deployed
  prompt's bytes match a registered artifact with a passing verdict. You cannot edit
  the prompt without re-earning the attestation.

Two numbers from building the gold set that shaped everything after: when my two
pre-labeling models *agreed* with each other, they were still jointly wrong on **8.5%**
of fields. And when they disagreed, the correct answer was *neither* of them 31 times
out of 56. That is why the referee is human-verified.

## The result

![what each optimizer believed vs what deployment measured](../reports/optimizer-gap-chart.png)

| optimizer | its own score for its winner | deployed reality (frozen gold, production runtime) | verdict |
|---|---|---|---|
| my loop (best of 12 candidates) | 0.955 | 0.898 (+0.006 vs incumbent) | rejected |
| GEPA | 0.970 | 0.892 (+0.0003) | rejected |
| MIPROv2 | 0.951 | 0.859 (**-3.3 points**) | rejected |

Three findings:

**1. Every optimizer overestimated itself, and one would have shipped a regression.**
GEPA's internal metric rated its winner 0.970. Deployed into the production runtime,
that winner was +0.0003 over the incumbent - statistically nothing - with four
critical-field regressions. MIPROv2's winner scored 0.951 by its own accounting and
*regressed production by 3.3 points*. If the acceptance criterion had been "the
optimizer's metric went up" - which is the default in every tutorial - both would have
shipped.

**2. The runtime is part of the program.** The identical prompt scores 0.892 in my
production runtime and 0.854 through DSPy's adapter formatting. That -3.8 point runtime
tax exceeds everything GEPA's optimization earned back (+2.2 inside its own runtime).
An optimizer that requires adopting its runtime must first pay for its runtime.

**3. Opposite mutation styles, identical failure signature.** GEPA bloated the prompt
to 3x its original length (my gate would have refused it on length alone). MIPROv2
*compressed* it to 0.73x and deleted instructions the task needs. Both, plus all 12 of
my own loop's candidates, regressed the same two fields: rare-variety capture and
multi-variant price selection. Against a well-tuned prompt on a small model, automated
search reliably finds candidates that look better on the visible metric and quietly
break the fields that matter.

## Then I audited my own gate, and it was broken too

Every verdict above is a rejection - so a fair question is whether my gate ever says
yes. I tested it: deliberately damaged the production prompt along three axes
(-3.5 points), then let the loop try to repair it under identical rules.

The loop *produced* good repairs - two candidates scored above the healthy original -
and the gate rejected all 18 of them. Perfect specificity, zero sensitivity. The
mechanisms turned out to be measurable: acceptance was scored on a suite-wide average
that dilutes targeted fixes (a failing test page still scores ~0.97 overall), and at 42
gold pages, a single page flipping on one field exceeds the per-field noise band, so
random wobbles blocked candidates.

I fixed both mechanisms as an explicitly versioned gate v2 - acceptance now requires a
candidate to *repair significantly more of the incumbent's known failures than it
breaks* (a sign test), and single-page wobbles are tolerated while two-page regressions
still block - and validated it in both directions:

- Replaying the 12 known-bad candidates under v2: **0 of 12 accepted**, and now with
  legible evidence - their ledgers show they break roughly as many fields as they fix.
- Re-running the repair experiment under v2: still no acceptance, but every rejection
  is now evidence-based (candidates repaired 0-3 fields while breaking 2-5). The
  remaining bottleneck is demonstrably upstream of the gate: one-small-edit mutations
  cannot fix three kinds of damage without collateral.

The general lesson: **system sensitivity factorizes into gate calibration x mutation
quality x test-suite size.** The naive setup conflates all three; separating them is
what made the failure attributable.

## One last attempt to earn a "yes"

After fixing the gate I gave my own loop every advantage - the strongest proposer model
available, fed a complete diagnosis (every failing field, grouped by pattern, plus the
full text of every failing page) instead of a few excerpts - and pointed it at the
production prompt one final time, with a pre-committed budget and stop rule.

It closed the search-quality gap: its edits were surgical, and for the first time
candidates repaired more test fields than they broke. It still never passed - because
every candidate that improved text extraction (the biggest weakness) measurably broke
price extraction on real pages. On a small model, prompt instructions compete for the
model's attention; the ledgers show the trade directly. That's the improvement frontier
for this prompt: not better search, not better gating - the single-prompt design itself.
The honest next moves (a feedback loop that tells the proposer why its last edit failed,
or splitting extraction into separate passes) are documented and out of scope.

## Does this generalize past coffee? A second task, and a bonus finding

To test the harness on something standard, I added an adapter for SROIE - the
most-cited receipt-extraction benchmark - and ran the same audit protocol on its
official labels: two models from different providers pre-label blind, triple agreement
auto-accepts, a human arbitrates every dispute.

Result: **a measured lower bound of 5.6% error in SROIE's official test labels** (9 of
160 audited fields), including a total written as `26:58` instead of `26.58`, a
truncated company registration, and an address missing two printed lines. It's a lower
bound for an uncomfortable reason: every modern model has SROIE in its training data,
so when a model "independently" agrees with an official label, it may just be reciting
it - the three votes are correlated in exactly the direction that hides errors.

Two sub-findings worth their own lines:

- Part of SROIE's folkloric "label noise" isn't annotation error at all: official
  labels faithfully reproduce OCR errors (`(EDAI BUKU` for `KEDAI BUKU`). For a
  text-input benchmark that is arguably correct behavior, and it should be counted
  separately from genuine mistakes.
- My audit's first run "found" label errors that were actually my own bug - a
  fixed-threshold line-reconstruction that scrambled word order on high-resolution
  receipts. Verbatim-on-page checks caught it before I claimed anything. **Audit the
  auditor first.**

## What I think this means

Prompt-optimization search is a commodity. Three different search strategies, including
a from-scratch adversarial loop, all found plausible-looking candidates cheaply. What
none of them come with is the thing that decided every outcome above: a frozen,
human-verified answer set with a stated error rate, variance-aware thresholds,
field-level vetoes, and a deployment gate that binds the shipped artifact to its
evidence. That infrastructure is where all the leverage was - it caught two frameworks'
winners, caught my own loop's winners, caught my own gate, and caught my own audit
pipeline.

Caveats, stated plainly: one small model under test (gpt-4o-mini); 42 gold pages is
small and the quantization effects above are partly a consequence; synthetic adversary
pages are not real pages; SROIE contamination affects absolute scores. The repo
publishes the fairness contract, and the referee is deterministic - if you think your
optimizer beats this gate, the harness will grade it: PRs welcome.

*Everything above - gold sets, ledgers, run states, verdicts, the audit forms - is in
the repo with checksums. Total LLM spend for all of it: under $50.*
