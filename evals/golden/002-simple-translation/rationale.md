# Case 002 — Simple translation

Why this case matters
---------------------
Tests the materiality gate against a common ChatGPT usage pattern:
"translate this for me". Translations are by definition *transient
artifacts the user could re-derive on demand*. They must not become
learnings or evergreens.

Failure modes
-------------
- The extractor treats the "fact" that 会议改到周二了 = "the meeting
  is rescheduled to Tuesday" as durable knowledge. (precision miss)
- An "evergreen note: Chinese meeting phrases" appears. (hard-fail)
