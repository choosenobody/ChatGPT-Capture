# Case 017 — Multiple insights in one conversation

Why this case matters
---------------------
The extractor prompt warns against creating duplicate notes within
one conversation; this is the *opposite* problem. Three distinct
insights must remain three notes. A naive summary-style extractor
collapses them into one and the user loses mechanism-level fidelity.

Failure modes
-------------
- 1 combined "SaaS revenue durability" note. (compression miss +
  recall miss — the three mechanisms are gone)
- 3 inbox notes with the same title. (dedup miss — distinct
  mechanisms deserve distinct titles)
- A single evergreen is created, but no inbox notes. (recall miss)
