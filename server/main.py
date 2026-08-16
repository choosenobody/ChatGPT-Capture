import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, HttpUrl, field_validator

# Raw conversations can contain sensitive material. New files should be private
# to the service account by default on POSIX systems.
os.umask(0o077)

BUFFER_DIR = Path(os.getenv("CAPTURE_BUFFER_DIR", "./data/chatgpt"))
CAPTURE_TOKEN = os.getenv("CAPTURE_TOKEN", "")
MAX_MESSAGE_CHARS = int(os.getenv("MAX_MESSAGE_CHARS", "120000"))
BUFFER_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ChatGPT Capture Receiver", version="0.1.0")

SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
    (
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (re.compile(r"\b(?:seed phrase|mnemonic)\s*[:=]\s*[^\n]{20,}", re.I), "[REDACTED_SEED_PHRASE]"),
]


class CaptureTurn(BaseModel):
    schema_version: Literal[1]
    source: Literal["chatgpt-web"]
    conversation_id: str = Field(min_length=1, max_length=256)
    conversation_title: str = Field(min_length=1, max_length=500)
    conversation_url: HttpUrl
    captured_at: datetime
    turn_id: str = Field(min_length=1, max_length=1024)
    user_message: str = Field(min_length=1)
    assistant_message: str = Field(min_length=1)

    @field_validator("conversation_url")
    @classmethod
    def validate_chatgpt_url(cls, value: HttpUrl) -> HttpUrl:
        host = (urlparse(str(value)).hostname or "").lower()
        if host not in {"chatgpt.com", "chat.openai.com"}:
            raise ValueError("conversation_url must point to ChatGPT")
        return value


def require_auth(authorization: str | None) -> None:
    if not CAPTURE_TOKEN:
        raise HTTPException(status_code=503, detail="CAPTURE_TOKEN is not configured")
    supplied = ""
    if authorization and authorization.startswith("Bearer "):
        supplied = authorization.removeprefix("Bearer ")
    if not hmac.compare_digest(supplied, CAPTURE_TOKEN):
        raise HTTPException(status_code=401, detail="unauthorized")


def redact(text: str) -> str:
    result = text
    for pattern, replacement in SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    if cleaned and len(cleaned) <= 100:
        return cleaned
    return hashlib.sha256(value.encode()).hexdigest()[:32]


@app.get("/healthz")
def healthz():
    return {"ok": True, "utc": datetime.now(timezone.utc).isoformat()}


@app.post("/v1/capture")
def capture(payload: CaptureTurn, authorization: str | None = Header(default=None)):
    require_auth(authorization)

    if len(payload.user_message) > MAX_MESSAGE_CHARS or len(payload.assistant_message) > MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=413, detail="message too large")

    conversation_dir = BUFFER_DIR / safe_id(payload.conversation_id)
    conversation_dir.mkdir(parents=True, exist_ok=True)
    file_path = conversation_dir / "turns.jsonl"
    dedupe_path = conversation_dir / ".seen"

    seen = set()
    if dedupe_path.exists():
        seen = set(dedupe_path.read_text(encoding="utf-8").splitlines())
    turn_hash = hashlib.sha256(payload.turn_id.encode()).hexdigest()
    if turn_hash in seen:
        return {"ok": True, "duplicate": True}

    record = payload.model_dump(mode="json")
    record["user_message"] = redact(record["user_message"])
    record["assistant_message"] = redact(record["assistant_message"])
    record["received_at"] = datetime.now(timezone.utc).isoformat()

    with file_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    with dedupe_path.open("a", encoding="utf-8") as f:
        f.write(turn_hash + "\n")

    return {"ok": True, "duplicate": False}
