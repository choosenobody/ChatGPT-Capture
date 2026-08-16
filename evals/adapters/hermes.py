"""Hermes adapter — production-shaped adapter.

This adapter calls the real LLM via the active Hermes provider
(default: MiniMax API). It is intentionally **lightweight**: it shells
out to whatever command the operator configured in the `MODEL_COMMAND`
environment variable, so it does not hard-code a particular SDK.

For V1 baseline reporting this adapter is *not* the default — the
`mock-stub` adapter is, so the harness runs with zero tokens. To run
the real pipeline:

    EVAL_ADAPTER=hermes python3 evals/run_eval.py

Or invoke Hermes with the relevant cron job directly; the golden set
is also a smoke fixture that the cron can ingest.

Important: this adapter is read-only with respect to `prompts/`,
`server/`, `extension/`, and `hermes/`. It only writes inside the
temp vault it is handed by the harness.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .base import Adapter, AdapterError, VaultDiff


def _load_prompt(name: str) -> str:
    """Read a prompt markdown file. Raises AdapterError on missing file.

    The prompts live in the production repo and are intentionally
    treated as immutable here.
    """
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "prompts" / f"{name}.md"
    if not path.exists():
        raise AdapterError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


class HermesAdapter(Adapter):
    """Adapter that drives the real Hermes cron pipeline."""

    name = "hermes"

    def __init__(self) -> None:
        self.extractor_prompt = _load_prompt("learning-extractor")
        self.librarian_prompt = _load_prompt("knowledge-librarian")

    def _invoke_model(self, prompt: str, user_input: str) -> str:
        """Shell out to `MODEL_COMMAND` if configured, else raise.

        `MODEL_COMMAND` must be a callable string. The harness injects
        `{prompt}` and `{input}` placeholders.
        """
        cmd = os.environ.get("MODEL_COMMAND")
        if not cmd:
            raise AdapterError(
                "Hermes adapter requires MODEL_COMMAND to be set. "
                "For 0-token CI smoke runs, use --adapter mock-stub."
            )
        formatted = cmd.format(prompt=prompt, input=user_input)
        try:
            completed = subprocess.run(
                formatted.split(),
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise AdapterError(f"MODEL_COMMAND failed: {exc}") from exc
        if completed.returncode != 0:
            raise AdapterError(
                f"MODEL_COMMAND exited {completed.returncode}: {completed.stderr}"
            )
        return completed.stdout

    def extractor_run(
        self, conversation: Path, vault_dir: Path, *, conversation_id: str,
    ) -> VaultDiff:
        user_input = conversation.read_text(encoding="utf-8")
        try:
            self._invoke_model(self.extractor_prompt, user_input)
        except AdapterError as exc:
            # Surface as a no-op diff so the harness can record the gap
            # honestly instead of swallowing it.
            diff = VaultDiff()
            diff.extra = {"adapter_error": str(exc)}
            return diff

        # When the real adapter is wired, the extractor will have
        # written its inbox notes into the vault already. We trust the
        # production code path and just snapshot the result.
        diff = VaultDiff()
        inbox = vault_dir / "00_Inbox"
        diff.inbox_count_before = 0
        diff.inbox_count_after = len(list(inbox.glob("*.md"))) if inbox.exists() else 0
        diff.new_inbox_notes = max(0, diff.inbox_count_after - diff.inbox_count_before)
        return diff

    def librarian_run(self, vault_dir: Path) -> VaultDiff:
        try:
            self._invoke_model(self.librarian_prompt, str(vault_dir))
        except AdapterError as exc:
            diff = VaultDiff()
            diff.extra = {"adapter_error": str(exc)}
            return diff

        diff = VaultDiff()
        inbox = vault_dir / "00_Inbox"
        learnings = vault_dir / "10_Learnings"
        diff.inbox_count_before = len(list(inbox.glob("*.md"))) if inbox.exists() else 0
        diff.inbox_count_after = 0
        diff.inbox_to_learnings = (
            len(list(learnings.glob("*.md"))) if learnings.exists() else 0
        )
        return diff


__all__ = ["HermesAdapter"]
