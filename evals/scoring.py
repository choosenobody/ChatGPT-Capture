"""Scoring engine for the Knowledge Quality Golden Set V1.

Each golden case declares a YAML `expected.yaml`. The runner produces
two diffs:

* L1 (extractor) — what landed in `00_Inbox/` after the extractor ran.
* L2 (librarian) — what landed in `10_Learnings/`, `20_Evergreen/`,
  `30_Entities/`, `40_Decisions/`, `90_Reviews/Archive/` after the
  librarian lifecycle ran.

This module translates those diffs + the `expected.yaml` into a
100-point score aligned with `evals/RUBRIC.md`:

* A. Materiality (30) — Precision 20 (FP heavy penalty) + Recall 10.
* B. Epistemic Discipline (20) — hypothesis→fact, fact-update→evergreen.
* C. Belief Evolution (15) — direction accuracy, history preservation.
* D. Deduplication (15) — duplicate evergreen, near-duplicate titles.
* E. Evergreen Quality (10) — reusable / mechanism / cross-context.
* F. Knowledge Compression (5) — weak notes -> one stronger model.
* G. Linking Quality (5) — meaningful links, not graph-density theater.

Hard-fail cases (any of the seven conditions in `RUBRIC.md`) cap the
case score at 0 and add to the `Epistemic Severe Errors` counter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from adapters.base import VaultDiff


@dataclass
class ExpectedCase:
    """Normalized representation of an `expected.yaml` file."""

    case_id: str
    raw: dict[str, Any]
    material_learning: bool
    expected_learning_count: dict[str, int]
    expected_actions: list[str]
    expected_belief_change: str | None
    expected_topics: list[str]
    expected_entities: list[str]
    evergreen_expected: bool
    evergreen_concept: str | None
    epistemic_must_not_promote: bool
    forbidden: list[str]
    hard_fail_conditions: list[str]
    level: str  # "extractor" or "librarian"
    requires_vault_before: bool
    description: str = ""

    @classmethod
    def load(cls, case_dir: Path) -> "ExpectedCase":
        yaml_path = case_dir / "expected.yaml"
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        level = (data.get("level") or "extractor").lower()
        counts = data.get("expected_learning_count") or {"min": 0, "max": 0}
        return cls(
            case_id=case_dir.name,
            raw=data,
            material_learning=bool(data.get("material_learning", False)),
            expected_learning_count={"min": int(counts.get("min", 0)),
                                     "max": int(counts.get("max", 0))},
            expected_actions=list(data.get("expected_action") or ["no_note"]),
            expected_belief_change=data.get("expected_belief_change"),
            expected_topics=list(data.get("expected_topics") or []),
            expected_entities=list(data.get("expected_entities") or []),
            evergreen_expected=bool((data.get("evergreen") or {}).get("expected", False)),
            evergreen_concept=(data.get("evergreen") or {}).get("concept"),
            epistemic_must_not_promote=bool(
                (data.get("epistemic") or {}).get("must_not_promote_to_fact", False)
            ),
            forbidden=list(data.get("forbidden") or []),
            hard_fail_conditions=list(data.get("hard_fail_conditions") or []),
            level=level,
            requires_vault_before=bool(data.get("requires_vault_before", False)),
            description=str(data.get("description") or ""),
        )


@dataclass
class CaseScore:
    case_id: str
    level: str
    pass_: bool
    hard_fail_triggered: bool
    hard_fail_reasons: list[str]
    hard_fail_coverage: list[str]
    material_section: dict[str, Any]
    epistemic_section: dict[str, Any]
    belief_section: dict[str, Any]
    dedup_section: dict[str, Any]
    evergreen_section: dict[str, Any]
    compression_section: dict[str, Any]
    linking_section: dict[str, Any]
    notes_created: int
    notes_expected_min: int
    notes_expected_max: int
    expected_actions: list[str]
    actual_actions: list[str]
    evergreen_observed: bool
    evergreen_expected: bool
    forbidden_observed: list[str] = field(default_factory=list)
    total_score: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "level": self.level,
            "pass": self.pass_,
            "hard_fail_triggered": self.hard_fail_triggered,
            "hard_fail_reasons": self.hard_fail_reasons,
            "hard_fail_coverage": self.hard_fail_coverage,
            "total_score": self.total_score,
            "breakdown": self.breakdown,
            "notes_created": self.notes_created,
            "notes_expected_min": self.notes_expected_min,
            "notes_expected_max": self.notes_expected_max,
            "expected_actions": self.expected_actions,
            "actual_actions": self.actual_actions,
            "evergreen_observed": self.evergreen_observed,
            "evergreen_expected": self.evergreen_expected,
            "forbidden_observed": self.forbidden_observed,
            "material_section": self.material_section,
            "epistemic_section": self.epistemic_section,
            "belief_section": self.belief_section,
            "dedup_section": self.dedup_section,
            "evergreen_section": self.evergreen_section,
            "compression_section": self.compression_section,
            "linking_section": self.linking_section,
        }


def _actions_from_diff(diff: VaultDiff) -> list[str]:
    """Map a VaultDiff into a set of high-level action labels."""
    actions: list[str] = []
    if diff.new_inbox_notes > 0:
        actions.append("create_learning")
    if diff.inbox_to_learnings > 0:
        actions.append("move_to_learnings")
    if diff.inbox_to_archive > 0:
        actions.append("archive")
    if diff.inbox_to_evergreen > 0:
        actions.append("create_evergreen")
    if diff.inbox_to_entities > 0:
        actions.append("update_entity")
    if diff.inbox_to_decisions > 0:
        actions.append("update_decision")
    if not actions:
        actions.append("no_note")
    return actions


def _detect_hard_fails(expected: ExpectedCase, diff: VaultDiff,
                       evergreen_observed: bool, full_text_chars: int) -> list[str]:
    """Return triggered hard-fail condition labels."""
    triggers: list[str] = []
    text_blob_parts: list[str] = []
    if hasattr(diff, "raw_text_chars_written"):
        pass  # not directly used; surface via separate fields below.
    # We rely on the runner to inspect the actual written files.
    if full_text_chars > 80_000:
        triggers.append("raw_full_conversation_copied")
    return triggers


def score_case(
    expected: ExpectedCase,
    *,
    notes_created: int,
    actions: list[str],
    evergreen_observed: bool,
    forbidden_observed: list[str],
    diff: VaultDiff,
    full_text_chars: int,
    belief_change_observed: str | None = None,
) -> CaseScore:
    """Compute one case's score and return a structured CaseScore.

    The hard-fail conditions from `RUBRIC.md` are evaluated last so the
    breakdown still reflects what the adapter *attempted*.
    """
    # ---- A. Materiality ----
    precision_hits, precision_misses = 0, 0
    recall_hits, recall_misses = 0, 0
    if expected.material_learning:
        if notes_created >= expected.expected_learning_count["min"]:
            recall_hits += 1
        else:
            recall_misses += 1
        if notes_created <= expected.expected_learning_count["max"]:
            precision_hits += 1
        else:
            precision_misses += 1
    else:
        if notes_created == 0:
            precision_hits += 1
        else:
            precision_misses += 1

    materiality_precision_score = 20.0 if precision_misses == 0 else max(
        0.0, 20.0 - (precision_misses * 5.0)
    )
    materiality_recall_score = 10.0 if recall_misses == 0 else max(
        0.0, 10.0 - (recall_misses * 5.0)
    )

    # ---- B. Epistemic Discipline ----
    epistemic_score = 20.0
    epistemic_notes: list[str] = []
    if expected.epistemic_must_not_promote and evergreen_observed:
        epistemic_score -= 10.0
        epistemic_notes.append(
            "hypothesis or fact-update promoted to evergreen"
        )
    if forbidden_observed and "duplicate_note" in forbidden_observed:
        epistemic_score -= 5.0
        epistemic_notes.append("duplicate note created within conversation")
    epistemic_score = max(0.0, epistemic_score)

    # ---- C. Belief Evolution ----
    belief_score = 15.0
    belief_notes: list[str] = []
    if expected.expected_belief_change and belief_change_observed:
        if belief_change_observed != expected.expected_belief_change:
            belief_score -= 7.5
            belief_notes.append(
                f"belief_change mismatch: expected {expected.expected_belief_change}, "
                f"observed {belief_change_observed}"
            )
    belief_score = max(0.0, belief_score)

    # ---- D. Deduplication ----
    dedup_score = 15.0
    dedup_notes: list[str] = []
    if forbidden_observed and "duplicate_note" in forbidden_observed:
        dedup_score -= 15.0
        dedup_notes.append("duplicate note explicitly forbidden and present")
    dedup_score = max(0.0, dedup_score)

    # ---- E. Evergreen Quality ----
    evergreen_score = 0.0
    evergreen_notes: list[str] = []
    if expected.evergreen_expected and evergreen_observed:
        evergreen_score = 10.0
    elif expected.evergreen_expected and not evergreen_observed:
        evergreen_score = 2.0  # partial credit for awareness
        evergreen_notes.append("expected evergreen but none observed")
    elif not expected.evergreen_expected and evergreen_observed:
        evergreen_score = 5.0  # partial credit: an evergreen was created
        evergreen_notes.append("unexpected evergreen created")
    else:
        evergreen_score = 10.0

    # ---- F. Knowledge Compression ----
    compression_score = 5.0
    if notes_created > expected.expected_learning_count["max"] + 1:
        compression_score = max(0.0, 5.0 - 2.5)
    if notes_created > expected.expected_learning_count["max"] + 3:
        compression_score = 0.0

    # ---- G. Linking Quality ----
    linking_score = 5.0
    if actions and "update_entity" in actions and not expected.expected_entities:
        linking_score = max(0.0, 5.0 - 2.0)

    breakdown = {
        "materiality_precision": materiality_precision_score,
        "materiality_recall": materiality_recall_score,
        "epistemic": epistemic_score,
        "belief": belief_score,
        "dedup": dedup_score,
        "evergreen": evergreen_score,
        "compression": compression_score,
        "linking": linking_score,
    }
    total = sum(breakdown.values())

    # ---- Hard-fail conditions ----
    # `forbidden_observed` is the OBSERVED failure (what the adapter
    # actually did wrong). `expected.hard_fail_conditions` is a
    # DECLARED coverage marker — i.e. "this case is the canonical
    # test for hard-fail condition X". We must keep them separate
    # so a clean run on a sentinel-tagged case is recorded as
    # `coverage_marker: X` (no trigger) rather than as `hard_fail`.
    hard_fail_reasons: list[str] = []
    if forbidden_observed:
        if "private_credential" in forbidden_observed:
            hard_fail_reasons.append("private credential written to vault")
        if "hypothesis_to_fact" in forbidden_observed:
            hard_fail_reasons.append("hypothesis promoted to fact")
        if "silent_belief_overwrite" in forbidden_observed:
            hard_fail_reasons.append("prior belief silently overwritten")
        if "trivial_evergreen" in forbidden_observed:
            hard_fail_reasons.append("trivial conversation created Evergreen")
        if "duplicate_evergreen" in forbidden_observed:
            hard_fail_reasons.append("exact/near duplicate Evergreen created")
        if "raw_full_conversation" in forbidden_observed:
            hard_fail_reasons.append("raw full conversation copied into long-term vault")
        if "auto_investment_decision" in forbidden_observed:
            hard_fail_reasons.append("automatic investment decision without user decision")

    pass_ = (total >= 70.0) and (not hard_fail_reasons)
    if hard_fail_reasons:
        total = 0.0

    return CaseScore(
        case_id=expected.case_id,
        level=expected.level,
        pass_=pass_,
        hard_fail_triggered=bool(hard_fail_reasons),
        hard_fail_reasons=hard_fail_reasons,
        hard_fail_coverage=list(expected.hard_fail_conditions),
        material_section={
            "precision_hits": precision_hits,
            "precision_misses": precision_misses,
            "recall_hits": recall_hits,
            "recall_misses": recall_misses,
        },
        epistemic_section={"notes": epistemic_notes},
        belief_section={"notes": belief_notes,
                        "expected": expected.expected_belief_change,
                        "observed": belief_change_observed},
        dedup_section={"notes": dedup_notes},
        evergreen_section={"notes": evergreen_notes,
                           "expected_concept": expected.evergreen_concept,
                           "observed": evergreen_observed},
        compression_section={},
        linking_section={},
        notes_created=notes_created,
        notes_expected_min=expected.expected_learning_count["min"],
        notes_expected_max=expected.expected_learning_count["max"],
        expected_actions=expected.expected_actions,
        actual_actions=actions,
        evergreen_observed=evergreen_observed,
        evergreen_expected=expected.evergreen_expected,
        forbidden_observed=forbidden_observed,
        total_score=total,
        breakdown=breakdown,
    )


__all__ = [
    "ExpectedCase",
    "CaseScore",
    "score_case",
]
