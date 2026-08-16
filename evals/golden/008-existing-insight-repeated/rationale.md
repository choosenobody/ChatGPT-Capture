# Case 008 — Existing insight repeated + Channel migration evergreen

Why this case matters
---------------------
Two distinct tests in one case:

1. **Dedup**: a high-quality inbox note already exists. The new
   conversation says the same thing. The librarian must *update*
   the existing note (appending belief history), not create a
   second evergreen.

2. **Channel migration evergreen**: this is a candidate for a
   cross-context evergreen ("where revenue is recognised is not the
   same as whether demand exists"). The vault_before/ note already
   contains the principle — the librarian must promote it (or
   confirm it is already in `20_Evergreen/`) rather than re-create.

Failure modes
-------------
- A second "Channel migration ≠ end demand" evergreen is created.
  (HARD-FAIL: duplicate evergreen)
- The existing inbox note is silently overwritten without a belief
  history append. (HARD-FAIL: silent belief overwrite)
- The note is *not* linked to the Moutai entity in `30_Entities/`.
  (linking miss)
