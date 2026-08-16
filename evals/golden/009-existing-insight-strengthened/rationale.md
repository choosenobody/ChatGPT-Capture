# Case 009 — Existing insight strengthened

Why this case matters
---------------------
Belief evolution is direction-typed. A `60 -> 70` update must be
classified as `strengthened`, not `new`, not `reversed`. The note
must *append* to belief history rather than overwrite the original
confidence value.

Failure modes
-------------
- Confidence silently re-written from 60 to 70 without history.
  (HARD-FAIL: silent belief overwrite)
- Direction classified as `new` (creates a second note).
  (precision miss + belief direction miss)
- Note not linked to Tencent entity in `30_Entities/`. (linking miss)
