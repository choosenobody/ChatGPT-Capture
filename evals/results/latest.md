# Latest eval — Knowledge Quality Golden Set V1

- Timestamp: 2026-08-16T11:13:16.765912+00:00
- Adapter: **mock-stub**
- Overall score: **92.75 / 100**

## Dashboard

| Metric | Value | Threshold |
| --- | --- | --- |
| Materiality Precision | 87.5% | — |
| Materiality Recall | 95.83% | — |
| False Positive Rate | 12.5% | ≤ 10% |
| False Negative Rate | 4.17% | — |
| Dedup Success Rate | 100.0% | — |
| Duplicate Rate | 0.0% | ≤ 5% |
| Belief Update Accuracy | 50.0% | — |
| Epistemic Severe Errors | 0 | = 0 |
| Hard-fail cases | 0 | — |

## Cases

| ID | Level | Pass | Score | Hard-fail | Notes |
| --- | --- | --- | --- | --- | --- |
| `001-trivial-weather` | extractor | ✅ | 100.0 | no | 0 |
| `002-simple-translation` | extractor | ✅ | 100.0 | no | 0 |
| `003-logistics` | extractor | ✅ | 100.0 | no | 0 |
| `004-long-but-no-learning` | extractor | ✅ | 95.0 | no | 1 |
| `005-short-high-value-insight` | extractor | ✅ | 95.0 | no | 1 |
| `006-new-mental-model` | extractor | ✅ | 84.5 | no | 1 |
| `007-investment-causal-model` | extractor | ✅ | 92.0 | no | 1 |
| `008-existing-insight-repeated` | librarian | ✅ | 79.5 | no | 2 |
| `009-existing-insight-strengthened` | librarian | ✅ | 92.5 | no | 1 |
| `010-belief-weakened` | librarian | ✅ | 92.5 | no | 1 |
| `011-belief-reversed` | librarian | ✅ | 92.5 | no | 1 |
| `012-conflicting-evidence` | extractor | ✅ | 92.5 | no | 1 |
| `013-hypothesis-not-fact` | extractor | ✅ | 92.5 | no | 1 |
| `014-open-question` | extractor | ✅ | 92.5 | no | 1 |
| `015-company-specific-only` | extractor | ✅ | 100.0 | no | 1 |
| `016-cross-company-evergreen` | extractor | ✅ | 92.0 | no | 1 |
| `017-multiple-insights-one-conversation` | extractor | ✅ | 87.5 | no | 1 |
| `018-noisy-long-conversation` | extractor | ✅ | 92.0 | no | 1 |
| `019-decision-changing-insight` | librarian | ✅ | 92.5 | no | 1 |
| `020-near-duplicate-wording` | librarian | ✅ | 92.0 | no | 1 |
| `021-fact-update-not-evergreen` | extractor | ✅ | 100.0 | no | 1 |
| `022-user-wrong-model-corrected` | librarian | ✅ | 84.5 | no | 1 |
| `023-uncertain-conclusion` | extractor | ✅ | 100.0 | no | 1 |
| `024-contradiction-with-existing-vault` | librarian | ✅ | 84.5 | no | 1 |
