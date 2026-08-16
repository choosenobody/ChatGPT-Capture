# Case 010 — Belief weakened (NOT reversed)

Why this case matters
---------------------
Direction typing matters. A 70 -> 65 update is `weakened`, not
`reversed`. The librarian must distinguish "I have less confidence
in the same thesis" from "I now hold the opposite view".

Failure modes
-------------
- Classified as `reversed` because the confidence dropped. (belief
  direction miss)
- Original belief history deleted. (HARD-FAIL: silent overwrite)
- New note created instead of updating existing. (dedup miss)
