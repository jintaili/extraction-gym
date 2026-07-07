# extraction-gym: Architecture and Control Rules

A harness that improves an LLM extraction program through an adversarial generator /
optimizer loop, gated by a frozen human-verified referee. First customer: the coffee
extractor from coffee-value-app.

## Architecture

```text
core/      schema-agnostic infrastructure: goldset store, cache, registry, budget
eval/      deterministic referee path: runner, scorers (via adapter config), stats/gates
adversary/ synthetic pressure-page generation with consistency + realism judges (Phase 4)
optimizer/ mutation proposal + generation loop (Phase 5)
adapters/  ALL coffee-specific code: fetch/page-context parity, extractor, scoring config
```

The harness never imports coffee-specific code outside `adapters/`. The adapter supplies
(a) the schema, (b) `extract(prompt, page_text) -> PageExtraction`, (c) field scoring
config with weights and critical fields. This boundary is what makes the harness reusable.

## Control rules (each enforced by a code path)

| rule | enforcement | test |
|---|---|---|
| Gold versions are immutable | `freeze` refuses if MANIFEST exists; `verify` recomputes checksums against MANIFEST | test_freeze_requires_labels_and_audit_then_is_immutable |
| Snapshots immutable; same-URL re-snapshot merges strata only | `GoldsetStore.store_snapshot` | test_snapshot_immutable_and_strata_merge |
| Referee sees exactly what production sees | adapter imports production `fetch_product_page` + `build_page_context` (no reimplementation) | smoke-tested against live pages |
| No LLM in the referee path | `core/scorers.py` is pure functions | test_scorers suite |
| Human-verified labels with stated residual error | `labelize` requires review_status VERIFIED; `colddiff` measures cold-vs-final change rate; `freeze` embeds it in MANIFEST | test_colddiff_counts_changes |
| Improvements must exceed 2x measured noise | `stats.compare` NOOP inside the band | test_compare_verdicts |
| Critical-field regression blocks regardless of composite | `stats.compare` FAIL path | test_compare_verdicts |
| Re-running unchanged evals costs zero API calls | content-hash extraction cache keyed on actual prompt hash | test_evaluate_artifact_scores_and_caches |
| Every artifact immutable, one mutation, lineage recorded | `PromptRegistry` (content-hash ids, parent links, append-only ledger) | test_registry_register_lineage_ledger |
| Hard USD spend cap | `BudgetTracker` raises `BudgetExceeded`; unknown models raise instead of costing $0 | test_noise_band_and_budget |
| Prompt bloat blocked | gate caps candidate length at 1.5x the ROOT prompt (anchored to root so drift cannot compound across accepted generations) | test_gate_blocks_prompt_bloat |
| Generator never sees gold pages or labels | adversary context assembled from taxonomy + schema + suite diffs only (Phase 4) | pending |
| Synthetic pages never enter the gold set | `freeze` only reads goldset/ pages; suite lives in suites/ | structural |

## Referee protocol notes

- Labels were produced by assisted verification: two independent prelabel models,
  disagreements adjudicated by the curator against frozen snapshots, agent-proposed
  resolutions accepted or overridden by the curator, rules R1-R15 in LABELING_POLICY.md.
- The residual label error in MANIFEST.json comes from a 10-page cold-label audit
  performed before the curator saw any model output. Curator-measured facts: model
  consensus was wrong on 8.5% of fields; when models disagreed the curator rejected both
  candidates 31/56 times. This is why the referee is human-verified.
- `is_specialty_coffee` is report-only (weight 0) until R11 survives a labeling pass.
- Verbatim fields keep the page's source language (R15); the production prompt was
  amended accordingly before root registration.

## What the optimizer edits, and why length is gated

v1 editable surface: the system prompt text only. Not editable: the schema, decoding
params, the model under test, anything in the referee path. This makes the loop a prompt
optimization harness in the same family as OPRO/GEPA, and inherits their failure mode:
the cheapest "mutation" is always to append more instructions. Length is material for
three reasons: per-page cost and latency scale with prompt tokens across every production
request; long instruction lists measurably dilute instruction-following on smaller models
(the model under test is a mini-class model); and unbounded growth is reward hacking
(memorizing pressure-suite quirks as special cases rather than generalizing). Hence the
1.5x-of-root length gate. Page-text input tokens are not gated: they are fixed by the
production trimming policy (COFFEE_VALUE_MAX_PAGE_TEXT_CHARS), which lives in the
non-editable referee path.

## First loop run: the gate earning its keep (2026-07-07)

Run1 (3 generations, 12 candidates, $4.16): every candidate improved or held the
pressure suite yet regressed critical gold fields, coffee.variety and price.listed_price
systematically. The mutation family that wins synthetic pressure pages (labeled-field
precedence rules) trades away rare-variety verbatim capture and multi-variant price
selection on real pages. Without the frozen-gold critical-field gate, generation 1 would
have shipped a prompt that looks +0.8% better and silently breaks price extraction.
Documented NOOP; honest per plan definition-of-done item 5.

## Known limitations

Single task, single model under test, residual label error as stated in the manifest,
synthetic-to-real distribution gap for adversary pages, judge and generator currently
share a provider family (different models; cross-family judging planned when a second
provider key is available).
