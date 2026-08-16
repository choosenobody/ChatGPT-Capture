import json
import os
import shutil
import sys
import time
from pathlib import Path

CONFIG_PATH = Path(os.path.expanduser("~/.hermes/chatgpt-capture.json"))


def main() -> int:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Missing config: {CONFIG_PATH}")

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    buffer_dir = Path(config["buffer_dir"]).expanduser().resolve()
    retention_days = int(config.get("retention_days", 7))
    cutoff = time.time() - retention_days * 86400

    if not buffer_dir.exists():
        return 0

    for conversation_dir in buffer_dir.iterdir():
        if not conversation_dir.is_dir():
            continue
        turns = conversation_dir / "turns.jsonl"
        marker = conversation_dir / ".extracted"
        if not turns.exists() or not marker.exists():
            continue
        if marker.stat().st_mtime >= turns.stat().st_mtime and marker.stat().st_mtime < cutoff:
            shutil.rmtree(conversation_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
