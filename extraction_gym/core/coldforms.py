"""Blank cold-label forms for the residual-error audit subset.

Protocol (docs/LABELING_POLICY.md): the reviewer labels these pages from the snapshot
text alone, BEFORE opening any review/*.review.yaml. The disagreement rate between these
cold labels and the final adjudicated labels is the referee's stated residual error.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

FORM_TEMPLATE = """\
# COLD LABEL FORM. Label from {page_text_path} ONLY.
# Do NOT open review/{page_id}.review.yaml until all cold forms are DONE.
# Policy rules: docs/LABELING_POLICY.md (R1-R11). Confirm or amend rules as you go.
# Verbatim fields (process_method, variety, roast_level, harvest_period, sensory_text,
# producer_text): copy exact spans/terms from the page, no paraphrase (R7).
page_id: {page_id}
url: {url}
page_text: {page_text_path}
status: PENDING  # set to DONE when complete
label:
  page_type: null            # coffee_product | coffee_equipment | other_product | not_a_product_page
  is_specialty_coffee: null  # true | false | null (null unless coffee_product; see R11)
  coffee.coffee_name: null
  coffee.roaster: null
  coffee.roaster_location: null
  coffee.roaster_country: null   # "unknown" if page gives no evidence
  coffee.origin_country: null    # "blend_multi_origin" for multi-country blends (R9)
  coffee.origin_region: null
  coffee.process_method: []      # verbatim terms, e.g. ["white honey"]; ["unknown"] if absent
  coffee.variety: []             # verbatim names, e.g. ["SL-9", "Geisha"]; ["unknown"] if absent
  coffee.producer_or_farm: null
  coffee.altitude: null          # as written, with units
  coffee.roast_level: null       # verbatim, e.g. "Ultralight", "Agtron 58"
  coffee.harvest_period: null    # verbatim crop year / harvest window
  coffee.is_blend: null          # true | false
  coffee.is_espresso: null       # true | false
  coffee.is_decaf: null          # true | false
  coffee.is_coferment_or_infused: null  # true | false; additives during processing only
  coffee.sensory_text: null      # verbatim tasting notes span
  coffee.display_tasting_notes: null    # concise comma-separated note names (R8)
  coffee.producer_text: null     # verbatim origin/producer/process details span
  price.listed_price: null       # as displayed for the default/pinned variant (R1, R5, R6)
  price.listed_currency: null    # ISO-like code as rendered in the snapshot
  price.bag_size_value: null
  price.bag_size_unit: null      # g | kg | oz | lb
  price.package_grams: null      # total grams; for samplers, sum across bags (R4)
  price.bags_count: null         # integer; null for a single standard bag
  price.price_type: null         # one_time | subscription | membership | unknown (R2)
  price.availability: null       # in_stock | sold_out | preorder | unknown (R3)
notes: ""  # anything ambiguous; candidate policy rules for the decision log
"""


def write_cold_forms(goldset: Path, *, seed: int, count: int) -> list[str]:
    ids = sorted(p.name.removesuffix(".meta.json") for p in (goldset / "pages").glob("*.meta.json"))
    rng = random.Random(seed)
    chosen = rng.sample(ids, count)
    out_dir = goldset / "coldlabels"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for page_id in sorted(chosen):
        form_path = out_dir / f"{page_id}.cold.yaml"
        if form_path.exists():
            continue  # never clobber partial human work
        meta = json.loads((goldset / "pages" / f"{page_id}.meta.json").read_text(encoding="utf-8"))
        form_path.write_text(
            FORM_TEMPLATE.format(
                page_id=page_id,
                url=meta["final_url"],
                page_text_path=f"{goldset}/pages/{page_id}.txt",
            ),
            encoding="utf-8",
        )
        written.append(page_id)
    return written
