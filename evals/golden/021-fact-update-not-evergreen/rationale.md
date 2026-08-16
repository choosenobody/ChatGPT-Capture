# Case 021 — Fact update, not evergreen (VAT 6% → 9%)

Why this case matters
---------------------
The user explicitly asks "does that change anything evergreen?"
The answer is no — this is the canonical fact-update case. A bare
percentage-point change is exactly what the extractor prompt
forbids generalising.

Failure modes
-------------
- A "VAT-driven SaaS pricing pressure" evergreen is created.
  (precision + evergreen quality miss)
- The number is recorded without a date/quarter tag, so it
  silently rots. (epistemic miss — bare numbers in vaults)
