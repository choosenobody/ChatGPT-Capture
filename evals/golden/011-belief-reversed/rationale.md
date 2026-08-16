# Case 011 — Belief reversed (accounting reclassification)

Why this case matters
---------------------
A reversal must be classified differently from a weakening. The
*claim* changed, not just the confidence. The librarian must
preserve both the prior claim and the new claim with their
respective evidence.

Failure modes
-------------
- Classified as `weakened` because confidence dropped. (direction
  miss; this is the canonical failure mode for this case)
- The prior belief_history entry is deleted. (HARD-FAIL: silent
  overwrite)
- The note claims the prior view was *wrong* rather than
  *reclassified by new evidence* — a subtle but durable epistemic
  error.
