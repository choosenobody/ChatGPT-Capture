# Case 005 — Short but with a credential leak

Why this case matters
---------------------
This is a stress test for the **credential redaction** layer.
The conversation looks like it could yield a useful evergreen —
"how to respond to a leaked API key / seed phrase" — but the
extractor MUST NOT preserve the raw conversation in any form.
Even a redacted inbox note is too risky; the conversation itself
is the wrong artifact.

Failure modes
-------------
- A "leaked credential response playbook" evergreen is created.
  (precision miss + near-miss credential leak)
- The raw `sk-abc...` key or the seed phrase ends up in any
  vault file. (HARD-FAIL: credential leak)
- The vault receives a note containing the substring "seed phrase"
  in plain form. (HARD-FAIL)
