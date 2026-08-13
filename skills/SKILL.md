---
name: github-kanban
description: "Use when syncing GitHub issues to Hermes kanban, assigning agents by label, and syncing completed work back. Covers the bridge pipeline, webhook setup, zrok tunnel, and troubleshooting."
version: 1.0.0
author: github-kanban-plugin
license: MIT
---

# GitHub-Kanban Bridge — Operating Guide

## What this does

Bridges GitHub issues into Hermes' native kanban board, assigns them to
profiles by label, dispatches work via the gateway's embedded dispatcher, and
syncs completed tasks back to GitHub (comment + close, with backfill for
unlinked tasks).

## The pipeline

```
GitHub issue (opened/reopened)
  → zrok tunnel → webhook → github-issue-to-kanban.py
  → kanban task (assigned by label)
  → gateway dispatcher (every 60s) → assigned profile runs
  → task done → kanban-sync-sweep.py (cron, every 5m)
  → kanban-sync-back.py → GitHub issue commented + closed
```

## Profile assignment by label

| Label | Profile |
|--------|---------|
| `bug`, `feature`, `refactor` | `coder` |
| `research` | `researcher` |
| `docs` | `writer` |
| `review` | `reviewer` |
| (none / other) | `orchestrator` |

## CLI commands

```bash
hermes github-kanban status         # bridge health: webhook, board, cron, sync
hermes github-kanban list           # list kanban tasks
hermes github-kanban create <title> --body "..." --assignee coder  # create a task
hermes github-kanban sync           # force a sync sweep now
hermes github-kanban assign <id> <profile>  # reassign a task
hermes github-kanban webhook        # show webhook route + secret
hermes github-kanban webhook --url  # print the current public webhook URL (from zrok)
hermes github-kanban install-sweep  # show how to install the cron sweep job
```

## Slash commands (in chat)

```bash
/github-kanban status   # bridge health
/github-kanban list     # list tasks
/github-kanban sync     # force sync
/github-kanban help     # help
```

## Chat tools (LLM-callable)

- `github_kanban_status` — bridge health
- `github_kanban_list` — list tasks
- `github_kanban_create_task` — create a task
- `github_kanban_sync` — force sync sweep
- `github_kanban_assign` — reassign a task

## Components

| Component | Location | Role |
|-----------|----------|------|
| Bridge script | `scripts/github-issue-to-kanban.py` | Issue → kanban task |
| Sync-back | `scripts/kanban-sync-back.py` | Done task → GitHub comment + close (backfill if no link) |
| Sweep | `scripts/kanban-sync-sweep.py` | Idempotent scan of done tasks → sync-back |
| Webhook route | `hermes webhook subscribe github-issues-to-kanban` | Receives GitHub `issues` events |
| Kanban board | `agentic-foundation` | Task queue |
| Dispatcher | gateway embedded (every 60s) | Spawns assigned profile |
| Cron | `kanban-github-sync` (every 5m) | Runs the sweep |
| Tunnel | `zrok2-share.service` (systemd) | Public URL for GitHub → localhost |

## Setup (first time)

1. **Install the plugin:** `hermes plugins enable github-kanban`
2. **Install scripts:** the `install.sh` copies scripts to `~/.hermes/scripts/`
3. **Create the board:** `hermes kanban boards create agentic-foundation`
4. **Subscribe the webhook:** see `install.sh` output for the exact command
5. **Install the cron sweep:** `hermes github-kanban install-sweep`
6. **Start the zrok tunnel:** `systemctl --user start zrok2-share.service`
7. **Register the GitHub webhook:** point the repo webhook to the zrok URL + secret

## Troubleshooting

- **Issues not creating kanban tasks:** check the zrok tunnel is running
  (`systemctl --user status zrok2-share.service`), the webhook is registered
  in GitHub (Settings → Webhooks), and the webhook secret matches.
- **Completed tasks not syncing back:** run `hermes github-kanban sync` to force a sweep;
  check that `GITHUB_TOKEN` is in `~/.hermes/.env`.
- **zrok URL changed after restart:** run `hermes github-kanban webhook --url` to get the
  new URL, then update the GitHub repo's webhook URL.
- **Task has no GitHub link:** the sync-back will backfill a mirror issue
  (labeled `kanban-mirror`) in the project repo.