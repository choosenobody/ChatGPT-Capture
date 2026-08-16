import json
import os
import sys
import time
from pathlib import Path

CONFIG_PATH = Path(os.path.expanduser("~/.hermes/chatgpt-capture.json"))


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Missing config: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def main() -> int:
    config = load_config()
    buffer_dir = Path(config["buffer_dir"]).expanduser().resolve()
    idle_seconds = int(config.get("idle_minutes", 30)) * 60
    max_conversations = int(config.get("max_conversations_per_run", 3))
    max_chars = int(config.get("max_chars_per_conversation", 160000))
    now = time.time()

    candidates = []
    if buffer_dir.exists():
        for turns_path in buffer_dir.glob("*/turns.jsonl"):
            marker = turns_path.parent / ".extracted"
            turns_mtime = turns_path.stat().st_mtime
            if now - turns_mtime < idle_seconds:
                continue
            if marker.exists() and marker.stat().st_mtime >= turns_mtime:
                continue
            candidates.append((turns_mtime, turns_path, marker))

    if not candidates:
        print("NO_IDLE_CONVERSATIONS")
        return 0

    candidates.sort(key=lambda item: item[0])
    for _, turns_path, marker in candidates[:max_conversations]:
        raw = turns_path.read_text(encoding="utf-8")
        if len(raw) > max_chars:
            raw = raw[-max_chars:]
            truncated = True
        else:
            truncated = False

        print("=== CHATGPT_CAPTURE_START ===")
        print(f"turns_path: {turns_path}")
        print(f"processed_marker: {marker}")
        print(f"truncated_from_front: {str(truncated).lower()}")
        print("jsonl:")
        print(raw.rstrip())
        print("=== CHATGPT_CAPTURE_END ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
