# Case 024 — Contradiction with existing vault

Why this case matters
---------------------
The canonical contradiction case. The user is *explicitly*
identifying a contradiction with an existing evergreen. The
librarian must keep both claims visible, mark the contradiction,
and provide resolution evidence.

Failure modes
-------------
- The existing evergreen is silently overwritten with the new
  view. (HARD-FAIL: silent overwrite)
- The new view is silently dropped. (recall miss)
- The two claims are collapsed into a single mid-ground evergreen
  without preserving the history. (HARD-FAIL: silent overwrite)
- The contradiction is resolved by the librarian ("I think the
  new evidence wins"). (epistemic miss — that's the user's call)
