---
name: github-kanban
description: "Use when syncing GitHub issues to Hermes kanban, assigning agents by label, and syncing completed work back. Covers the bridge pipeline, webhook setup, public URL configuration, and troubleshooting."
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
  → your public URL (reverse proxy/tunnel) → webhook → github-issue-to-kanban.py
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

## Projects (onboarded repos)

The bridge only creates kanban tasks for issues from **onboarded projects** — a
GitHub repo (`owner/repo`) you've explicitly wired in. Onboarding registers a
GitHub webhook on the repo (pointing at the bridge's configured public URL) and
adds the repo to the config's `projects` list. Removing deletes the webhook and
drops the repo. If the `projects` list is empty, the bridge accepts issues from
any repo (legacy behavior).

```bash
hermes github-kanban webhook --set-url https://kanban.example.com
hermes github-kanban project list
hermes github-kanban project onboard e8kor/agentic-foundation
hermes github-kanban project remove e8kor/agentic-foundation
```

The webhook script (`github-issue-to-kanban.py`) silently ignores issues from
repos not in the `projects` list.

## CLI commands

```bash
hermes github-kanban status         # bridge health: webhook, board, cron, sync
hermes github-kanban list           # list kanban tasks
hermes github-kanban create <title> --body "..." --assignee coder  # create a task
hermes github-kanban sync           # force a sync sweep now
hermes github-kanban assign <id> <profile>  # reassign a task
hermes github-kanban webhook        # show webhook route + secret
hermes github-kanban webhook --set-url https://kanban.example.com  # set the public base URL
hermes github-kanban webhook --url  # print the current public webhook URL
hermes github-kanban install-sweep  # show how to install the cron sweep job
hermes github-kanban project list   # list onboarded GitHub repos
hermes github-kanban project onboard <owner/repo>   # register webhook + add repo
hermes github-kanban project remove <owner/repo>     # delete webhook + drop repo
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
- `github_kanban_project` — onboard/remove/list GitHub projects

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
| Public URL | operator-provided reverse proxy/tunnel | Public URL for GitHub → localhost |

## Setup (first time)

1. **Install the plugin:** `hermes plugins enable github-kanban`
2. **Install scripts:** the `install.sh` copies scripts to `~/.hermes/scripts/`
3. **Create the board:** `hermes kanban boards create agentic-foundation`
4. **Subscribe the webhook:** see `install.sh` output for the exact command
5. **Install the cron sweep:** `hermes github-kanban install-sweep`
6. **Expose Hermes publicly:** use your own reverse proxy or tunnel, then run
   `hermes github-kanban webhook --set-url https://your.domain`
7. **Register the GitHub webhook:** point the repo webhook to `hermes github-kanban webhook --url` + secret

## Troubleshooting

- **Issues not creating kanban tasks:** check your reverse proxy/tunnel is
  running, `webhook_base_url` is set (`hermes github-kanban webhook --url`),
  the webhook is registered in GitHub (Settings → Webhooks), and the webhook
  secret matches.
- **Completed tasks not syncing back:** run `hermes github-kanban sync` to force a sweep;
  check that `GITHUB_TOKEN` is in `~/.hermes/.env`.
- **Public URL changed:** run `hermes github-kanban webhook --set-url https://new.domain`,
  then update the GitHub repo's webhook URL to the output of `hermes github-kanban webhook --url`.
- **Task has no GitHub link:** the sync-back will backfill a mirror issue
  (labeled `kanban-mirror`) in the project repo.