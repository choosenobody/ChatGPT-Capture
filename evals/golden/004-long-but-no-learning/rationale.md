# Case 004 — Long but no learning

Why this case matters
---------------------
Length of conversation is *not* a signal of materiality. This case
is long (5 turns) but every turn is small-talk, a haiku, a coffee
shop list, or a capital-of-Australia lookup.

Failure modes
-------------
- The extractor rewards verbosity: it writes a summary note.
  (precision miss)
- The librarian promotes a "Tokyo coffee shop list" evergreen.
  (hard-fail: trivial -> Evergreen)
- A raw transcript is dumped into the long-term vault. (hard-fail:
  raw full conversation copied)
