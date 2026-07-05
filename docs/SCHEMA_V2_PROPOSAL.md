# Extraction Schema v2 Proposal

Principle (set by the curator, 2026-07-05): the extraction schema captures what the page
actually says, verbatim and exact. Normalization into the ML model's limited vocabulary is
the model pipeline's job, not the extractor's. The two schemas are decoupled; `ModelInput`
does not change.

## Gaps found in the current production schema (schemas.py)

### G1. Closed Variety enum loses ground truth (critical)

`Variety` is a 15-value StrEnum. Two pages already in the gold candidate list cannot be
represented today:

- Moonwake "anaerobic washed SL-9 Peru": SL-9 is not in the enum. Collapses to unknown.
- Lohas "Ombligon by Nestor Lasso": Ombligon is not in the enum. Collapses to unknown.

Also missing and common on specialty pages: sidra, chiroso, wush wush, pacas, pache,
batian, K7, villa sarchi, landrace/heirloom designations. Every one is silent data loss.

### G2. Closed ProcessMethod enum loses ground truth (critical)

Same problem: Sey "Danche White Honey" (gold candidate, stratum A) has no representable
process (white honey is not in the enum; nearest is honey, which erases the distinction).
Missing: honey color grades, thermal shock, koji/yeast fermentation, co-ferment/infused
descriptors, double washed, giling basah as distinct from wet-hulled naming.

Note: the ML feature contract (coffee-grader `coffee_value/features.py`) already normalizes
free text to its own vocabulary with regex mappings (white honey maps to honey there). So
the lumping layer exists where it belongs. The extractor enums duplicate it lossily.

### G3. No page-type or specialty classification

Production traffic includes espresso machines, Amazon commodity coffee, Target Dunkin'.
The extractor currently has no way to say "this is not a specialty coffee product page";
it hallucinates or degrades unpredictably. Curator decision: negative pages join the gold
set and the schema must express this.

### G4. No roast level

Stated on most product pages, value-relevant, absent from the schema. Sometimes roast level 
is expressed in measurable ways, such as Agtron Scale.

### G5. No price type

Subscription-per-shipment vs one-time purchase is indistinguishable in the output. This is
the silent price failure mode behind labeling rule R2 and the subscription stratum.

### G6. No availability

Sold-out pages with stale prices (rule R3) are not expressible.

### G7. No sampler/multi-bag support

`bags_count` absent; a 3x100g sampler cannot be distinguished from a 300g bag (rule R4).

### G8. No co-ferment/infused flag

A growing, price-distorting category (also an adversary taxonomy entry). Currently only
recoverable by parsing producer_text downstream.

## Proposed changes

### ExtractedCoffee

| change | field | type | note |
|---|---|---|---|
| replace | `variety` | `list[str]` | verbatim exact names as stated on page |
| replace | `process_method` | `list[str]` | verbatim, e.g. "white honey", "72h anaerobic natural" |
| add | `roast_level` | `str \| None` | verbatim, e.g. "Ultralight", "Medium", "Agtron 58"; measurable scales kept as stated, scorer normalizes |
| add | `is_coferment_or_infused` | `bool` | true when fruit/botanical added during processing |
| add | `harvest_period` | `str \| None` | verbatim crop year / harvest window if stated |

### New page-level fields (on PageExtraction)

| field | type | note |
|---|---|---|
| `page_type` | `Literal["coffee_product", "coffee_equipment", "other_product", "not_a_product_page"]` | graded with high weight on negative pages |
| `is_specialty_coffee` | `bool \| None` | null unless page_type is coffee_product; needs a checkable definition in LABELING_POLICY (proposed R11: page states at least origin plus one of process/variety/roast date) |

When `page_type != "coffee_product"`, all coffee and price fields are null/unknown by
contract and excluded from scoring; only `page_type` (and quality warnings) are graded.

### ExtractedPrice

| change | field | type | note |
|---|---|---|---|
| add | `price_type` | `Literal["one_time", "subscription", "membership", "unknown"]` | encodes rule R2 |
| add | `availability` | `Literal["in_stock", "sold_out", "preorder", "unknown"]` | encodes rule R3 |
| add | `bags_count` | `int \| None` | samplers; `package_grams` stays total per R4 |

### Normalization moves to code

`to_model_input` gains a deterministic mapping table (verbatim string -> model vocab),
reusing the regex logic already in coffee-grader features.py. Unmapped varieties lump to
the model's other/unknown bucket inside the pipeline, exactly as the curator specified.
`ModelInput` itself is unchanged: predictors are untouched by this migration.

## Scoring implications for the gym

- Verbatim `variety`/`process_method` graded as normalized-string set F1 (casefold, small
  alias table in the adapter scorer config: gesha/geisha, SL-9/SL9).
- `is_specialty_coffee` starts report-only (not gate-blocking) until R11's definition has
  survived a full labeling pass; promote to gated once stable.
- The `quality` block (extraction_quality, missing_fields, warnings) is self-reported by
  the extractor and is never graded by the referee.

## Migration sequence

1. PR to coffee-value-app: schemas v2, mapping table in `to_model_input`, minimal prompt
   additions so the current prompt fills the new fields. This updated prompt becomes the
   gym's `root` artifact.
2. Gold set labels are authored in v2 from the start (no relabeling later).
3. extraction-gym adapter vendors the v2 schema.

Decision status: CONFIRMED by curator 2026-07-05 (with note on measurable roast scales in G4).
