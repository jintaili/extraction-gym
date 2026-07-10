# SROIE label audit: arbitration instructions (HITL, ~20-30 min)

Open `disputes.yaml`. It has 41 disputes (of 160 sampled fields; 119 triple-agreed and
were auto-accepted). Each dispute has a `case:` line telling you the situation (models agree with each
other / one model matches official / all three differ). Set `resolution:` to one of:

- `official` - the official SROIE label is correct
- `gpt-4o-mini` - that model's value is the correct one
- `claude-haiku-4-5` - that model's value is the correct one
- `models` - shorthand valid only when the two models agree with each other
- `"<exact value>"` - none of the candidates is right; supply the value from the excerpt

Note a dispute only means "not both models matched official" - in 28 of the 41, one
model DOES match official and the other differs; usually those resolve to `official`
unless the odd one out is actually right.

How to decide, per field:

- The `receipt_excerpt` contains the relevant lines from the reconstructed OCR text;
  `verbatim_on_page` tells you whether each candidate appears verbatim.
- `date`: SROIE convention is the date string as printed on the receipt (e.g.
  16/03/2018, not 2018-03-16). A model that reformatted is WRONG under this convention
  even if the date is the same day. If you prefer a canonicalization rule instead,
  write it at the top of the file as a note and apply it consistently.
- `company`: the registered business name line, usually the first prominent line;
  official labels sometimes include or exclude the registration suffix ((0005583085-K)).
  Pick what the receipt states as the name; note a rule if you adopt one.
- `total`: the final payable amount. Watch for total vs cash vs change vs rounding
  lines; the excerpt shows candidates in context.
- `address`: the full printed address block.
- `drafted_recommendation` is a heuristic (verbatim-on-page checks), not authority.
- OCR-corrupted values (e.g. official label `(EDAI BUKU...` where the receipt image
  surely says `KEDAI BUKU...`): resolve as `official` - the rule is faithfulness to the
  TEXT the extractor receives, not to the image nobody in this pipeline can see. Add
  `note: ocr-inherited (image likely says ...)` on that dispute; these are tallied as a
  separate noise category in the final report, distinct from annotation mistakes.

When all 41 have resolutions, run:

    .venv/bin/python scripts/sroie_audit_finalize.py

which writes the audited labels, the corrections list, and the measured label-error
LOWER BOUND (lower bound because the 119 auto-accepts were never human-read, and both
prelabel models saw SROIE in training - their agreement with the official label is
partly recitation, so the three votes are correlated in the direction that hides errors).
