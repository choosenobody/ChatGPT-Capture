# ChatGPT Capture

A private-by-design pipeline that captures completed ChatGPT user/assistant turns, buffers them on your own Hermes/VPS endpoint, and later converts only material learnings into an Obsidian knowledge base.

## Architecture

```text
ChatGPT Web
  -> Chrome extension (capture only)
  -> HTTPS + bearer token
  -> Hermes/VPS receiver
  -> JSONL conversation buffer
  -> Learning Extractor
  -> Obsidian 00_Inbox
  -> Knowledge Librarian
  -> Obsidian Headless Sync
```

The core design rule is **capture broadly, preserve narrowly**. Raw conversation is not the knowledge base.

## V1 scope

- Captures completed user -> assistant turn pairs from ChatGPT web.
- Does not transmit while the assistant is still streaming.
- Deduplicates captured turns in the browser session and again server-side.
- Redacts obvious API keys/private-key material before storage.
- Sends data only to the endpoint configured in the extension.
- Requests network permission only for the configured Hermes origin.
- Stores the endpoint and bearer token in local Chrome extension storage, not Chrome Sync.
- Buffers conversations as JSONL for Hermes to process later.
- Includes prompts for a Learning Extractor, Knowledge Librarian, and Monthly Synthesis.

## 1. Run the receiver on the VPS

```bash
cd server
cp .env.example .env
# Edit .env and set:
#   CAPTURE_TOKEN=<a long random secret>
#   CAPTURE_BUFFER_HOST_DIR=/root/ChatGPT-Capture-Buffer   # or any host path
docker compose --env-file .env up -d --build
curl http://127.0.0.1:8787/healthz
```

`CAPTURE_BUFFER_HOST_DIR` is the directory on the VPS that the container bind-mounts into `/data`. Hermes cron reads the same path via `~/.hermes/chatgpt-capture.json`, so keep them in sync.

For production, put Caddy/Nginx/Cloudflare Tunnel in front of `127.0.0.1:8787` and expose only HTTPS.

Do **not** expose the port directly to the internet.

## 2. Install the Chrome extension locally

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Click **Load unpacked**.
4. Select the `extension/` directory.
5. Open the extension details -> Extension options.
6. Configure your HTTPS Hermes endpoint (e.g. `https://<your-tunnel>.trycloudflare.com`) and the same bearer token. Chrome will ask for access only to that endpoint origin.
7. Enable capture and save. The token remains in local extension storage and is not synced through Chrome Sync.

Then open ChatGPT normally. Completed turns will be POSTed to:

```text
POST /v1/capture
Authorization: Bearer ***
```

## 3. Automate extraction and knowledge maintenance with Hermes

Hermes Agent can schedule both LLM-driven cron jobs and zero-token script-only jobs, and can attach the `obsidian-vault` skill to scheduled work. This repo includes a setup script that creates the full unattended pipeline.

Prerequisites:

- the capture buffer is readable on the Hermes host;
- the Obsidian vault is present on that host (for example via Obsidian Headless Sync);
- Hermes gateway/cron is installed and running;
- the Hermes `obsidian-vault` skill is available.

Run:

```bash
./hermes/setup-cron.sh /absolute/path/to/chatgpt-buffer /absolute/path/to/obsidian-vault
```

It creates four jobs:

- hourly material-learning extraction after a conversation has been idle for 30 minutes;
- daily Knowledge Librarian maintenance at 02:30;
- monthly synthesis at 08:00 on the first day of the month;
- daily raw-buffer pruning at 03:15 in no-agent mode.

See `hermes/README.md` for lifecycle and testing details.

## Payload schema

```json
{
  "schema_version": 1,
  "source": "chatgpt-web",
  "conversation_id": "...",
  "conversation_title": "...",
  "conversation_url": "https://chatgpt.com/c/...",
  "captured_at": "2026-08-16T10:00:00.000Z",
  "turn_id": "...",
  "user_message": "...",
  "assistant_message": "..."
}
```

## Buffer layout

```text
server/data/chatgpt/<conversation-id>/turns.jsonl
server/data/chatgpt/<conversation-id>/.seen
```

The recommended production policy is to delete raw buffers after successful knowledge extraction, with a short retention period such as 7 days.

## Hermes workflow

### Learning Extractor

The included Hermes pre-script selects conversations that have been idle for at least 30 minutes and are newer than their `.extracted` marker. The extractor runs hourly and writes only material learnings to Obsidian `00_Inbox/`.

### Knowledge Librarian

Runs once daily, silently by default, using `prompts/knowledge-librarian.md`. It deduplicates, links, preserves belief evolution, detects contradictions, and promotes only durable concepts to Evergreen notes. A separate monthly job writes a decision-oriented synthesis to `90_Reviews/`.

## Recommended Obsidian folders

```text
00_Inbox/
10_Learnings/
20_Evergreen/
30_Entities/
40_Decisions/
90_Reviews/
99_System/
```

On the VPS, Hermes can write Markdown directly into the synced vault. Obsidian-specific CLI operations are optional; they are not required for V1.

## Security notes

- Use HTTPS only outside localhost. The extension refuses plain HTTP except for localhost/127.0.0.1.
- Use a long random bearer token.
- Keep the receiver bound to localhost behind a reverse proxy/tunnel.
- The redactor is best-effort, not a formal DLP system.
- Never intentionally paste seed phrases, private keys, passwords, or OAuth tokens into ChatGPT.
- Treat raw conversation buffers as sensitive and short-lived.

## Manual Chrome-extension test plan

After installing the unpacked extension and configuring endpoint + token:

1. **Normal capture**: open a new ChatGPT conversation, send a short user prompt, wait for the assistant reply to finish, then check `/root/ChatGPT-Capture-Buffer/chatgpt/<id>/turns.jsonl` on the VPS — one record should appear.
2. **Streaming**: send a long prompt (e.g. "Explain in 800 words..."), confirm nothing is sent while the Stop button is visible, and exactly one record appears when the response ends.
3. **Multiple turns in one conversation**: send three more rounds, confirm four records with monotonic turn_ids.
4. **Refresh**: hard-refresh the ChatGPT tab, confirm no duplicate captures (browser-side `seen` set + server-side `.seen` both gate this).
5. **Switch conversation**: click a different conversation in the sidebar, confirm a new `<conversation-id>/` directory appears.
6. **New conversation**: click "New chat", send one prompt, confirm capture works.
7. **Redaction**: paste a fake API key (`sk-abc...1234567890`), confirm the saved JSONL on the VPS contains `[REDACTED_OPENAI_KEY]` instead.

If any test fails, check `/var/log/cloudflared/tunnel.log` and `docker logs server-capture-1` for the receiver side.

## Known V1 limitations

ChatGPT's web DOM can change. The extension uses multiple selectors, but capture may require selector updates after a UI redesign. This is why extraction logic is kept isolated in `extension/content.js`.

The extension currently captures visible text, not uploaded file bytes or hidden model metadata.

## Development

```bash
cd server
pip install -r requirements-dev.txt
pytest -q
```

CI also validates the extension manifest, syntax-checks the JavaScript files, and checks the Hermes helper scripts.
