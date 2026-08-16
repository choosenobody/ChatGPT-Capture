# Case 003 — Logistics

Why this case matters
---------------------
The extractor prompt explicitly lists *logistics* as one of the
categories that must not be preserved. This case checks that the
guardrail actually fires when the conversation is purely operational.

Failure modes
-------------
- "Logistics is hard" or "Customs delays are common" promoted to
  evergreen. (hard-fail)
- The DHL tracking number persisted as a "fact" in the vault.
  (precision miss, but also a small data-handling concern)
