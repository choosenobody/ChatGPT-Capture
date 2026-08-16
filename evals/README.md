# ChatGPT-Capture — Knowledge Quality Golden Set V1

This directory holds the regression harness for the
**Learning Extractor** + **Knowledge Librarian** prompts that landed
in PR #1 (`feat/v1-capture-pipeline`). It does not ship a model and
it does not modify `prompts/`, `server/`, `extension/`, or `hermes/`.

## Why this exists

The whole knowledge system optimises for "preserve the minimum amount
of highest-value cognition", not "preserve as much as possible". That
makes **false positives more dangerous than false negatives**:

* A wrong note lives in the vault for months.
* A missed note can be re-discovered on the next capture.

So the rubric weights FP heavily, and any of seven **hard-fail
conditions** instantly zeroes a case (see `RUBRIC.md`).

## How to run

```bash
python3 evals/run_eval.py
```

This runs all 24 golden cases through the `mock-stub` adapter (zero
LLM tokens, fully deterministic) and writes:

* `evals/results/latest.json` — machine-readable score
* `evals/results/latest.md`   — human-readable scorecard
* `evals/results/baseline-v1.md` — frozen baseline report

To use the production Hermes adapter instead:

```bash
EVAL_ADAPTER=hermes MODEL_COMMAND="claude -p '{prompt}'" \
    python3 evals/run_eval.py --output evals/results/latest.json
```

The `hermes` adapter shells out to whatever `MODEL_COMMAND` you set,
substituting `{prompt}` and `{input}`.

## How to add a new case

Each case is a directory under `evals/golden/NNN-short-name/`:

```
evals/golden/025-my-new-case/
├── conversation.jsonl     # required, JSONL with schema_version=1
├── vault_before/          # optional; required when level == librarian
├── expected.yaml          # required; semantic expectations
└── rationale.md           # required; why this case matters
```

`expected.yaml` follows the schema in `RUBRIC.md` plus:

```yaml
level: extractor | librarian           # default: extractor
material_learning: true | false
expected_learning_count:
  min: 1
  max: 1
expected_action:                       # one of:
  - create_learning                    # inbox note
  - move_to_learnings                  # librarian lifecycle
  - create_evergreen                   # evergreen created
  - update_entity                      # 30_Entities update
  - update_decision                    # 40_Decisions update
  - archive                            # moved to 90_Reviews/Archive
  - no_note                            # zero-output expectation
expected_belief_change: new | strengthened | weakened | reversed | unchanged
expected_topics: [RONIC, reinvestment]
expected_entities: [null]              # null means "no entity"
evergreen:
  expected: true
  concept: "High RONIC reduces reinvestment required for growth"
epistemic:
  must_not_promote_to_fact: false      # true for hypothesis/fact-update cases
forbidden:                             # things the adapter must NOT do
  - full_conversation_summary
  - transient_numbers
  - duplicate_note
  - private_credential
  - hypothesis_to_fact
  - silent_belief_overwrite
  - trivial_evergreen
  - duplicate_evergreen
  - raw_full_conversation
  - auto_investment_decision
hard_fail_conditions:                  # cross-checked against the seven sentinel labels
  - hypothesis_promoted
```

The runner reads the YAML and never depends on exact Markdown
wording. Scoring is over:

* action labels (which folders the adapter wrote into)
* note counts (how many inbox / learning / evergreen files appear)
* concept presence (the evergreen `concept` field if it appears)
* forbidden patterns scanned from the post-run vault state
* declared belief_change direction

## How to interpret the score

* **Overall / 100** — sum of A..G, capped at 0 on any hard-fail.
* **Cases passed / total** — per-case `pass_` is `score ≥ 70` and no
  hard-fail.
* **False Positive Rate** — share of cases with a precision miss.
* **Duplicate Rate** — share of cases with a dedup violation.
* **Compression ratio** — `raw → candidate → retained → evergreen`.
  A healthy V1 baseline is `24 → 17 → 11 → 5`. Anything approaching
  `24 → 60+` means the adapter is over-extracting.

## Why we don't do exact-text matching

The harness never asserts on a specific Markdown phrase. Two reasons:

1. The production prompts are deliberately terse; minor wording
   drift between model revisions should not break the gate.
2. The user-facing value is **what landed in the vault**, not
   **how it was phrased**. Folder placement, count, belief direction,
   and concept presence are the durable signals.

## Hard-fail coverage matrix

The 24 cases cover all seven hard-fail conditions across both L1 and
L2 runs:

| Hard-fail | Tagged in case(s) |
| --- | --- |
| 1. credential leak | 005 |
| 2. hypothesis → fact | 013, 015, 021 |
| 3. silent belief overwrite | 010, 011 |
| 4. trivial → Evergreen | 001, 002, 003, 004 |
| 5. duplicate Evergreen | 008, 020 |
| 6. raw full conversation copied | 018 |
| 7. auto investment decision | 019 |

`baseline-v1.md` reports each tagged violation as
`hard_fail_triggered: true` and zeroes the case score — that gap is
the entire point of the baseline.

## CI

V1 ships a manual eval workflow only. There is **no** blocking CI
gate yet. To run the eval in CI later, expose:

```yaml
- name: Knowledge Quality baseline
  run: python3 evals/run_eval.py
```

The runner exits 0 even on hard-fail cases (so the run is not
flaky); the JSON / Markdown outputs are the durable artefact.
