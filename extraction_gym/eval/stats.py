"""Noise band estimation, paired comparison, and gate decisions.

Gates require improvements to exceed 2x the measured noise band; changes within the
band are NOOP (candidate discarded); any critical-field regression beyond its own band
is FAIL. Everything here is deterministic given the seed.
"""

from __future__ import annotations

import math
import random
import statistics

from extraction_gym.adapters.coffee.scoring import CRITICAL_FIELDS


def noise_band(reports: list[dict]) -> dict:
    """Std-dev across repeat runs of the same artifact (cache disabled)."""
    assert len(reports) >= 2, "need at least 2 runs for a noise band"
    composites = [r["composite_mean"] for r in reports]
    fields = reports[0]["field_means"].keys()
    field_stds = {}
    for field in fields:
        values = [r["field_means"][field] for r in reports if r["field_means"][field] is not None]
        field_stds[field] = statistics.pstdev(values) if len(values) >= 2 else None
    return {
        "runs": len(reports),
        "composite_mean": statistics.mean(composites),
        "composite_std": statistics.pstdev(composites),
        "field_stds": field_stds,
    }


def paired_bootstrap_ci(
    deltas_by_page: dict[str, float], *, iterations: int = 5000, seed: int = 20260705
) -> tuple[float, float, float]:
    """Mean delta and 95% CI by resampling pages with replacement."""
    pages = sorted(deltas_by_page)
    deltas = [deltas_by_page[p] for p in pages]
    rng = random.Random(seed)
    means = []
    for _ in range(iterations):
        sample = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        means.append(sum(sample) / len(sample))
    means.sort()
    mean_delta = sum(deltas) / len(deltas)
    return mean_delta, means[int(0.025 * iterations)], means[int(0.975 * iterations)]


def mcnemar_p(b01: int, b10: int) -> float:
    """Exact binomial McNemar test on discordant pair counts."""
    n = b01 + b10
    if n == 0:
        return 1.0
    k = min(b01, b10)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2**n * 2
    return min(1.0, p)


def compare(report_a: dict, report_b: dict, band: dict) -> dict:
    """Gate verdict for candidate B against incumbent A on the same page set."""
    pages = sorted(set(report_a["composite_by_page"]) & set(report_b["composite_by_page"]))
    deltas = {p: report_b["composite_by_page"][p] - report_a["composite_by_page"][p] for p in pages}
    mean_delta, ci_low, ci_high = paired_bootstrap_ci(deltas)
    threshold = 2 * band["composite_std"]

    critical_regressions = []
    for field in CRITICAL_FIELDS:
        a_mean, b_mean = report_a["field_means"].get(field), report_b["field_means"].get(field)
        if a_mean is None or b_mean is None:
            continue
        field_band = band["field_stds"].get(field) or 0.0
        if b_mean < a_mean - max(field_band, 1e-9):
            critical_regressions.append(
                {"field": field, "incumbent": a_mean, "candidate": b_mean, "band": field_band}
            )

    mcnemar = {}
    scores_a, scores_b = report_a.get("scores_by_page", {}), report_b.get("scores_by_page", {})
    if scores_a and scores_b:
        for field in CRITICAL_FIELDS:
            b01 = b10 = 0
            for page in pages:
                sa = scores_a.get(page, {}).get(field)
                sb = scores_b.get(page, {}).get(field)
                if sa is None or sb is None or sa == sb:
                    continue
                if sa < sb:
                    b01 += 1
                else:
                    b10 += 1
            mcnemar[field] = {"improved": b01, "regressed": b10, "p": mcnemar_p(b01, b10)}

    if critical_regressions:
        verdict = "FAIL"
    elif mean_delta > threshold:
        verdict = "PASS"
    else:
        verdict = "NOOP"

    return {
        "pages": len(pages),
        "mean_composite_delta": mean_delta,
        "bootstrap_ci95": [ci_low, ci_high],
        "noise_threshold_2x": threshold,
        "critical_regressions": critical_regressions,
        "mcnemar_critical_fields": mcnemar,
        "verdict": verdict,
    }
