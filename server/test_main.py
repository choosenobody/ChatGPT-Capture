import importlib
import json

from fastapi.testclient import TestClient


def load_app(monkeypatch, tmp_path):
    monkeypatch.setenv("CAPTURE_TOKEN", "test-token")
    monkeypatch.setenv("CAPTURE_BUFFER_DIR", str(tmp_path))
    import main
    importlib.reload(main)
    return main


def valid_payload():
    return {
        "schema_version": 1,
        "source": "chatgpt-web",
        "conversation_id": "abc-123",
        "conversation_title": "Test conversation",
        "conversation_url": "https://chatgpt.com/c/abc-123",
        "captured_at": "2026-08-16T10:00:00Z",
        "turn_id": "abc-123:1->abc-123:2",
        "user_message": "hello",
        "assistant_message": "world",
    }


def test_capture_requires_auth(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    client = TestClient(main.app)
    response = client.post("/v1/capture", json=valid_payload())
    assert response.status_code == 401


def test_capture_and_deduplicate(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    client = TestClient(main.app)
    headers = {"Authorization": "Bearer test-token"}

    first = client.post("/v1/capture", json=valid_payload(), headers=headers)
    second = client.post("/v1/capture", json=valid_payload(), headers=headers)

    assert first.status_code == 200
    assert first.json() == {"ok": True, "duplicate": False}
    assert second.json() == {"ok": True, "duplicate": True}

    lines = (tmp_path / "abc-123" / "turns.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["assistant_message"] == "world"


def test_server_redacts_secrets(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    client = TestClient(main.app)
    payload = valid_payload()
    payload["user_message"] = "token sk-abcdefghijklmnopqrstuvwxyz1234567890"

    response = client.post(
        "/v1/capture",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    stored = (tmp_path / "abc-123" / "turns.jsonl").read_text(encoding="utf-8")
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in stored
    assert "[REDACTED_OPENAI_KEY]" in stored


def test_rejects_non_chatgpt_url(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    client = TestClient(main.app)
    payload = valid_payload()
    payload["conversation_url"] = "https://example.com/c/abc-123"

    response = client.post(
        "/v1/capture",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
