"""Deterministic, 0-token mock adapter for CI smoke + V1 baseline.

This adapter is explicitly **not** a substitute for the real pipeline. It
exists so that:

* CI can run `python3 evals/run_eval.py` with zero model calls.
* The V1 baseline report can be generated locally without an LLM.
* Engineers can iterate on `expected.yaml` / `rationale.md` /
  scoring logic without burning tokens.

Behaviour: it parses the conversation text via simple deterministic
heuristics, writes a structured inbox note into the vault, and (if
applicable) classifies / moves it like the librarian would. Every
decision is rule-based; the goal is to surface *what the harness
expects*, not to mimic production output.

Hard rules:

* Never calls any LLM.
* Never modifies `prompts/`, `hermes/`, `server/`, or `extension/`.
* Always returns a VaultDiff even when it deliberately "under-shoots"
  on hard cases, so the harness records the gap honestly.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .base import Adapter, AdapterError, VaultDiff, make_temp_vault_from_fixture

VAULT_DIRS = ("00_Inbox", "10_Learnings", "20_Evergreen", "30_Entities", "40_Decisions", "90_Reviews")


def _ensure_vault_dirs(vault_dir: Path) -> None:
    for name in VAULT_DIRS:
        (vault_dir / name).mkdir(parents=True, exist_ok=True)


def _list_md(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def _read_conversation(conv_path: Path) -> list[dict]:
    """Read a JSONL capture buffer (schema_version=1) into a list."""
    rows: list[dict] = []
    for line in conv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# Heuristic signal patterns. Tuned for the 24 golden cases shipped in V1;
# they are intentionally narrow — this is a deterministic stub.
TRIVIAL_PATTERNS = [
    r"\bweather\b",
    r"how do you say .+ in (chinese|spanish|french|japanese|german)",
    r"translate .+ to (chinese|spanish|french|japanese|german)",
    r"shipping status|tracking number|parcel",
]
HIGH_VALUE_PATTERNS = [
    r"ROIC|RONIC|return on invested capital",
    r"value creation|value destruction",
    r"channel (?:economics|migration)|channel inventory",
    r"AI economics|AI inference",
    r"pricing power|moat",
    r"margins? (?:expand|compress)",
    r"belief (?:change|update|reverse|strengthen|weaken)",
]
EVERGREEN_CONCEPT_PATTERNS = [
    r"high RONIC.*(?:reinvest|growth)",
    r"revenue growth.*value creation",
    r"channel migration.*end demand",
    r"AI inference.*marginal cost",
    r"incremental returns?.*capital intensiv",
]
HYPOTHESIS_PATTERNS = [
    r"may (?:raise|hike)|expected to (?:raise|hike)|will (?:raise|hike) prices? next year",
]
FACT_UPDATE_PATTERNS = [
    r"VAT (?:from )?\d+% ?(?:to|->) ?\d+%",
    r"Q\d revenue \$[\d\.]+ ?bn",
]
CONTRADICTION_PATTERNS = [
    r"marginal cost.*(?:near[- ]zero|zero)",
    r"marginal cost.*meaningful|meaningful.*marginal cost",
]


def _classify_text(text: str) -> dict:
    """Return a heuristic classification of the conversation text."""
    text_l = text.lower()
    signals = {
        "trivial": any(re.search(p, text_l) for p in TRIVIAL_PATTERNS),
        "high_value": any(re.search(p, text_l) for p in HIGH_VALUE_PATTERNS),
        "evergreen_concept": any(re.search(p, text_l) for p in EVERGREEN_CONCEPT_PATTERNS),
        "hypothesis": any(re.search(p, text_l) for p in HYPOTHESIS_PATTERNS),
        "fact_update": any(re.search(p, text_l) for p in FACT_UPDATE_PATTERNS),
        "contradiction": any(re.search(p, text_l) for p in CONTRADICTION_PATTERNS),
    }
    return signals


class MockStubAdapter(Adapter):
    """Deterministic, no-token adapter."""

    name = "mock-stub"

    # ---- Level 1: extractor ----
    def extractor_run(
        self, conversation: Path, vault_dir: Path, *, conversation_id: str,
    ) -> VaultDiff:
        _ensure_vault_dirs(vault_dir)
        rows = _read_conversation(conversation)
        text = "\n".join(
            (r.get("user_message", "") + "\n" + r.get("assistant_message", ""))
            for r in rows
        )
        cls = _classify_text(text)

        diff = VaultDiff()
        diff.inbox_count_before = len(_list_md(vault_dir / "00_Inbox"))
        diff.raw_text_chars_written = 0

        # Heuristic gating:
        # * trivial-only conversations => no note (matches `no_note` expectation).
        # * high-value signal => create exactly one inbox note.
        if cls["trivial"] and not cls["high_value"]:
            diff.inbox_count_after = len(_list_md(vault_dir / "00_Inbox"))
            return diff

        # Build a single inbox note (the harness checks *count*; the stub
        # intentionally collapses duplicates into one file to make
        # duplicate-creation easy to spot in `latest.json`).
        title = rows[0].get("conversation_title", conversation_id) if rows else conversation_id
        note = self._render_inbox_note(
            conversation_id=conversation_id,
            title=title,
            cls=cls,
        )
        target = vault_dir / "00_Inbox" / f"{conversation_id} - stub.md"
        target.write_text(note, encoding="utf-8")
        diff.created_files.append(str(target.relative_to(vault_dir)))
        diff.new_inbox_notes = 1
        diff.raw_text_chars_written = len(note)

        diff.inbox_count_after = len(_list_md(vault_dir / "00_Inbox"))
        diff.extra = {"classification": cls}
        return diff

    # ---- Level 2: librarian ----
    def librarian_run(self, vault_dir: Path) -> VaultDiff:
        _ensure_vault_dirs(vault_dir)
        diff = VaultDiff()
        inbox = vault_dir / "00_Inbox"
        diff.inbox_count_before = len(_list_md(inbox))
        diff.inbox_count_after = 0

        for note in _list_md(inbox):
            text = note.read_text(encoding="utf-8")
            cls = _classify_text(text)
            moved = self._lifecycle_move(note, cls, diff, vault_dir)
            diff.raw_text_chars_written += moved
        diff.inbox_count_after = len(_list_md(inbox))
        return diff

    # ---- helpers ----
    @staticmethod
    def _render_inbox_note(conversation_id: str, title: str, cls: dict) -> str:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        belief = "new" if cls["high_value"] else "unchanged"
        epistemic = "HYPOTHESIS" if cls["hypothesis"] else "INFERENCE"
        evergreen = "true" if cls["evergreen_concept"] else "false"
        return (
            "---\n"
            "type: learning\n"
            "domains: []\n"
            "entities: []\n"
            "topics: []\n"
            "status: active\n"
            "confidence: 0\n"
            f"belief_change: {belief}\n"
            "source: chatgpt\n"
            f"created: {today}\n"
            f"epistemic_kind: {epistemic}\n"
            f"evergreen_candidate: {evergreen}\n"
            f"conversation_id: {conversation_id}\n"
            "---\n\n"
            f"# {title}\n\n"
            "Stub note generated by mock-stub adapter.\n"
        )

    @staticmethod
    def _lifecycle_move(note: Path, cls: dict, diff: VaultDiff, vault_dir: Path) -> int:
        """Move or transform an inbox note the way the librarian would.

        Deliberately conservative: when in doubt we do nothing — the
        gap then shows up honestly in `baseline-v1.md`.
        """
        if cls["trivial"]:
            archive = vault_dir / "90_Reviews" / "Archive" / note.name
            archive.parent.mkdir(parents=True, exist_ok=True)
            note.replace(archive)
            diff.modified_files.append(str(archive.relative_to(vault_dir)))
            diff.inbox_to_archive += 1
            return 0

        # Decide where the note lands:
        if cls["evergreen_concept"]:
            evergreen_target = vault_dir / "20_Evergreen" / note.name
            evergreen_target.write_text(note.read_text(encoding="utf-8"), encoding="utf-8")
            diff.created_files.append(str(evergreen_target.relative_to(vault_dir)))
            diff.inbox_to_evergreen += 1
        elif cls["high_value"]:
            entity_target = vault_dir / "30_Entities" / note.name
            entity_target.write_text(note.read_text(encoding="utf-8"), encoding="utf-8")
            diff.created_files.append(str(entity_target.relative_to(vault_dir)))
            diff.inbox_to_entities += 1

        # Always move the original to 10_Learnings.
        learning_target = vault_dir / "10_Learnings" / note.name
        learning_target.write_text(note.read_text(encoding="utf-8"), encoding="utf-8")
        diff.modified_files.append(str(learning_target.relative_to(vault_dir)))
        diff.inbox_to_learnings += 1

        # Remove the inbox original.
        try:
            note.unlink()
        except FileNotFoundError:
            pass
        return len(note.read_text(encoding="utf-8")) if note.exists() else 0


# Re-export make_temp_vault_from_fixture so callers do not need to
# import `adapters.base` separately.
__all__ = ["MockStubAdapter", "make_temp_vault_from_fixture"]
