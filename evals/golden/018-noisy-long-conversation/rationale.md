# Case 018 — Noisy long conversation with one core insight

Why this case matters
---------------------
The signal-to-noise ratio is the user's enemy. A 5-turn chat with
a joke, shipping-status chatter, and one real insight must yield
exactly one durable note. Capturing the noise is a precision miss
*and* a near-miss on the raw-conversation hard-fail.

Failure modes
-------------
- All 5 turns preserved as a "summary" note. (HARD-FAIL: raw full
  conversation copied into long-term vault)
- The joke and shipping status are recorded as separate learnings.
  (precision miss)
- The agent-first insight is recorded but without the failure
  conditions. (evergreen quality partial)
