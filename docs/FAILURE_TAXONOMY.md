# Failure Taxonomy

Failure modes the extractor is known or suspected to exhibit. The adversary samples
from this taxonomy (and invents new categories with probability 0.3); the loop appends
discovered modes here with evidence.

## Seed categories (from the plan)

1. multi-variant page where the default variant is a small sampler
2. subscription-only pricing (per-shipment price mistaken for purchase price)
3. non-English page (Japanese, Danish, Italian, Korean)
4. co-ferment or infused coffee described in marketing prose
5. blend presented like a single origin
6. price shown per subscription shipment rather than per bag
7. sold-out product with stale price
8. wholesale page with tiered pricing
9. region-ambiguous origin
10. decaf mentioned only in a variant name

## Discovered in real gold-set data (2026-07-05, during labeling)

11. **Embedded weight is shipping weight, not content weight.** Brandywine: Shopify
    variant weight 425g for a 12oz (340g) bag. An extractor trusting embedded
    package_grams over the stated size silently inflates bag size by 25%.
12. **Displayed price rounds down from true variant price.** Coffee Collective shows
    "159 DKK" while the embedded variant price is 159.20. Two page-internal sources
    disagree; policy: embedded variant price wins.
13. **Localized sites render English to the production fetcher.** The /da/ Danish page
    returned English (Accept-Language: en-US). Extractors and evals must not assume URL
    locale implies page language.
14. **default_for_inference marker points at the wrong variant when gram metadata is
    missing.** Nomad: eight 250g variants lack grams, so the marker lands on the 1kg
    variant (130 EUR) while the page-load default is 250g at 32.50 EUR.
15. **Stale metadata vs current body.** Black Fox meta description names last season's
    component lot (El Meridiano/Herrera); the body names the current one (El Nevado del
    Huila). Extractors reading only the description extract superseded facts.
16. **Junk enum echo under pressure.** On a non-product listing page, the production
    model emitted ">unknown" (with angle bracket) for string fields.
17. **Producer name lost by the html-to-text pipeline.** Coffee Collective's "Produced
    together with <name>" widget loses the name on some pages; the correct label is
    absent even though the browser shows it.

## Adversary-invented categories (generator, 2026-07-06 validation round)

18. Cross-sell recommendation block contains another coffee's specs (suite 3a05db992a;
    no incumbent hit yet)
19. Brew recipe dose mistaken for package size (suite c0cc15648e; no incumbent hit yet)

First confirmed incumbent hits (validation round, K=6, root ce68bd4c4e):
category 3 (non-English page) broke coffee.origin_country; category 5 (blend as single
origin) broke coffee.process_method.

## Suite after run1 (2026-07-07): 25 pages, 16 categories, 8 generator-invented

Highest incumbent hit rates against root ce68bd4c4e (hits/accepted):

- 3/5 multi-variant page where default is a small sampler
- 2/3 region-ambiguous origin
- 2/3 stale meta description contradicting body
- 2/2 blend presented like a single origin
- 1/1 each: related-product spec bleed (invented), decaf-navigation contamination
  (invented), footer-keyword contamination (invented), non-English spec page,
  co-ferment in prose, wholesale tiered pricing

Generator convergence note: five independently invented categories are variants of one
theme, "other products' text contaminating the main product's extraction" (cross-sell
specs, related-variant data, recommended-product blocks, decaf navigation, footer
keywords). The generator keeps rediscovering the extractor's real weakest surface:
distinguishing the page's subject from its surroundings. This clusters with taxonomy 15
(stale metadata) and both scored hits where tried.

Per-category before/after accuracy is added by the loop (Phase 6).
