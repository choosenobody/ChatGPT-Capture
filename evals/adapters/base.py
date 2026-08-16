"""Adapter interface for the Knowledge Quality Golden Set V1.

The harness is intentionally split into:

* `extractor_run(conversation, vault_dir)` — Level 1 eval.
  Input is a conversation block. Vault may be empty.
  Output is the vault state after running the extractor.

* `librarian_run(vault_dir)` — Level 2 eval.
  Input is a vault with at least one unprocessed inbox note.
  Output is the vault state after the librarian lifecycle runs.

Adapters MUST be deterministic-enough for CI smoke runs and MUST NOT
modify `prompts/`, `hermes/`, `server/`, or `extension/`.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class AdapterError(RuntimeError):
    """Raised when an adapter cannot produce a result."""


@dataclass
class VaultDiff:
    """Minimal snapshot of a vault before and after a run."""

    created_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    inbox_count_before: int = 0
    inbox_count_after: int = 0
    inbox_to_learnings: int = 0  # notes moved 00_Inbox -> 10_Learnings
    inbox_to_archive: int = 0     # notes moved 00_Inbox -> 90_Reviews/Archive
    inbox_to_evergreen: int = 0   # notes created in 20_Evergreen
    inbox_to_entities: int = 0    # notes created/updated in 30_Entities
    inbox_to_decisions: int = 0   # notes created/updated in 40_Decisions
    new_inbox_notes: int = 0
    raw_text_chars_written: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


class Adapter:
    """Base interface. Subclasses implement the two _run_ methods."""

    name: str = "base"

    # ---- Level 1: extractor ----
    def extractor_run(
        self, conversation: Path, vault_dir: Path, *, conversation_id: str,
    ) -> VaultDiff:
        raise AdapterError("extractor_run not implemented")

    # ---- Level 2: librarian ----
    def librarian_run(self, vault_dir: Path) -> VaultDiff:
        raise AdapterError("librarian_run not implemented")


def make_temp_vault_from_fixture(fixture: Path | None) -> Path:
    """Copy an optional fixture `vault_before/` into a fresh tempdir.

    If `fixture` is None or does not exist, return an empty tempdir.
    """
    target = Path(tempfile.mkdtemp(prefix="golden-vault-"))
    if fixture is not None and fixture.exists() and any(fixture.iterdir()):
        for child in fixture.iterdir():
            dest = target / child.name
            if child.is_dir():
                shutil.copytree(child, dest)
            else:
                shutil.copy2(child, dest)
    return target
