"""The headline figure: composite score over loop generations, gold vs pressure suite,
with the gold noise band shaded and the root prompt as baseline."""

from __future__ import annotations

from pathlib import Path


def render_chart(state_history: list[dict], gold_band: dict | None, out_path: Path) -> Path:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("install the chart extra: pip install -e '.[chart]'") from exc

    generations = [h["generation"] for h in state_history if "suite_incumbent" in h]
    suite = [h["suite_incumbent"] for h in state_history if "suite_incumbent" in h]
    gold = [h.get("gold_incumbent") for h in state_history if "suite_incumbent" in h]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(generations, suite, marker="o", label="pressure suite (adversarial)", color="#d62728")
    if any(g is not None for g in gold):
        ax.plot(generations, gold, marker="s", label="frozen gold set (real pages)", color="#1f77b4")
        if gold_band and gold[0] is not None:
            band = 2 * gold_band.get("composite_std", 0)
            ax.axhspan(gold[0] - band, gold[0] + band, alpha=0.15, color="#1f77b4",
                       label="gold noise band (2x std)")
    if suite:
        ax.axhline(suite[0], linestyle=":", color="gray", label="root prompt baseline (suite)")
    accepted = [(h["generation"], h["accepted"]) for h in state_history if h.get("accepted")]
    for gen, artifact_id in accepted:
        ax.axvline(gen, alpha=0.2, color="green")
        ax.annotate(artifact_id[:6], (gen, ax.get_ylim()[1]), fontsize=7, ha="center", va="top")

    ax.set_xlabel("loop generation")
    ax.set_ylabel("weighted composite score")
    ax.set_title("Extraction accuracy over optimizer generations")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
