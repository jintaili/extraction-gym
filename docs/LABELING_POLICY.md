# Labeling Policy (HITL 2)

This document is the task definition. Every ambiguous labeling call gets resolved here as a
written rule, not just as a one-off label. The policies below are proposed defaults: confirm,
amend, or replace each one during the first 5 calibration pages. Rules added mid-review apply
retroactively (go back and fix earlier pages that the rule touches).

Status of each rule: PROPOSED until the human marks it CONFIRMED.

## R1. Default variant selection (PROPOSED)

When the URL has no `?variant=` parameter, the variant preselected on page load defines
`package_grams` and `listed_price`. When the URL pins a variant, that variant wins.
Rationale: matches what production sees and what a shopper lands on.

## R2. Subscription pricing (PROPOSED)

Prefer the one-time purchase price when both exist. If the page is subscription-only, label
the per-shipment price as `listed_price` and note `subscription_only` in the page metadata.

## R3. Sold-out products (PROPOSED)

Label the displayed price even if stale. The referee grades extraction fidelity, not
commercial validity.

## R4. Samplers and multi-bag sets (PROPOSED)

`package_grams` is the total grams across all bags when the page states it; otherwise null
with a metadata note. Origin fields: if the set spans origins, `is_blend` stays false (it is
not a blend), origin fields go to unknown/multiple per schema semantics.

## R5. VAT and tax-inclusive prices (PROPOSED)

Label the price exactly as displayed at snapshot time. No VAT arithmetic.

## R6. Geo-priced sites (PROPOSED)

The snapshot's rendered currency is ground truth (e.g. timwendelboe.no may render USD or NOK
depending on fetch locale). The label matches the frozen snapshot text, never the live page.

## R7. Verbatim text fields (PROPOSED)

`sensory_text` and `producer_text` must be contiguous spans copied from the snapshot, no
paraphrase, no stitching from distant parts of the page. If the page splits the content into
two adjacent blocks, joining with "; " is acceptable (matches current extractor behavior:
verify against coffee-value-app conventions on the first page where this arises).

## R8. display_tasting_notes (PROPOSED)

The roaster's headline note list as displayed, comma-separated, order preserved, original
language kept.

## R9. Blends and origin fields (PROPOSED)

`is_blend` true when components span multiple origins or the roaster markets it as a blend.
Origin fields follow production schema semantics for blends (verify against
coffee-value-app extractor schema before first blend page; record the exact convention here).

## R10. Non-English pages (PROPOSED)

Enum fields (country, process, variety) normalize to schema vocabulary in English. Verbatim
fields stay in the source language. `display_tasting_notes` stays in the source language per R8.

## R11. Specialty coffee definition (PROPOSED)

`is_specialty_coffee` is true when the page states an origin (country or region) plus at
least one of: process method, variety, or roast date. Mass-market pages (Dunkin', commodity
blends with no origin story) are false. Null unless `page_type` is `coffee_product`.
Report-only in gates until this rule survives a full labeling pass.

## R12. Multiple tasting-note blocks (RECOMMENDED 2026-07-05, pending curator veto)

sensory_text may stitch ALL lot-specific tasting/cup description blocks in page order,
joined with "; ". Generic marketing prose and boilerplate (brew guides, country explainers)
are excluded. Rationale: pages routinely split sensory content (headline notes plus an
"In the cup" section); both prelabel models and the curator's cold labels stitch, and the
token-F1 scorer degrades gracefully on span-boundary differences either way.

## R13. Producer vs farm when both are stated (CONFIRMED 2026-07-05, curator-amended)

Format: "producer; farm" with "; " as the slot delimiter, producer slot first
(e.g. "Lamastus Family; El Burro"). Multiple entities within one slot are comma-separated
(blend example: "cooperative in Ayarza, smallholder farm in Huila" is a single source
slot). Missing-part convention: when only one entity is stated, record it bare with no
semicolon (the schema field is producer_or_farm, so slot ambiguity for a lone entity is
acceptable and the token-F1 scorer is delimiter-insensitive). Neither stated: null.

## R14. Field classes: verbatim evidence vs canonical display (RECOMMENDED 2026-07-05,
pending curator veto; canonical-format principle set by curator)

Two classes of text fields with different rules:

1. Verbatim evidence fields (sensory_text, producer_text): capture what the page says.
   Structured spec lines (Producer: X / Elevation: Y / Tasting Notes: A, B, C) COUNT as
   page text; join relevant lines and lot prose in page order with "; ". Lot-specific
   content only; generic country or process explainer paragraphs are excluded. Absent
   means empty string "".
2. Canonical display fields (display_tasting_notes): normalized format, not verbatim.
   Lowercase noun phrases, comma-separated, no "and", no trailing period, page order,
   flavor notes only (no body/acidity/finish descriptors: "syrupy body" and "medium
   acidity" stay in sensory_text but not here). Example: "black cherry, chocolate bar,
   honey". Scored as a normalized set match, so ordering differences do not penalize.

Cold forms to revisit under R14: 672c1b9795, b115e3916e, ee70a8fc3c (spec-line spans
count). 52915c5c1a producer_text stays "": the "Produced together with" widget loses its
name in the html-to-text pipeline, so the text genuinely absent from the referee's input.

## R15. Language of verbatim fields vs production prompt (RESOLVED 2026-07-05)

Conflict found while adjudicating the Spanish Nomad page: R8/R10 keep verbatim fields in
source language, but the production prompt instructs "Translate to English" for
sensory_text, producer_text, and display note names. Gold labels follow R8/R10 (source
language: translation is nondeterministic and destroys verbatim gradability). Resolution:
amend those prompt lines to keep original language BEFORE the prompt is registered as the
gym's root artifact (one-line change on the schema-v2-extraction branch, pending with the
open PR). Resolved by curator: source language kept everywhere. Prompt amended on the
schema-v2-extraction branch (translate instructions removed); PR #1 updated.

## R16. Roast style is not roast level (CONFIRMED 2026-07-07, curator)

roast_level records development level (Light, Medium-Dark, Agtron values). Brew-style
roast designations ("Filter", "Espresso roast", "Whole bean coffee roasted for filter")
are NOT roast levels: roast_level is null when only a style is stated. Applied
retroactively to the Brick and Coffee Collective pages.

## Decision log

| date | page id | field | decision | rule affected |
|---|---|---|---|---|
| 2026-07-05 | 2f273f134c | coffee.sensory_text | stitched non-adjacent blocks, pending R12 | R7 |
| 2026-07-05 | 2f273f134c | coffee.producer_or_farm | chose producer over farm, pending R13 | new |
| 2026-07-05 | 2f273f134c | price.bags_count | 1 canonicalized to null for single bags | R4 |
| 2026-07-07 | 4cdd06ccd9 | display_tasting_notes | curator: headline Notas only, evolution notes stay in sensory_text | R14 |
| 2026-07-07 | 3e5d836124 | roaster_location/country | curator: Lancaster facility mention suffices; NOT propagated to sibling pages lacking the mention | evidence rule |
| 2026-07-07 | cc79f136ae | page_type | curator confirmed coffee_product for subscription-only product page | new |
| 2026-07-07 | 3 CC pages | roast_level | 'roasted for filter' nulled retroactively | R16 |

Append one line per adjudication that required judgment beyond the rules above.
