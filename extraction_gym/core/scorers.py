"""Per-field deterministic scorers. No LLM anywhere in the referee path.

Null semantics everywhere: both sides absent (None or empty) scores 1.0; exactly one
side absent scores 0.0.
"""

from __future__ import annotations

import re


def _is_absent(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip()) or value == []


def _norm_str(value, aliases: dict[str, str] | None = None) -> str:
    s = re.sub(r"\s+", " ", str(value).strip().casefold())
    if aliases:
        s = aliases.get(s, s)
    return s


def score_exact(gold, got) -> float:
    if _is_absent(gold) or _is_absent(got):
        return 1.0 if _is_absent(gold) and _is_absent(got) else 0.0
    if isinstance(gold, bool) or isinstance(got, bool):
        return 1.0 if gold is got else 0.0
    return 1.0 if _norm_str(gold) == _norm_str(got) else 0.0


def score_number(gold, got, *, rel_tol: float = 0.0, decimals: int | None = None) -> float:
    if _is_absent(gold) or _is_absent(got):
        return 1.0 if _is_absent(gold) and _is_absent(got) else 0.0
    try:
        g, p = float(gold), float(got)
    except (TypeError, ValueError):
        return 0.0
    if decimals is not None:
        return 1.0 if round(g, decimals) == round(p, decimals) else 0.0
    if g == 0:
        return 1.0 if p == 0 else 0.0
    return 1.0 if abs(p - g) / abs(g) <= rel_tol else 0.0


def _f1(gold_set: set[str], got_set: set[str]) -> float:
    if not gold_set and not got_set:
        return 1.0
    if not gold_set or not got_set:
        return 0.0
    overlap = len(gold_set & got_set)
    if overlap == 0:
        return 0.0
    precision = overlap / len(got_set)
    recall = overlap / len(gold_set)
    return 2 * precision * recall / (precision + recall)


def score_set_f1(gold, got, *, aliases: dict[str, str] | None = None) -> float:
    gold_list = gold if isinstance(gold, list) else ([] if _is_absent(gold) else [gold])
    got_list = got if isinstance(got, list) else ([] if _is_absent(got) else [got])
    gold_set = {_norm_str(v, aliases) for v in gold_list if not _is_absent(v)} - {"unknown"}
    got_set = {_norm_str(v, aliases) for v in got_list if not _is_absent(v)} - {"unknown"}
    return _f1(gold_set, got_set)


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.UNICODE)


def _tokens(value) -> list[str]:
    # \w-based split keeps unicode letters (Japanese text tokenizes per character run).
    return re.findall(r"\w+", str(value).casefold(), re.UNICODE)


def score_token_f1(gold, got) -> float:
    if _is_absent(gold) or _is_absent(got):
        return 1.0 if _is_absent(gold) and _is_absent(got) else 0.0
    gold_tokens, got_tokens = _tokens(gold), _tokens(got)
    # Multiset F1 via token counts.
    from collections import Counter

    gc, pc = Counter(gold_tokens), Counter(got_tokens)
    overlap = sum((gc & pc).values())
    if overlap == 0:
        return 0.0
    precision = overlap / max(sum(pc.values()), 1)
    recall = overlap / max(sum(gc.values()), 1)
    return 2 * precision * recall / (precision + recall)


def score_notes_set(gold, got) -> float:
    def split(value):
        if _is_absent(value):
            return set()
        return {_norm_str(part) for part in str(value).split(",") if part.strip()}

    return _f1(split(gold), split(got))
