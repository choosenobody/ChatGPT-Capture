#!/usr/bin/env python3
"""Knowledge Quality Golden Set V1 — eval runner.

Usage:

    python3 evals/run_eval.py
    python3 evals/run_eval.py --adapter mock-stub
    python3 evals/run_eval.py --adapter hermes --output evals/results/latest.json
    EVAL_ADAPTER=hermes python3 evals/run_eval.py

Outputs:

    evals/results/latest.json     — full machine-readable score
    evals/results/latest.md       — human-readable scorecard
    evals/results/baseline-v1.md  — frozen baseline report (V1 prompt)

Design notes:

* The runner never modifies `prompts/`, `hermes/`, `server/`, or
  `extension/`. Every filesystem write happens inside a tempdir scoped
  to a single case run.

* Each golden case declares a `level` field in `expected.yaml`:
  - `extractor` => L1 only (no `vault_before/`, no librarian).
  - `librarian` => L1 + L2: copy `vault_before/`, run the extractor
    on the conversation, then run the librarian on the resulting
    vault.

* Hard-fail cases are *not* deleted or down-weighted. They are run,
  scored honestly, and recorded as `hard_fail_triggered: true` so the
  baseline report captures every violation. This is the only way the
  baseline can be a true source-of-truth for downstream prompt
  improvements.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

# Allow `python3 evals/run_eval.py` to find the evals package even when
# the working directory is the repo root.
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from adapters import get_adapter  # noqa: E402
from adapters.base import VaultDiff, make_temp_vault_from_fixture  # noqa: E402
from scoring import CaseScore, ExpectedCase, score_case  # noqa: E402

GOLDEN_DIR = ROOT / "golden"
RESULTS_DIR = ROOT / "results"
DEFAULT_BASELINE = RESULTS_DIR / "baseline-v1.md"


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(__import__("json").loads(line))
        except Exception:
            continue
    return rows


def _list_md(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*.md") if p.is_file())


def _forbidden_observed(expected: ExpectedCase, vault_dir: Path,
                       new_inbox: int = 0, new_evergreen: int = 0) -> list[str]:
    """Scan the vault for forbidden outputs that hard-fail the case.

    `new_inbox` / `new_evergreen` are the *deltas* vs `vault_before/`,
    so we never mis-fire on pre-existing duplicate evergreens in a
    fixture.
    """
    observed: list[str] = []
    inbox = vault_dir / "00_Inbox"
    learnings = vault_dir / "10_Learnings"
    evergreen = vault_dir / "20_Evergreen"
    decisions = vault_dir / "40_Decisions"
    inbox_md = _list_md(inbox) if inbox.exists() else []
    learnings_md = _list_md(learnings) if learnings.exists() else []
    evergreen_md = _list_md(evergreen) if evergreen.exists() else []
    decisions_md = _list_md(decisions) if decisions.exists() else []

    all_md = inbox_md + learnings_md + evergreen_md + decisions_md
    blob = "\n".join(p.read_text(encoding="utf-8", errors="ignore")
                     for p in all_md)

    # 1) Trivial -> Evergreen
    if expected.material_learning is False and evergreen_md:
        observed.append("trivial_evergreen")

    # 2) Hypothesis promoted to fact
    if expected.epistemic_must_not_promote and evergreen_md:
        observed.append("hypothesis_to_fact")

    # 3) Duplicate notes within ONE conversation (delta-based)
    if new_inbox >= 2:
        observed.append("duplicate_note")
    if new_evergreen >= 2:
        observed.append("duplicate_evergreen")

    # 4) Private credential
    if "sk-" in blob or "BEGIN PRIVATE KEY" in blob or "seed phrase" in blob.lower():
        observed.append("private_credential")

    # 5) Raw full conversation copied
    for note in all_md:
        try:
            if note.stat().st_size > 80_000:
                observed.append("raw_full_conversation")
                break
        except OSError:
            pass

    # 6) Automatic investment decision without user action
    for decision in decisions_md:
        body = decision.read_text(encoding="utf-8", errors="ignore")
        if "SELL" in body and "user_action" not in body:
            observed.append("auto_investment_decision")
            break

    return observed


def _run_case(case_dir: Path, adapter_name: str) -> tuple[CaseScore, dict]:
    expected = ExpectedCase.load(case_dir)
    conversation_path = case_dir / "conversation.jsonl"
    fixture_vault = case_dir / "vault_before"

    adapter = get_adapter(adapter_name)

    metrics: dict = {
        "conversation_rows": len(_read_jsonl(conversation_path)),
        "vault_before_files": (
            sum(1 for _ in fixture_vault.rglob("*")) if fixture_vault.exists() else 0
        ),
    }

    if expected.level == "librarian":
        vault_dir = make_temp_vault_from_fixture(fixture_vault)
    else:
        vault_dir = make_temp_vault_from_fixture(None)

    metrics["raw_text_chars_written"] = 0
    metrics["evergreen_observed"] = False
    belief_change_observed: str | None = None

    # Count pre-existing notes that are not part of the new output.
    pre_learnings = (
        len(_list_md(vault_dir / "10_Learnings")) if (vault_dir / "10_Learnings").exists() else 0
    )
    pre_evergreen = (
        len(_list_md(vault_dir / "20_Evergreen")) if (vault_dir / "20_Evergreen").exists() else 0
    )
    pre_inbox = (
        len(_list_md(vault_dir / "00_Inbox")) if (vault_dir / "00_Inbox").exists() else 0
    )
    pre_entities = (
        len(_list_md(vault_dir / "30_Entities")) if (vault_dir / "30_Entities").exists() else 0
    )
    pre_decisions = (
        len(_list_md(vault_dir / "40_Decisions")) if (vault_dir / "40_Decisions").exists() else 0
    )
    # ---- L1: extractor ----
    diff = adapter.extractor_run(
        conversation_path,
        vault_dir,
        conversation_id=expected.case_id,
    )
    inbox_after_extractor = _list_md(vault_dir / "00_Inbox")
    evergreen_after_extractor = _list_md(vault_dir / "20_Evergreen")

    # Inspect created files for belief_change and evergreen hints.
    for note in inbox_after_extractor:
        body = note.read_text(encoding="utf-8", errors="ignore")
        metrics["raw_text_chars_written"] += len(body)
        for line in body.splitlines():
            if line.startswith("belief_change:"):
                belief_change_observed = line.split(":", 1)[1].strip()
            if line.startswith("evergreen_candidate:") and "true" in line:
                metrics["evergreen_observed"] = True

    evergreen_observed = metrics["evergreen_observed"] or bool(evergreen_after_extractor)

    # ---- L2: librarian (only when expected.level == librarian) ----
    if expected.level == "librarian":
        lib_diff = adapter.librarian_run(vault_dir)
        diff = lib_diff

    # Compute NEW notes produced by the pipeline (delta vs fixture).
    learnings_after = _list_md(vault_dir / "10_Learnings") if (vault_dir / "10_Learnings").exists() else []
    evergreen_after = _list_md(vault_dir / "20_Evergreen") if (vault_dir / "20_Evergreen").exists() else []
    entities_after = _list_md(vault_dir / "30_Entities") if (vault_dir / "30_Entities").exists() else []
    decisions_after = _list_md(vault_dir / "40_Decisions") if (vault_dir / "40_Decisions").exists() else []
    inbox_after = _list_md(vault_dir / "00_Inbox") if (vault_dir / "00_Inbox").exists() else []

    new_learnings = max(0, len(learnings_after) - pre_learnings)
    new_evergreen = max(0, len(evergreen_after) - pre_evergreen)
    new_entities = max(0, len(entities_after) - pre_entities)
    new_decisions = max(0, len(decisions_after) - pre_decisions)
    new_inbox = max(0, len(inbox_after) - pre_inbox)

    # `notes_created` for scoring = the new durable artefact the
    # pipeline actually produced in the long-term vault (post-librarian
    # for L2, post-extractor for L1).
    if expected.level == "librarian":
        notes_after_extractor = new_learnings
    else:
        notes_after_extractor = new_inbox

    evergreen_observed = bool(new_evergreen)

    # ---- forbidden scan ----
    forbidden_observed = _forbidden_observed(expected, vault_dir, new_inbox, new_evergreen)

    score = score_case(
        expected,
        notes_created=notes_after_extractor,
        actions=_actions_from_diff(diff),
        evergreen_observed=evergreen_observed,
        forbidden_observed=forbidden_observed,
        diff=diff,
        full_text_chars=metrics["raw_text_chars_written"],
        belief_change_observed=belief_change_observed,
    )

    metrics["new_learnings"] = new_learnings
    metrics["new_evergreen"] = new_evergreen
    metrics["new_entities"] = new_entities
    metrics["new_decisions"] = new_decisions
    metrics["new_inbox"] = new_inbox
    metrics["case_score"] = score.as_dict()
    metrics["vault_files_created"] = diff.created_files
    metrics["vault_files_modified"] = diff.modified_files

    # Cleanup tempdir.
    try:
        shutil.rmtree(vault_dir, ignore_errors=True)
    except Exception:
        pass

    return score, metrics


def _actions_from_diff(diff: VaultDiff) -> list[str]:
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


def _gather_case_dirs() -> list[Path]:
    if not GOLDEN_DIR.exists():
        return []
    return sorted(p for p in GOLDEN_DIR.iterdir() if p.is_dir())


def _aggregate(scores: list[CaseScore]) -> dict:
    """Compute the dashboard metrics that `RUBRIC.md` requires."""
    total = len(scores)
    material_cases = [s for s in scores if s.material_section]
    extractor_cases = [s for s in scores if s.level == "extractor"]
    librarian_cases = [s for s in scores if s.level == "librarian"]
    hard_fail_cases = [s for s in scores if s.hard_fail_triggered]
    pass_cases = [s for s in scores if s.pass_]
    total_score = sum(s.total_score for s in scores)

    # False positive / false negative counts at the *case* granularity.
    fp_cases = [
        s for s in scores
        if s.material_section.get("precision_misses", 0) > 0
    ]
    fn_cases = [
        s for s in scores
        if s.material_section.get("recall_misses", 0) > 0
    ]
    dedup_failures = [s for s in scores if s.dedup_section.get("notes")]
    belief_failures = [s for s in scores if s.belief_section.get("notes")]
    epistemic_severe = sum(
        1 for s in scores if s.hard_fail_triggered and any(
            r in {"hypothesis promoted to fact",
                  "private credential written to vault"}
            for r in s.hard_fail_reasons
        )
    )

    # Compression ratio: candidate learnings vs evergreen concepts.
    candidate_learnings = sum(s.notes_created for s in scores)
    retained_learnings = sum(
        max(0, s.notes_created - 1) for s in scores
        if s.level == "librarian" and s.material_section.get("recall_misses", 0) == 0
    )
    evergreen_concepts = sum(1 for s in scores if s.evergreen_observed)

    overall = round(total_score / total, 2) if total else 0.0

    return {
        "cases_total": total,
        "cases_passed": len(pass_cases),
        "cases_failed": total - len(pass_cases),
        "cases_l1_extractor": len(extractor_cases),
        "cases_l2_librarian": len(librarian_cases),
        "cases_hard_fail_triggered": len(hard_fail_cases),
        "overall_score": overall,
        "materiality_precision_pct": (
            round(100.0 * (1.0 - (len(fp_cases) / total)), 2) if total else 0.0
        ),
        "materiality_recall_pct": (
            round(100.0 * (1.0 - (len(fn_cases) / total)), 2) if total else 0.0
        ),
        "false_positive_rate_pct": (
            round(100.0 * (len(fp_cases) / total), 2) if total else 0.0
        ),
        "false_negative_rate_pct": (
            round(100.0 * (len(fn_cases) / total), 2) if total else 0.0
        ),
        "dedup_success_rate_pct": (
            round(100.0 * (1.0 - (len(dedup_failures) / total)), 2) if total else 0.0
        ),
        "duplicate_rate_pct": (
            round(100.0 * (len(dedup_failures) / total), 2) if total else 0.0
        ),
        "belief_update_accuracy_pct": (
            round(100.0 * (1.0 - (len(belief_failures) / total)), 2) if total else 0.0
        ),
        "epistemic_severe_errors": epistemic_severe,
        "average_notes_per_material_conversation": (
            round(candidate_learnings / max(1, len([s for s in scores if s.material_section])), 2)
        ),
        "compression_ratio": {
            "raw_conversations": total,
            "candidate_learnings": candidate_learnings,
            "retained_learnings": retained_learnings,
            "evergreen_concepts": evergreen_concepts,
        },
    }


def _write_latest_json(scores: list[CaseScore], metrics: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "adapter": metrics.get("adapter", "unknown"),
        "metrics": metrics,
        "cases": [s.as_dict() for s in scores],
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_latest_md(scores: list[CaseScore], metrics: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Latest eval — Knowledge Quality Golden Set V1",
        "",
        f"- Timestamp: {datetime.now(timezone.utc).isoformat()}",
        f"- Adapter: **{metrics.get('adapter', 'unknown')}**",
        f"- Overall score: **{metrics['overall_score']} / 100**",
        "",
        "## Dashboard",
        "",
        "| Metric | Value | Threshold |",
        "| --- | --- | --- |",
        f"| Materiality Precision | {metrics['materiality_precision_pct']}% | — |",
        f"| Materiality Recall | {metrics['materiality_recall_pct']}% | — |",
        f"| False Positive Rate | {metrics['false_positive_rate_pct']}% | ≤ 10% |",
        f"| False Negative Rate | {metrics['false_negative_rate_pct']}% | — |",
        f"| Dedup Success Rate | {metrics['dedup_success_rate_pct']}% | — |",
        f"| Duplicate Rate | {metrics['duplicate_rate_pct']}% | ≤ 5% |",
        f"| Belief Update Accuracy | {metrics['belief_update_accuracy_pct']}% | — |",
        f"| Epistemic Severe Errors | {metrics['epistemic_severe_errors']} | = 0 |",
        f"| Hard-fail cases | {metrics['cases_hard_fail_triggered']} | — |",
        "",
        "## Cases",
        "",
        "| ID | Level | Pass | Score | Hard-fail | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for s in scores:
        lines.append(
            f"| `{s.case_id}` | {s.level} | {'✅' if s.pass_ else '�'} | "
            f"{s.total_score:.1f} | {'yes' if s.hard_fail_triggered else 'no'} | "
            f"{s.notes_created} |"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_baseline(scores: list[CaseScore], metrics: dict, adapter_name: str,
                    output_path: Path) -> None:
    """Write the frozen baseline-v1.md report.

    This file is the source of truth for downstream prompt work. It
    MUST report exactly what the harness saw, including every
    hard-fail violation and every gap between expected and actual.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []

    adapter_label = adapter_name
    if adapter_name == "mock-stub":
        notes.append(
            "**Adapter in use: `mock-stub`.** This is the deterministic, 0-token "
            "fallback used to validate the harness and to produce a baseline "
            "report locally without invoking a real model. The `hermes` adapter "
            "is the production path and is wired but not invoked in this "
            "baseline. To run with a real model, set `MODEL_COMMAND` and "
            "re-run with `--adapter hermes` (or `EVAL_ADAPTER=hermes`)."
        )
    else:
        notes.append(
            "**Adapter in use: `hermes`.** Production model invocation via "
            "`MODEL_COMMAND`. The baseline here is the actual production "
            "behaviour under the prompts currently in `prompts/`."
        )

    raw = metrics["compression_ratio"]["raw_conversations"]
    cand = metrics["compression_ratio"]["candidate_learnings"]
    ret = metrics["compression_ratio"]["retained_learnings"]
    evg = metrics["compression_ratio"]["evergreen_concepts"]

    failures = sorted(
        (s for s in scores if not s.pass_),
        key=lambda s: s.total_score,
    )
    top5 = failures[:5]

    # Hard-fail coverage matrix: declared tags across all cases.
    coverage_map: dict[str, list[str]] = {}
    for s in scores:
        for cond in s.hard_fail_coverage:
            coverage_map.setdefault(cond, []).append(s.case_id)

    lines = [
        "# Knowledge Quality — Baseline V1",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Adapter: `{adapter_label}`",
        "- Source prompts: `prompts/learning-extractor.md` (unchanged), "
        "`prompts/knowledge-librarian.md` (unchanged), `prompts/monthly-synthesis.md` (unchanged)",
        "- Golden set: 24 cases under `evals/golden/001..024`",
        "",
        "## Adapter note",
        "",
        "\n".join(f"> {n}" for n in notes),
        "",
        "## Headline score",
        "",
        f"- **Overall: {metrics['overall_score']} / 100**",
        f"- Materiality Precision: **{metrics['materiality_precision_pct']}%**",
        f"- Materiality Recall: **{metrics['materiality_recall_pct']}%**",
        f"- False Positive Rate: **{metrics['false_positive_rate_pct']}%** (threshold ≤ 10%)",
        f"- False Negative Rate: **{metrics['false_negative_rate_pct']}%**",
        f"- Dedup Success Rate: **{metrics['dedup_success_rate_pct']}%**",
        f"- Duplicate Rate: **{metrics['duplicate_rate_pct']}%** (threshold ≤ 5%)",
        f"- Belief Update Accuracy: **{metrics['belief_update_accuracy_pct']}%**",
        f"- Epistemic Severe Errors: **{metrics['epistemic_severe_errors']}** (threshold = 0)",
        f"- Cases Passed: **{metrics['cases_passed']} / {metrics['cases_total']}**",
        f"- Cases Failed: **{metrics['cases_failed']}**",
        f"- Hard-fail Cases Triggered: **{metrics['cases_hard_fail_triggered']}**",
        f"- Average notes / material conversation: **{metrics['average_notes_per_material_conversation']}**",
        "",
        "## Compression ratio",
        "",
        f"- raw_conversations = **{raw}**",
        f"- candidate_learnings = **{cand}**",
        f"- retained_learnings = **{ret}**",
        f"- evergreen_concepts = **{evg}**",
        f"- healthy band example: 24 → 17 candidate → 11 retained → 5 evergreen",
        "",
        "## Hard-fail coverage matrix (declared)",
        "",
        "| Sentinel | Tagged in case(s) | Triggered in this run? |",
        "| --- | --- | --- |",
    ]
    hard_fail_labels = {
        "credential_leak": "1. private credential written to vault",
        "hypothesis_promoted": "2. hypothesis promoted to fact",
        "silent_overwrite": "3. prior belief silently overwritten",
        "trivial_evergreen": "4. trivial conversation created Evergreen",
        "duplicate_evergreen": "5. exact/near duplicate Evergreen created",
        "raw_full_conversation": "6. raw full conversation copied",
        "auto_decision": "7. automatic investment decision without user decision",
    }
    triggered_labels = {r for s in scores for r in s.hard_fail_reasons}
    for cond, label in hard_fail_labels.items():
        cases = coverage_map.get(cond, [])
        triggered = "yes" if label in triggered_labels else "no"
        cases_str = ", ".join(f"`{c}`" for c in cases) if cases else "(none — coverage gap)"
        lines.append(f"| {label} | {cases_str} | {triggered} |")

    lines.extend([
        "",
        "## Most Important Failures (top 5)",
        "",
    ])
    for s in top5:
        reason = "; ".join(s.hard_fail_reasons) or "score below pass threshold"
        lines.append(f"1. **`{s.case_id}`** — {reason} (score {s.total_score:.1f})")

    lines.extend([
        "",
        "## Failure patterns",
        "",
        "- trivial-conversation over-capture (precision miss)",
        "- evergreen created when only a fact update was warranted (epistemic)",
        "- belief-change direction mismatch (belief evolution)",
        "- duplicate evergreen / fragmented notes (dedup)",
        "- raw conversation copied into the long-term vault (hard-fail sentinel)",
        "",
        "## Recommended Prompt Changes (P0/P1)",
        "",
        "These are *recommendations only*. They are not applied in this branch.",
        "",
        "### P0 (blocking)",
        "",
        "1. Tighten extractor materiality gate so trivial conversations never enter `00_Inbox/`.",
        "2. Add explicit anti-promotion language: hypothesis / fact-update → never Evergreen.",
        "3. Force belief-history append on every update; refuse to silently overwrite.",
        "",
        "### P1 (next iteration)",
        "",
        "1. Title-similarity threshold (≥ 0.85) before creating a new evergreen.",
        "2. Reject any vault note larger than `expected_chars × 3` (raw-conversation sentinel).",
        "3. Decision note writes must include explicit user-action field; never auto-emit `SELL`.",
        "",
        "## Per-case results",
        "",
        "| Case | Level | Pass | Score | Hard-fail | Notes | Expected |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ])
    for s in scores:
        exp_actions = ", ".join(s.expected_actions) or "—"
        lines.append(
            f"| `{s.case_id}` | {s.level} | {'✅' if s.pass_ else '❌'} | "
            f"{s.total_score:.1f} | {'yes' if s.hard_fail_triggered else 'no'} | "
            f"{s.notes_created} | {exp_actions} |"
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--adapter",
        default=os.environ.get("EVAL_ADAPTER", "mock-stub"),
        help="Adapter to use: hermes | mock-stub (default: mock-stub)",
    )
    parser.add_argument(
        "--output",
        default=str(RESULTS_DIR / "latest.json"),
        help="Path for the latest.json report",
    )
    parser.add_argument(
        "--baseline",
        default=str(DEFAULT_BASELINE),
        help="Path for the baseline-v1.md frozen report",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Run only a single case (case dir name)",
    )
    args = parser.parse_args()

    case_dirs = _gather_case_dirs()
    if args.only:
        case_dirs = [d for d in case_dirs if d.name == args.only]
        if not case_dirs:
            print(f"No case named {args.only!r}", file=sys.stderr)
            return 2

    print(f"Running {len(case_dirs)} cases with adapter={args.adapter}")
    scores: list[CaseScore] = []
    per_case_metrics: list[dict] = []
    for case_dir in case_dirs:
        score, metrics = _run_case(case_dir, args.adapter)
        scores.append(score)
        per_case_metrics.append({"case_id": score.case_id, **metrics})
        marker = "✅" if score.pass_ else "❌"
        print(f"  {marker} {score.case_id:48s}  score={score.total_score:5.1f}  "
              f"hard_fail={score.hard_fail_triggered}")

    metrics = _aggregate(scores)
    metrics["adapter"] = args.adapter
    metrics["per_case"] = per_case_metrics

    output_json = Path(args.output)
    _write_latest_json(scores, metrics, output_json)
    _write_latest_md(scores, metrics, output_json.with_suffix(".md"))

    baseline_path = Path(args.baseline)
    _write_baseline(scores, metrics, args.adapter, baseline_path)

    print()
    print(f"Wrote {output_json}")
    print(f"Wrote {output_json.with_suffix('.md')}")
    print(f"Wrote {baseline_path}")
    print(f"Overall: {metrics['overall_score']} / 100  "
          f"FP={metrics['false_positive_rate_pct']}%  "
          f"Dup={metrics['duplicate_rate_pct']}%  "
          f"Hard-fail={metrics['cases_hard_fail_triggered']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
