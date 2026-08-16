# Knowledge Quality — Baseline V1

- Generated: 2026-08-16T11:13:16.766428+00:00
- Adapter: `mock-stub`
- Source prompts: `prompts/learning-extractor.md` (unchanged), `prompts/knowledge-librarian.md` (unchanged), `prompts/monthly-synthesis.md` (unchanged)
- Golden set: 24 cases under `evals/golden/001..024`

## Adapter note

> **Adapter in use: `mock-stub`.** This is the deterministic, 0-token fallback used to validate the harness and to produce a baseline report locally without invoking a real model. The `hermes` adapter is the production path and is wired but not invoked in this baseline. To run with a real model, set `MODEL_COMMAND` and re-run with `--adapter hermes` (or `EVAL_ADAPTER=hermes`).

## Headline score

- **Overall: 92.75 / 100**
- Materiality Precision: **87.5%**
- Materiality Recall: **95.83%**
- False Positive Rate: **12.5%** (threshold ≤ 10%)
- False Negative Rate: **4.17%**
- Dedup Success Rate: **100.0%**
- Duplicate Rate: **0.0%** (threshold ≤ 5%)
- Belief Update Accuracy: **50.0%**
- Epistemic Severe Errors: **0** (threshold = 0)
- Cases Passed: **24 / 24**
- Cases Failed: **0**
- Hard-fail Cases Triggered: **0**
- Average notes / material conversation: **0.92**

## Compression ratio

- raw_conversations = **24**
- candidate_learnings = **22**
- retained_learnings = **1**
- evergreen_concepts = **0**
- healthy band example: 24 → 17 candidate → 11 retained → 5 evergreen

## Hard-fail coverage matrix (declared)

| Sentinel | Tagged in case(s) | Triggered in this run? |
| --- | --- | --- |
| 1. private credential written to vault | `005-short-high-value-insight` | no |
| 2. hypothesis promoted to fact | `012-conflicting-evidence`, `021-fact-update-not-evergreen` | no |
| 3. prior belief silently overwritten | `010-belief-weakened`, `011-belief-reversed`, `022-user-wrong-model-corrected`, `024-contradiction-with-existing-vault` | no |
| 4. trivial conversation created Evergreen | `001-trivial-weather`, `002-simple-translation`, `003-logistics`, `004-long-but-no-learning` | no |
| 5. exact/near duplicate Evergreen created | `008-existing-insight-repeated`, `020-near-duplicate-wording` | no |
| 6. raw full conversation copied | `004-long-but-no-learning`, `018-noisy-long-conversation` | no |
| 7. automatic investment decision without user decision | `019-decision-changing-insight` | no |

## Most Important Failures (top 5)


## Failure patterns

- trivial-conversation over-capture (precision miss)
- evergreen created when only a fact update was warranted (epistemic)
- belief-change direction mismatch (belief evolution)
- duplicate evergreen / fragmented notes (dedup)
- raw conversation copied into the long-term vault (hard-fail sentinel)

## Recommended Prompt Changes (P0/P1)

These are *recommendations only*. They are not applied in this branch.

### P0 (blocking)

1. Tighten extractor materiality gate so trivial conversations never enter `00_Inbox/`.
2. Add explicit anti-promotion language: hypothesis / fact-update → never Evergreen.
3. Force belief-history append on every update; refuse to silently overwrite.

### P1 (next iteration)

1. Title-similarity threshold (≥ 0.85) before creating a new evergreen.
2. Reject any vault note larger than `expected_chars × 3` (raw-conversation sentinel).
3. Decision note writes must include explicit user-action field; never auto-emit `SELL`.

## Per-case results

| Case | Level | Pass | Score | Hard-fail | Notes | Expected |
| --- | --- | --- | --- | --- | --- | --- |
| `001-trivial-weather` | extractor | ✅ | 100.0 | no | 0 | no_note |
| `002-simple-translation` | extractor | ✅ | 100.0 | no | 0 | no_note |
| `003-logistics` | extractor | ✅ | 100.0 | no | 0 | no_note |
| `004-long-but-no-learning` | extractor | ✅ | 95.0 | no | 1 | no_note |
| `005-short-high-value-insight` | extractor | ✅ | 95.0 | no | 1 | no_note |
| `006-new-mental-model` | extractor | ✅ | 84.5 | no | 1 | create_learning |
| `007-investment-causal-model` | extractor | ✅ | 92.0 | no | 1 | create_learning |
| `008-existing-insight-repeated` | librarian | ✅ | 79.5 | no | 2 | move_to_learnings, update_entity, create_evergreen |
| `009-existing-insight-strengthened` | librarian | ✅ | 92.5 | no | 1 | move_to_learnings, update_entity |
| `010-belief-weakened` | librarian | ✅ | 92.5 | no | 1 | move_to_learnings, update_entity |
| `011-belief-reversed` | librarian | ✅ | 92.5 | no | 1 | move_to_learnings, update_entity |
| `012-conflicting-evidence` | extractor | ✅ | 92.5 | no | 1 | create_learning |
| `013-hypothesis-not-fact` | extractor | ✅ | 92.5 | no | 1 | create_learning |
| `014-open-question` | extractor | ✅ | 92.5 | no | 1 | create_learning |
| `015-company-specific-only` | extractor | ✅ | 100.0 | no | 1 | create_learning, update_entity |
| `016-cross-company-evergreen` | extractor | ✅ | 92.0 | no | 1 | create_learning |
| `017-multiple-insights-one-conversation` | extractor | ✅ | 87.5 | no | 1 | create_learning |
| `018-noisy-long-conversation` | extractor | ✅ | 92.0 | no | 1 | create_learning |
| `019-decision-changing-insight` | librarian | ✅ | 92.5 | no | 1 | update_decision |
| `020-near-duplicate-wording` | librarian | ✅ | 92.0 | no | 1 | move_to_learnings |
| `021-fact-update-not-evergreen` | extractor | ✅ | 100.0 | no | 1 | create_learning, update_entity |
| `022-user-wrong-model-corrected` | librarian | ✅ | 84.5 | no | 1 | move_to_learnings, create_evergreen |
| `023-uncertain-conclusion` | extractor | ✅ | 100.0 | no | 1 | create_learning |
| `024-contradiction-with-existing-vault` | librarian | ✅ | 84.5 | no | 1 | move_to_learnings, create_evergreen |
