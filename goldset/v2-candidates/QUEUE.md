# Gold v2 Candidate Queue

The adversary tells you where to look; reality provides the referee. For each
adversary-discovered or run1-confirmed failure mode, this queue lists real pages to
snapshot and label for gold v2. Nothing here enters gold v1 (frozen).

Status: DRAFT. Snapshotting these is mechanical; labeling is HITL (curator).

## From run1's systematic candidate regressions (highest value)

The 12 rejected candidates all regressed coffee.variety and price.listed_price on real
pages. Gold v2 should over-sample exactly those:

- [ ] 2-3 more rare-variety pages (Sidra, Chiroso, Wush Wush, SL-9 already covered once
      each; a second instance of each turns anecdotes into a measurable stratum)
- [ ] 2-3 more multi-variant pages with non-obvious defaults (the listed_price failure
      surface)

## From adversary-invented categories

- [ ] Cross-sell block with another coffee's specs: most Shopify roaster pages qualify;
      Hydrangea pages already show "Brewing Accesories" cross-sells - find one where the
      cross-sell is another COFFEE (e.g. Onyx "You might also like" rows)
- [ ] Brew-recipe dose mistaken for package size: Perc pages carry "DOSE: 22g" blocks;
      Nomad carries "19 gramos de café" recipes - both already in gold v1, tag them
- [ ] Related-product variant data preceding main product data: La Cabra page layout
- [ ] Recommended-product spec contamination: Trade product pages ("Shop for similar
      coffees" with spec rows)

## From taxonomy entries 11-17 (real, discovered during labeling)

- [ ] Shipping-weight-vs-content: any Brandywine page (systematic on their Shopify)
- [ ] Rounded display price: any Coffee Collective page (159 vs 159.20 pattern)
- [ ] Stale meta description: Black Fox blends (seasonal rotation)

When 8-12 candidates are agreed: snapshot (gym snapshot --goldset goldset/v2), prelabel,
curator review, freeze v2. Cross-version comparisons re-score both artifacts on the same
version (growth policy, DESIGN.md).
