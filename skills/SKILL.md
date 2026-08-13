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
hermes ghk status         # bridge health: webhook, board, cron, sync
hermes ghk list           # list kanban tasks
hermes ghk create <title> --body "..." --assignee coder  # create a task
hermes ghk sync           # force a sync sweep now
hermes ghk assign <id> <profile>  # reassign a task
hermes ghk webhook        # show webhook route + secret
hermes ghk webhook --url  # print the current public webhook URL (from zrok)
hermes ghk install-sweep  # show how to install the cron sweep job
```

## Slash commands (in chat)

```
/ghk status   # bridge health
/ghk list     # list tasks
/ghk sync     # force sync
/ghk help     # help
```

## Chat tools (LLM-callable)

- `ghk_status` — bridge health
- `ghk_list` — list tasks
- `ghk_create_task` — create a task
- `ghk_sync` — force sync sweep
- `ghk_assign` — reassign a task

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
5. **Install the cron sweep:** `hermes ghk install-sweep`
6. **Start the zrok tunnel:** `systemctl --user start zrok2-share.service`
7. **Register the GitHub webhook:** point the repo webhook to the zrok URL + secret

## Troubleshooting

- **Issues not creating kanban tasks:** check the zrok tunnel is running
  (`systemctl --user status zrok2-share.service`), the webhook is registered
  in GitHub (Settings → Webhooks), and the webhook secret matches.
- **Completed tasks not syncing back:** run `hermes ghk sync` to force a sweep;
  check that `GITHUB_TOKEN` is in `~/.hermes/.env`.
- **zrok URL changed after restart:** run `hermes ghk webhook --url` to get the
  new URL, then update the GitHub repo's webhook URL.
- **Task has no GitHub link:** the sync-back will backfill a mirror issue
  (labeled `kanban-mirror`) in the project repo.