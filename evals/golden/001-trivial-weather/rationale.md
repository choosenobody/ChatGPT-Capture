# Case 001 — Trivial weather query

Why this case matters
---------------------
Pure small-talk / lookup conversation. The conversation has no
mental model, no reusable mechanism, no decision impact. This is the
baseline trivial test for the materiality gate.

Failure modes it should catch
-----------------------------
- Extractor writes a "weather note" because the user asked a question.
  (precision miss, but not a hard-fail by itself)
- Extractor or librarian writes a "weather evergreen" because
  forecasts recur. (HARD-FAIL: trivial -> Evergreen)
- The librarian promotes it to a reusable principle. (HARD-FAIL)

What a clean run looks like
---------------------------
- `00_Inbox/` is empty after the extractor runs.
- The vault's `20_Evergreen/` count is unchanged.
- The runner reports `pass: true`, `notes_created: 0`.
