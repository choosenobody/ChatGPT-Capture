#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <capture-buffer-dir> <obsidian-vault-dir>" >&2
  exit 2
fi

BUFFER_DIR=$(realpath "$1")
VAULT_DIR=$(realpath "$2")
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
HERMES_DIR="$HOME/.hermes"
HERMES_SCRIPTS="$HERMES_DIR/scripts"
CONFIG_PATH="$HERMES_DIR/chatgpt-capture.json"

command -v hermes >/dev/null || { echo "hermes CLI not found" >&2; exit 1; }
[[ -d "$BUFFER_DIR" ]] || { echo "Buffer dir not found: $BUFFER_DIR" >&2; exit 1; }
[[ -d "$VAULT_DIR" ]] || { echo "Vault dir not found: $VAULT_DIR" >&2; exit 1; }

mkdir -p "$HERMES_SCRIPTS"
install -m 700 "$SCRIPT_DIR/collect-idle-conversations.py" "$HERMES_SCRIPTS/chatgpt-capture-collect.py"
install -m 700 "$SCRIPT_DIR/prune-extracted.py" "$HERMES_SCRIPTS/chatgpt-capture-prune.py"

python - "$CONFIG_PATH" "$BUFFER_DIR" "$VAULT_DIR" <<'PY'
import json, sys
from pathlib import Path
path, buffer_dir, vault_dir = sys.argv[1:]
config = {
    "buffer_dir": buffer_dir,
    "vault_dir": vault_dir,
    "idle_minutes": 30,
    "retention_days": 7,
    "max_conversations_per_run": 3,
    "max_chars_per_conversation": 160000,
}
Path(path).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY
chmod 600 "$CONFIG_PATH"

mkdir -p \
  "$VAULT_DIR/00_Inbox" \
  "$VAULT_DIR/10_Learnings" \
  "$VAULT_DIR/20_Evergreen" \
  "$VAULT_DIR/30_Entities" \
  "$VAULT_DIR/40_Decisions" \
  "$VAULT_DIR/90_Reviews/Archive" \
  "$VAULT_DIR/99_System"

EXTRACTOR_PROMPT=$(cat "$REPO_ROOT/prompts/learning-extractor.md")
LIBRARIAN_PROMPT=$(cat "$REPO_ROOT/prompts/knowledge-librarian.md")
MONTHLY_PROMPT=$(cat "$REPO_ROOT/prompts/monthly-synthesis.md")

hermes cron create "every 1h" "$EXTRACTOR_PROMPT" \
  --script chatgpt-capture-collect.py \
  --skill obsidian-vault \
  --workdir "$VAULT_DIR" \
  --deliver local \
  --name "ChatGPT Learning Extractor"

hermes cron create "30 2 * * *" "$LIBRARIAN_PROMPT" \
  --skill obsidian-vault \
  --workdir "$VAULT_DIR" \
  --deliver local \
  --name "Knowledge Librarian"

hermes cron create "0 8 1 * *" "$MONTHLY_PROMPT" \
  --skill obsidian-vault \
  --workdir "$VAULT_DIR" \
  --deliver origin \
  --name "Monthly Knowledge Synthesis"

hermes cron create "15 3 * * *" \
  --no-agent \
  --script chatgpt-capture-prune.py \
  --deliver local \
  --name "ChatGPT Capture Raw Buffer Prune"

echo "Created ChatGPT Capture automation jobs:"
hermes cron list
