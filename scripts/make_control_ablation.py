"""Positive control: derive a documented ablation of the root prompt.

Purpose (docs/BENCHMARK.md follow-up): every gate result so far is a rejection, so
"does the gate ever accept?" is untested. This control cripples the root prompt along
three axes whose failures the adversary demonstrably surfaces (existing suite categories
with confirmed hits), runs the identical loop under identical gates, and measures whether
genuine improvements get accepted.

This is a CONTROL ABLATION, never a claimed baseline. The ablations:
  A1 remove verbatim-variety guidance      -> coffee.variety failures (critical field)
  A2 remove default-variant/embedded-data  -> listed_price/package_grams failures (critical)
  A3 remove blend guidance                 -> origin_country/is_blend failures (critical)
Each maps to suite categories with prior confirmed hits (sampler-default, blend-as-single-
origin, rare-variety pages), so the optimizer can see exemplars of the induced damage.
"""

from __future__ import annotations

from pathlib import Path

from extraction_gym.core.registry import PromptRegistry

ABLATIONS = {
    "A1_variety_verbatim": (
        """- variety: array of the exact variety names as stated on the page, verbatim (e.g. "SL-9", "Ombligon",
  "Pink Bourbon", "Geisha"). Keep the page's spelling. Do not normalize or lump rare varieties. Use ["unknown"]
  only when the page states no variety.
""",
        "- variety: array of variety names.\n",
    ),
    "A2_default_variant": (
        """- If no selected variant is present, use the variant marked default_for_inference, chosen as the package size closest to 10 oz (283.5 grams).
""",
        "",
    ),
    "A3_blend_guidance": (
        """- origin_country: producing country. Use "blend_multi_origin" only when multiple producing countries are clearly present.
""",
        "- origin_country: producing country.\n",
    ),
}


def main() -> None:
    registry = PromptRegistry(Path("registry"))
    root = registry.get("ce68bd4c4e")
    text = root.text
    for name, (old, new) in ABLATIONS.items():
        assert old in text, f"ablation {name}: target text not found in root prompt"
        text = text.replace(old, new)
    # Also remove the selected_by_url instruction (part of A2's failure surface).
    sel = "- If embedded product variant data identifies a selected_by_url variant, use that variant for price and package size.\n"
    assert sel in text
    text = text.replace(sel, "")

    control = registry.register(
        text=text,
        parent_id=root.artifact_id,
        mutation_note="CONTROL ABLATION (not a baseline): removed verbatim-variety, "
        "default-variant/selected_by_url, and blend guidance for gate-sensitivity test",
        source="human",
    )
    registry.append_ledger(
        {"event": "control_ablation", "artifact_id": control.artifact_id,
         "parent": root.artifact_id, "ablations": list(ABLATIONS) + ["A2b_selected_by_url"]}
    )
    print(f"control artifact: {control.artifact_id} (root {len(root.text)} -> control {len(text)} chars)")


if __name__ == "__main__":
    main()
