# Gold Set v1: Candidate URLs (HITL 1)

Status: DRAFT, awaiting human curation.

Target: 50 pages, roughly 25 ordinary English single-origin and 25 across hard strata.
Sources: coffee-value-app production query history (marked `[history]`, these reflect real
traffic), plus proposed pages from well-known roasters (marked `[proposed]`).

How to curate (your job is veto and policy, not hitting the counts):

1. Uncheck any URL you do not want. Adding replacements is optional.
2. Keep the roaster cap in mind: no roaster should exceed 4 pages (Onyx and Hydrangea are
   near the cap below; trim to taste).
3. Decide the two open questions at the bottom.
4. URLs are validated at snapshot time; dead pages get flagged for replacement, so do not
   spend time checking liveness.

After your pass, the agent backfills every stratum toward its target and presents only the
new URLs as a delta list for quick approval. Iterate until ~50. Stratum targets are soft:
what matters is roughly half ordinary / half hard, no empty stratum, no dominant roaster.

## Stratum A: ordinary English single-origin (target ~25)

- [x] https://aviary.coffee/collections/2026-season-coffees/products/025-maria-nieves `[history]` Peru gesha, rich producer prose
- [x] https://hydrangea.coffee/products/gesha-washed-finca-el-turpial `[history]`
- [x] https://hydrangea.coffee/products/purple-caturra-pineapple-washed-finca-monteblanco `[history]` pineapple co-ferment-adjacent naming
- [ ] https://hydrangea.coffee/products/letty-bermudez `[history]`
- [x] https://hydrangea.coffee/products/salma-bermudez `[history]` (README example)
- [x] https://shoebox.coffee/products/colombia-finca-los-angeles-gesha-washed `[history]`
- [x] https://ilsecoffee.com/collections/all-products/products/kenya-ibonia-estate-ab `[history]`
- [x] https://www.seycoffee.com/collections/coffee/products/2026-danche-white-honey-ethiopia `[history]` white honey process
- [x] https://www.seycoffee.com/collections/coffee/products/2026-jose-pena-los-naranjos-colombia `[history]`
- [x] https://moonwakecoffeeroasters.com/products/gilber-huayllas-llaqta-pata-anaerobic-washed-sl-9-peru `[history]` SL-9 variety edge case
- [x] https://lacabra.com/products/hermanos-burbano `[history]`
- [x] https://september.coffee/en-us/products/el-burro-lot-e-panama-natural-geisha `[history]` en-us locale path
- [x] https://onyxcoffeelab.com/products/peru-la-margarita-gesha-26?variant=42842298646626 `[history]` explicit variant param
- [x] https://www.brandywinecoffeeroasters.com/collections/all-coffee-1/products/stellar-collisions-next-generation `[history]` playful naming, hard to parse origin
- [x] https://timwendelboe.no/products/gachatha `[proposed]` .no domain, geo-priced
- [x] https://timwendelboe.no/products/finca-tamana-bourbon `[proposed]`
- [x] https://timwendelboe.no/products/echemo-certified-organic `[proposed]` organic certification prose
- [x] https://coffeecollective.dk/products/nueva-alianza-gesha-250-g `[proposed]` DKK
- [x] https://coffeecollective.dk/products/bombona-250-g `[proposed]` DKK
- [x] https://coffeecollective.dk/products/familia-ccapa-250g `[proposed]` DKK
- [ ] https://onyxcoffeelab.com/products/geometry `[proposed]` multi-size variants
- [ ] https://onyxcoffeelab.com/products/tropical-weather `[proposed]` multi-size variants
- [x] https://onyxcoffeelab.com/products/colombia-el-jardin-gesha `[proposed]`

## Stratum B: blends and espresso blends (target ~6)

- [x] https://philzcoffee.com/products/philtered-soul `[history]` mass-specialty blend
- [x] https://sightglasscoffee.com/collections/coffee/products/toketee-organic-blend `[history]`
- [x] https://blackfoxcoffee.com/collections/all-products/products/all-day-blend `[history]`
- [x] https://varietycoffeeroasters.com/products/lucky-shot-espresso?variant=32078925824100 `[history]` espresso blend + variant param
- [x] https://www.drinktrade.com/products/pump-house?variant=45942406873407 `[history]` marketplace-style blend page
- [x] https://onyxcoffeelab.com/products/monarch `[proposed]` house blend
- [x] https://onyxcoffeelab.com/products/southern-weather?variant=31862699917410 `[history]` blend + variant param
- [x] https://coffeeprojectnyshop.square.site/product/-crowd-pleaser-house-espresso/52?cs=true&cst=custom `[history]` square.site platform oddity

## Stratum C: decaf (target ~3)

- [x] https://perccoffee.com/products/decaf?variant=44057029869882 `[history]` decaf only in product title
- [x] https://onyxcoffeelab.com/products/decaf-ethiopia-suke-quto-26 `[proposed]`
- [x] TO FILL: one more decaf where "decaf" appears only in a variant name (agent finds during snapshotting)

## Stratum D: non-English (target ~6, at least 3 languages)

I am not sure if we necessarily need to test Estonian. Spanish and some nordic language is needed. Japanese is good to have

