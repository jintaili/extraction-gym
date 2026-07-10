# SROIE label audit: arbitration instructions (HITL, ~20-30 min)

Open `disputes.yaml`. It has 41 disputes (of 160 sampled fields; 119 triple-agreed and
were auto-accepted). For each dispute, set `resolution:` to one of:

- `official` - the official SROIE label is correct
- `models` - the model consensus is correct and the official label is wrong
- `"<exact value>"` - neither is right; supply the correct value from the excerpt

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

When all 41 have resolutions, run:

    .venv/bin/python scripts/sroie_audit_finalize.py

which writes the audited labels, the corrections list, and the measured label-error
LOWER BOUND (lower bound because the 119 auto-accepts were never human-read, and both
prelabel models saw SROIE in training - their agreement with the official label is
partly recitation, so the three votes are correlated in the direction that hides errors).
