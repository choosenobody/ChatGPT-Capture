# Knowledge Quality Golden Set V1 — Scoring Rubric

The scoring rubric below is the source of truth for the
`evals/run_eval.py` engine. Every score that appears in
`evals/results/latest.json`, `latest.md`, and `baseline-v1.md` is
derived from this rubric.

Total: **100 points** per case. Hard-fail conditions (see below) cap
the case score at **0** and add to the **Epistemic Severe Errors**
counter.

## A. Materiality — 30 points

The most important axis. False Positive (FP) is heavily penalised
because the optimisation target is "preserve the minimum amount of
highest-value cognition", not "preserve as much as possible".

| Component | Points | Notes |
| --- | --- | --- |
| **Precision** | 20 | FP misses deduct **5 points each**, with a floor of 0. |
| **Recall** | 10 | FN misses deduct **5 points each**, with a floor of 0. |

### Why FP > FN in penalty weight

A wrong evergreen or a wrong note lives in the user's vault forever.
A missed note can be re-discovered. Therefore:

* 1 FP costs **5 points**.
* 1 FN costs **5 points** (same numeric penalty), but the **count**
  is reported separately so prompt authors can prioritise FP.

## B. Epistemic Discipline — 20 points

Distinct from materiality. This axis catches "saved the right thing
in the wrong epistemic form":

| Trigger | Deduction |
| --- | --- |
| Hypothesis or fact-update promoted to Evergreen | **−10** |
| Duplicate note within one conversation | **−5** |
| Other epistemic drift | **−2** per minor violation |

## C. Belief Evolution — 15 points

When a case declares `expected_belief_change`, the runner checks the
written inbox note's frontmatter. A mismatch deducts **7.5 points**.

The rubric is direction-only (`new`, `strengthened`, `weakened`,
`reversed`, `unchanged`) — it does not check the magnitude of a
confidence shift.

## D. Deduplication — 15 points

A single hard-fail condition: if `forbidden: duplicate_note` is set
on the case and the adapter still creates duplicates, the entire
**15-point** section is zeroed.

## E. Evergreen Quality — 10 points

| Observed | Expected | Score |
| --- | --- | --- |
| yes | yes | **10** |
| no | yes | **2** (partial credit for restraint) |
| yes | no | **5** (over-promotion penalty; case-level hard-fail still fires) |
| no | no | **10** |

## F. Knowledge Compression — 5 points

If the adapter creates `expected_learning_count.max + 1` notes or
more, score drops to 2.5. If it creates `expected_learning_count.max
+ 3` notes or more, score drops to 0.

## G. Linking Quality — 5 points

When the adapter promotes a note to `30_Entities/` but the case
expects no entity link, deduct 2 points. The runner never rewards
graph density for its own sake.

## Hard-fail conditions

Any of the following instantly zeroes the case and contributes to
`Epistemic Severe Errors`:

1. **private credential written to vault** — `sk-…`, `BEGIN PRIVATE
   KEY`, `seed phrase:` style patterns observed in any vault file.
2. **hypothesis promoted to fact** — `must_not_promote_to_fact: true`
   in `expected.yaml` and the adapter wrote Evergreen.
3. **prior belief silently overwritten** — librarian did not append a
   belief-history entry on a `weakened` / `reversed` update.
4. **trivial conversation creates Evergreen** — case declared
   `material_learning: false` and adapter wrote `20_Evergreen/`.
5. **exact/near duplicate Evergreen created** — multiple evergreen
   notes produced with title similarity ≥ 0.85.
6. **raw full conversation copied into long-term vault** — file size
   exceeds the `expected_chars × 3` heuristic.
7. **automatic investment decision made without user decision** —
   adapter wrote a `40_Decisions/` note containing `SELL` without a
   `user_action:` field.

## Dashboard metrics

The baseline report always emits these, in this order:

1. Materiality Precision (%)
2. Materiality Recall (%)
3. False Positive Rate (%)
4. False Negative Rate (%)
5. Dedup Success Rate (%)
6. Duplicate Rate (%)
7. Belief Update Accuracy (%)
8. Epistemic Error Rate / Epistemic Severe Errors (count)
9. Evergreen Precision (%)
10. Average Notes / Material Conversation
11. Compression Ratio (raw → candidate → retained → evergreen)

## Acceptance thresholds (advisory, not blocking)

| Metric | Threshold |
| --- | --- |
| False Positive Rate | ≤ 10% |
| Duplicate Evergreen Rate | ≤ 5% |
| Epistemic Severe Error | = 0 |
| Silent Belief Overwrite | = 0 |
| Credential Leak | = 0 |

These are surfaced in `baseline-v1.md` for the human reviewer to
act on. CI does not hard-block on them in V1.
