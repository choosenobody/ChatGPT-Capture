# Case 020 — Near duplicate wording

Why this case matters
---------------------
This is the librarian-level companion to case 006. The canonical
evergreen already exists; the new conversation is a rephrase. The
librarian must detect the title-similarity, append belief history,
and not create a second evergreen.

Failure modes
-------------
- A second evergreen titled differently ("Incremental returns make
  growth less capital intensive") is created. (HARD-FAIL: duplicate
  evergreen)
- The original evergreen is overwritten. (HARD-FAIL: silent
  overwrite)
- Both evergreens are kept. (dedup miss)
