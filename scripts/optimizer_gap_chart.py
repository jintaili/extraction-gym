"""The headline figure for the public writeup: what each optimizer believed about its
candidate (internal/suite metric) vs what the frozen human-verified referee measured on
deployment (gold composite, production runtime), with gate verdicts.

Reads: run1 state (gym loop candidates), gepa-baseline.json + transplant verdict,
miprov2-baseline.json + transplant verdict (when present). Rerun after new results.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT_GOLD = 0.8920
NOISE_2X = 0.00802


def main() -> None:
    points = []  # (internal_belief, deployed_gold, label, verdict)

    state = json.loads(Path("runs/run1/state.json").read_text())
    for h in state["history"]:
        for c in h.get("candidates", []):
            if c.get("gold") is not None:
                points.append((c["suite"], c["gold"], None, "FAIL"))

    gepa = json.loads(Path("reports/gepa-baseline.json").read_text())
    transplant = json.loads(Path("reports/gepa-transplant-verdict.json").read_text())
    points.append((0.9703, ROOT_GOLD + transplant["mean_composite_delta"], "GEPA winner", transplant["verdict"]))

    mipro_path = Path("reports/miprov2-baseline.json")
    if mipro_path.exists():
        mipro = json.loads(mipro_path.read_text())
        verdict_path = Path("reports/miprov2-transplant-verdict.json")
        verdict = json.loads(verdict_path.read_text())["verdict"] if verdict_path.exists() else "?"
        internal = mipro.get("internal_best_score") or mipro["miprov2_optimized_on_gold"]["composite_mean"]
        deployed = json.loads(Path("reports/miprov2-transplant-gold.json").read_text())["composite_mean"] \
            if Path("reports/miprov2-transplant-gold.json").exists() \
            else mipro["miprov2_optimized_on_gold"]["composite_mean"]
        points.append((internal, deployed, "MIPROv2 winner", verdict))

    fig, ax = plt.subplots(figsize=(7.5, 6))
    lo, hi = 0.85, 1.0
    ax.plot([lo, hi], [lo, hi], ":", color="gray", lw=1, label="belief = reality")
    ax.axhspan(ROOT_GOLD - NOISE_2X, ROOT_GOLD + NOISE_2X, alpha=0.15, color="#1f77b4",
               label="incumbent ± gate threshold (2x noise)")
    ax.axhline(ROOT_GOLD, color="#1f77b4", lw=1)

    loop_pts = [(x, y) for x, y, lbl, v in points if lbl is None]
    if loop_pts:
        xs, ys = zip(*loop_pts)
        ax.scatter(xs, ys, marker="x", color="#d62728", s=45,
                   label=f"gym loop candidates (n={len(loop_pts)}, all REJECTED)")
    for x, y, lbl, v in points:
        if lbl:
            ax.scatter([x], [y], marker="o", s=90, color="#9467bd", zorder=5)
            ax.annotate(f"{lbl}\n({v})", (x, y), textcoords="offset points",
                        xytext=(10, -18), fontsize=8)

    ax.set_xlabel("optimizer's internal belief (its own metric on its own split)")
    ax.set_ylabel("deployed reality (frozen gold, production runtime)")
    ax.set_title("Every optimizer's winner, as it saw itself vs as the referee scored it")
    ax.set_xlim(lo, hi)
    ax.set_ylim(0.85, 0.905)
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    out = Path("reports/optimizer-gap-chart.png")
    fig.savefig(out, dpi=150)
    print(f"written: {out} ({len(points)} points)")


if __name__ == "__main__":
    main()
