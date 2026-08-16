# Hermes automation

This directory turns the capture receiver into an unattended knowledge pipeline using Hermes Agent cron.

## What gets scheduled

- **ChatGPT Learning Extractor** — hourly. A pre-script emits conversations idle for at least 30 minutes; Hermes decides whether each contains material learning and writes only durable notes to `00_Inbox/`.
- **Knowledge Librarian** — daily at 02:30. Deduplicates, links, maintains belief history, and promotes only durable concepts.
- **Monthly Knowledge Synthesis** — 08:00 on the first day of each month, reviewing the month that just ended.
- **Raw Buffer Prune** — daily at 03:15 in Hermes no-agent mode. It deletes only successfully processed raw conversation directories after 7 days.

Cron expressions use the timezone of the Hermes scheduler host. Configure the VPS/system timezone to the timezone you want before creating the jobs.

## Install

The capture receiver's host data directory must be readable by the Hermes user, and the Obsidian vault must already exist locally on the VPS (for example via Obsidian Headless Sync).

```bash
./hermes/setup-cron.sh /absolute/path/to/chatgpt-buffer /absolute/path/to/obsidian-vault
```

The script copies the cron helper scripts to `~/.hermes/scripts/`, writes `~/.hermes/chatgpt-capture.json`, creates the vault folders, and creates the four cron jobs.

Hermes cron jobs run in fresh sessions, so the prompts are deliberately self-contained. The extractor marks each successfully reviewed capture state with `.extracted`; if new turns arrive later, the changed `turns.jsonl` is eligible for another extraction pass.

## Recommended first-run checks

```bash
hermes cron list
hermes cron run "ChatGPT Learning Extractor"
hermes cron run "Knowledge Librarian"
```

For the monthly review, it is delivered to the origin chat (this conversation) by default so the user is notified; change later if you want local-only:

```bash
hermes cron edit "Monthly Knowledge Synthesis" --deliver local
```

## Skill attachment

`setup-cron.sh` attaches the `obsidian-vault` skill (the canonical Hermes skill that knows the layout of `00_Inbox/` / `10_Learnings/` / `20_Evergreen/` etc.). If your local skill is named differently, edit the three `--skill` flags in `setup-cron.sh` before running it.

## Buffers and `setup-cron.sh`

`setup-cron.sh` writes `buffer_dir` into `~/.hermes/chatgpt-capture.json` from its first CLI argument. The capture container must write to that same host directory. The default `server/docker-compose.yml` reads `CAPTURE_BUFFER_HOST_DIR` from `server/.env` for the bind mount and falls back to `./data` for local development. Set `CAPTURE_BUFFER_HOST_DIR` in `server/.env` to the same path you pass to `setup-cron.sh`.

If you change the prompts in this repository, update the existing cron jobs or rerun setup only after removing the old jobs; job names are not inherently unique.
