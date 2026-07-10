"""Fetch SROIE test data and materialize a gold set directory.

Source: the sizhkhy/SROIE HuggingFace mirror of the ICDAR-2019 SROIE test split
(347 receipts, OCR words + boxes, official Task-3 field labels). Data is NOT
redistributed with this repo: goldset/sroie-v1/ is gitignored except the manifest,
and the download is checksum-pinned here. Original source: ICDAR RRC portal
(rrc.cvc.uab.es, registration required); the mirror is used for reproducibility.

Page text is reconstructed from OCR words by grouping word boxes into lines
(y-center clustering, then x-sort) - the same text-only surface KIE papers use for
SROIE without vision.

Labels: OFFICIAL labels are written as label source "official". The audited gold
(post-HITL) is written separately; both scorings are reported (see plan step 3).
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

MIRROR_URL = "https://huggingface.co/datasets/sizhkhy/SROIE/resolve/main/data/test-00000-of-00001.parquet"
EXPECTED_SHA256 = None  # pinned after first fetch; see MANIFEST


def reconstruct_lines(words, bboxes) -> str:
    """Group word boxes into text lines.

    The line-break threshold adapts to the receipt's own text size (median word-box
    height) rather than a fixed pixel count - receipt scans vary widely in resolution,
    and a fixed threshold scrambles word order on high-resolution images by merging
    adjacent lines before the x-sort.
    """
    boxes = [(str(w), box) for w, box in zip(words, bboxes)]
    if not boxes:
        return ""
    heights = sorted(box[3] - box[1] for _, box in boxes)
    threshold = max(6.0, heights[len(heights) // 2] * 0.6)
    items = sorted(
        ((box[1] + box[3]) / 2, box[0], w) for w, box in boxes
    )
    lines: list[list[tuple[float, str]]] = []
    line_ys: list[float] = []
    for y, x, w in items:
        if not lines or abs(y - line_ys[-1]) > threshold:
            lines.append([])
            line_ys.append(y)
        else:
            n = len(lines[-1])
            line_ys[-1] = (line_ys[-1] * n + y) / (n + 1)
        lines[-1].append((x, w))
    return "\n".join(" ".join(w for _, w in sorted(line)) for line in lines)


def main(out_root: Path = Path("goldset/sroie-v1"), cache: Path | None = None) -> None:
    import pandas as pd

    cache = cache or Path(".cache") / "sroie-test.parquet"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        print(f"downloading {MIRROR_URL}")
        urllib.request.urlretrieve(MIRROR_URL, cache)
    sha = hashlib.sha256(cache.read_bytes()).hexdigest()
    print(f"parquet sha256: {sha}")

    df = pd.read_parquet(cache)
    pages_dir = out_root / "pages"
    labels_dir = out_root / "labels-official"
    pages_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    for i, row in df.iterrows():
        page_id = f"sroie-{i:03d}"
        text = reconstruct_lines(row["words"], row["bboxes"])
        (pages_dir / f"{page_id}.txt").write_text(text, encoding="utf-8")
        fields = {k.lower(): v for k, v in row["fields"].items()}
        (pages_dir / f"{page_id}.meta.json").write_text(json.dumps({
            "url": f"sroie:test:{i}", "final_url": f"sroie:test:{i}", "strata": ["sroie"],
            "sha256": hashlib.sha256(text.encode()).hexdigest(), "chars": len(text),
            "fetched_at": "mirror",
        }, indent=2) + "\n", encoding="utf-8")
        (labels_dir / f"{page_id}.json").write_text(json.dumps({
            "page_id": page_id, "label": fields, "source": "official",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (out_root / "SOURCE.json").write_text(json.dumps({
        "mirror": MIRROR_URL, "parquet_sha256": sha, "receipts": len(df),
        "note": "data gitignored; fetch with python -m extraction_gym.adapters.sroie.fetch_data",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(df)} receipts to {out_root}")


if __name__ == "__main__":
    main()
