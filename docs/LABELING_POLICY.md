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

## Decision log

Append one line per adjudication that required judgment beyond the rules above:

| date | page id | field | decision | rule affected |
|---|---|---|---|---|
