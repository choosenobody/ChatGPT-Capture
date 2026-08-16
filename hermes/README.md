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

For the monthly review, change delivery later if you want it pushed to Telegram or another Hermes channel instead of local output:

```bash
hermes cron edit "Monthly Knowledge Synthesis" --deliver telegram
```

If you change the prompts in this repository, update the existing cron jobs or rerun setup only after removing the old jobs; job names are not inherently unique.
