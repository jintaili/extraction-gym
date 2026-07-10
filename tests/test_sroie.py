from extraction_gym.adapters.sroie.fetch_data import reconstruct_lines
from extraction_gym.adapters.sroie.scoring import composite, score_page, score_total


def test_reconstruct_lines_adaptive_threshold():
    # Two lines on a high-res receipt (line spacing 40px, word height 30px):
    # a fixed 12px threshold would merge them; adaptive must not.
    words = ["HELLO", "WORLD", "SECOND", "LINE"]
    bboxes = [[10, 100, 90, 130], [100, 100, 190, 130], [10, 140, 110, 170], [120, 140, 180, 170]]
    assert reconstruct_lines(words, bboxes) == "HELLO WORLD\nSECOND LINE"

    # Slight y-jitter within one line stays one line.
    jitter = [[10, 100, 90, 130], [100, 104, 190, 134]]
    assert reconstruct_lines(["A", "B"], jitter) == "A B"


def test_score_total_numeric_tolerance():
    assert score_total("135.68", "RM 135.68") == 1.0
    assert score_total("1,135.68", "1135.68") == 1.0
    assert score_total("135.68", "135.60") == 0.0
    assert score_total(None, None) == 1.0
    assert score_total("135.68", None) == 0.0


def test_score_page_and_composite():
    gold = {"company": "KEDAI PAPAN", "date": "16/03/2018", "address": "LOT 276", "total": "135.68"}
    got = {"company": "kedai  papan", "date": "2018-03-16", "address": "LOT 276", "total": "135.68"}
    scores = score_page(gold, got)
    assert scores["company"] == 1.0  # case/whitespace-normalized
    assert scores["date"] == 0.0     # format differences are misses (audit rule pending)
    assert composite(scores) == (1.0 * 1 + 0 * 2 + 1.0 * 1 + 1.0 * 2) / 6
