# extraction-gym

A harness that improves an LLM extraction program through an adversarial generator /
optimizer loop, gated by a frozen, human-verified referee. First customer: the coffee
product-page extractor behind [coffee-value-app](https://github.com/jintaili/coffee-value-app).

The product is the harness, not the coffee prompt. Prompt-optimization search is a
commodity (DSPy, GEPA, OPRO); what those frameworks do not give you is the evaluation
and governance infrastructure that lets an optimized prompt earn deployment:

1. **Evals as infrastructure.** A versioned, checksummed gold set of real pages with
   human-verified labels and a *stated residual label error* measured by a cold-label
   audit. Deterministic scorers only; no LLM anywhere in the referee path.
2. **Prompts as deployable artifacts.** Content-hash identity, immutable registration,
   parent lineage, an append-only evaluation ledger, and a release gate.
3. **Agent orchestration under budgets.** Resumable checkpointed loop, content-hash
   extraction caching (re-running an unchanged eval costs zero API calls), hard USD caps
   that raise instead of overspending.
4. **Anti-reward-hacking control rules, enforced in code.** The generator and optimizer
   never see gold pages or labels; synthetic pages never enter the gold set; the judge
   model must differ from the generator model; improvements must beat 2x the measured
   noise band; critical-field regressions block promotion regardless of composite gains.
   Every rule maps to a code path and a test: see [docs/DESIGN.md](docs/DESIGN.md).

## How the loop works

```text
generation g:
  adversary: generate K synthetic pressure pages embodying failure-taxonomy categories
             (30% chance: invent a new category), each with exact ground truth
             -> consistency judge (labels entailed by page?) -> realism judge (>=4/5)
             -> run incumbent, record failure diffs -> append to versioned suite
  optimizer: propose ONE focused prompt mutation from failure exemplars
             -> register artifact -> evaluate on pressure suite AND frozen gold
             -> gates: suite improvement beyond band, gold non-regression within
                2x noise band, no critical gold field regression
             -> PASS: candidate becomes incumbent; else discard, try next (max 4)
  checkpoint; stop on 3 no-improve generations, generation cap, or budget cap
```

The adversary is the piece search frameworks lack entirely: the evaluation distribution
is alive, regenerated each generation to target the current incumbent's weaknesses,
while the frozen human-verified gold set keeps the optimizer honest.

## Real findings so far

Building the gold set surfaced production failure modes no one planned for, now seeded
into [docs/FAILURE_TAXONOMY.md](docs/FAILURE_TAXONOMY.md): embedded variant weights that
are *shipping* weight rather than content weight, displayed prices that round differently
than the purchasable variant price, locale URLs that render English to a fetcher sending
`Accept-Language: en-US`, and stale page metadata contradicting the current body. The
first live adversary round (K=6, $0.42) found two genuine incumbent failures and invented
two failure categories that were in no taxonomy.

The referee's authority is quantified, not assumed: on the 10-page cold-label audit, the
two prelabel models' *consensus* was wrong on 8.5% of fields, and where they disagreed
the human curator rejected both candidates 31 times out of 56.

## CLI

```text
gym snapshot URL --stratum A     fetch through the production pipeline, store frozen page
gym prelabel --models A B        two-model prelabels -> blind adjudication review files
gym coldforms / checkforms       cold-label audit forms + validation
gym labelize / colddiff / freeze reviews -> labels -> residual error -> immutable manifest
gym verify                       checksum + manifest integrity
gym register-root / lineage      prompt artifact registry
gym eval / noise / compare       referee: eval report, noise band, gated verdict
gym adversary --count K          one adversary round against an incumbent
gym mutate / evalsuite           one focused mutation; score artifacts on the suite
gym chart RUN_ID                 the headline figure
```

## Reusing the harness

The harness never imports task-specific code outside `adapters/`. An adapter supplies
(a) a Pydantic output schema, (b) `extract(prompt, page_text) -> schema`, (c) a field
scoring config (scorer kind + weight per field, critical fields). Everything else —
gold-set tooling, cache, registry, budget, gates, adversary and optimizer machinery —
is task-agnostic.

## Status

Gold set v1 FROZEN: 42 real pages, human-verified labels, residual label error 0.159
stated in the manifest. Baseline: the production prompt scores 0.8920 composite; noise
band std 0.0040. First autonomous loop run: 12 candidates, all REJECTED — every one
improved the adversarial suite while regressing critical gold fields. **DSPy GEPA under
the same referee** ([reports/BENCHMARK.md](reports/BENCHMARK.md)): its internal metric
rated its winner 0.9703; transplanted into the production runtime that winner scores
+0.0003 over the incumbent with four critical-field regressions — GEPA's acceptance
criterion would have shipped it, this harness's gate refuses it. The shipped production
prompt is CI-pinned to its attested artifact (coffee-value-app
tests/test_prompt_attestation.py). MIPROv2 joined the benchmark (n=3: same failure
signature, opposite mutation pathology - compression instead of bloat, -3.3 points
deployed). A positive-control experiment measured the gate itself: perfect specificity,
zero sensitivity under the strict protocol, mechanism quantified and a gate-v2 direction
documented (reports/BENCHMARK.md). Second adapter: SROIE receipts (adapters/sroie), with
a cross-family label audit in progress. 30 tests.

## Honest limitations

Single model under test per adapter; residual label error as stated in each manifest; a
synthetic-to-real distribution gap for adversary pages; the acceptance gate is highly
specific but weakly sensitive under the strict protocol (measured by the positive
control; gate-v2 direction in reports/BENCHMARK.md). Retired since first writing:
second adapter (SROIE) and cross-family judging (`--judge-provider anthropic`) now exist.
Companion projects: [coffee-value-app](https://github.com/jintaili/coffee-value-app)
(inference service) and
[coffee-value-autoresearch](https://github.com/jintaili/coffee-value-autoresearch)
(model research loop this harness's discipline is adapted from).