- [x] https://acidcoffee.stores.jp/items/69a76fe8fe1d6b005e3e0001 `[history]` Japanese, stores.jp platform
- [ ] https://shop.leavescoffee.jp/products/origami-pinn `[proposed]` Japanese, JPY
- [x] https://leavescoffee.jp/products/colombia-los-eucaliptos `[proposed]` Japanese, JPY (URL revised by curator; annotation fixed, no longer the sampler)
- [x] https://nomadcoffee.es/products/aji-las-flores `[history]` Spain, check ES vs EN rendering
- [ ] TO FILL: Korean page (Momos or Fritz, JS-heavy sites, agent validates during snapshotting)
- [ ] TO FILL: Italian page (Gardelli shop redirect issue, agent retries during snapshotting)
- [X] TO FILL: Famous nordic roaster page in native language, e.g., Denmark, Norway, Sweden
- [x] https://www.thebrickcoffee.ee/en/shop/tooted/el-salvador-las-nubes-1-1 `[history]` Estonian site, EN path, EUR
- [x] https://www.thebrickcoffee.ee/en/shop/tooted/honduras-emiliana-montoya `[history]`

## Stratum E: multi-variant with tricky defaults (target ~5) 

- [ ] https://perccoffee.com/products/colombia-luna-bermudez?variant=53343791481146 `[history]`
- [ ] https://perccoffee.com/products/colombia-diego-bermudez-castillo-m-03?variant=51260736569658 `[history]`
- [ ] https://perccoffee.com/products/colombia-andres-cardona-purple-honey?variant=53089244021050 `[history]`
- [ ] https://hydrangea.coffee/products/gesha-hybrid-washed-mikava-estates-marsella-ultralight `[history]` ultralight roast variant naming
- [ ] https://coffeecollective.dk/products/penas-blancas-gesha-200g `[proposed]` 200g nonstandard size
- [x] https://lovelesscoffees.coffee/products/yessica-parra-natural-gesha-pitalito-colombia?variant=48665088589979
- [x] https://onyxcoffeelab.com/products/colombia-el-jardin-gesha same URL as Stratum A entry: snapshotted once, tagged with both strata (tooling supports multi-stratum tags; it does not count twice toward the 50)

## Stratum F: subscription / sampler / luxury price (target ~5)

I could not find samplers. Please suggest. It's ok if you cannot find any good ones.

Agent sampler suggestions (approve by checking):

- [ ] https://shop.leavescoffee.jp/products/the-african-trio `[proposed]` 3-coffee sampler, Japanese, JPY (double stratum with D; was dropped when its slot was rewritten)
- [ ] Onyx box set: concrete URL comes in the backfill delta list from /collections/special

NOTE (agent): https://www.drinktrade.com/collections is a category listing, not a product
page. Under schema v2 its gold label would be page_type=not_a_product_page with all other
fields null, so it belongs in Stratum G if kept. Moved there pending your confirmation.
- [ ] https://www.drinktrade.com/products/ethiopia-haro-badessa-natural `[history]` subscription-forward marketplace
- [x] https://shop.leavescoffee.jp/products/subscription `[proposed]` subscription-only product page, JPY
- [ ] https://onyxcoffeelab.com/products/ecuador-el-dorado-gesha `[proposed]` $70 luxury tier
- [ ] TO FILL: one Onyx box set / sampler from /collections/special (agent finds during snapshotting)

## Stratum G: negative pages (target ~4)

Added per curator decision 2026-07-05: negative examples stay in the gold set so the
extractor is graded on classifying page type (see docs/SCHEMA_V2_PROPOSAL.md). On these
pages only page_type (and specialty flag where applicable) is graded; coffee and price
fields are null by contract. All four are from real production traffic.

- [x] https://www.amazon.ae/Coffee-Planet-Breakfast-Specialty-Ground/dp/B07MV2WHXG `[history]` coffee product, marketplace, non-specialty, AED
- [x] https://www.target.com/p/dunkin-39-original-blend-whole-bean-medium-roast-coffee-18oz/-/A-91290408 `[history]` coffee product, mass-market, non-specialty
- [x] https://clivecoffee.com/products/lelit-mara-x-espresso-machine `[history]` coffee equipment, not coffee
- [x] https://home.lamarzoccousa.com/espresso-machines/linea-mini/ `[history]` coffee equipment, marketing-style page
- [x] https://www.drinktrade.com/collections category listing page, not_a_product_page (moved from Stratum F by agent; uncheck if unintended)

## Open questions for the curator: RESOLVED 2026-07-05

1. Marketplace/mass-market and non-coffee pages: INCLUDED as Stratum G. The extractor
   gains page_type and is_specialty_coffee fields (schema v2) and is graded on them.
2. Extraction schema may diverge from the ML model input schema: extraction captures
   verbatim ground truth (exact variety, exact process); normalization to model vocabulary
   happens deterministically in the pipeline. See docs/SCHEMA_V2_PROPOSAL.md.
3. Stratum E kept at 2 to 3 pages. The agent backfills with verified-divergent multi-variant
   pages (real size/price spread, non-obvious default) in the delta list; the unchecked
   Perc/Hydrangea entries above stay out unless re-approved there.

Counts as drafted: ~45 concrete + 4 to-fill slots. Strike or add to land at 50.
