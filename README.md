# hermes-github-kanban-plugin

GitHub Issues <-> Hermes Kanban bridge. Syncs GitHub issues to a kanban board,
assigns profiles by label, dispatches work via the gateway's embedded
dispatcher, and syncs completed tasks back to GitHub (comment + close, with
backfill for unlinked tasks).

## Install

```bash
./install.sh
hermes plugins enable github-kanban
# Restart Hermes for the plugin to take effect
```

## What it does

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

## CLI

```bash
hermes github-kanban status         # bridge health
hermes github-kanban list           # list tasks
hermes github-kanban create <title> --body "..." --assignee coder
hermes github-kanban sync           # force sync sweep
hermes github-kanban assign <id> <profile>
hermes github-kanban webhook --set-url https://kanban.example.com  # configure public base URL
hermes github-kanban webhook --url  # current public webhook URL
hermes github-kanban project list   # list onboarded GitHub repos
hermes github-kanban project onboard <owner/repo>   # register webhook + add repo
hermes github-kanban project remove <owner/repo>     # delete webhook + drop repo
```

## Projects (onboarded repos)

The bridge only creates kanban tasks for issues from **onboarded projects** — a
GitHub repo (`owner/repo`) you've explicitly wired in. Onboarding registers a
GitHub webhook on the repo (pointing at the bridge's configured public URL) and
adds the repo to the config's `projects` list. Removing deletes the webhook and
drops the repo. If the `projects` list is empty, the bridge accepts issues from
any repo (legacy behavior).

Set the public base URL before onboarding:

```bash
hermes github-kanban webhook --set-url https://kanban.example.com
hermes github-kanban project onboard owner/repo
```

The URL is stored as `webhook_base_url` in
`~/.hermes/scripts/github-kanban-bridge-config.json`; the bridge appends
`/webhooks/github-issues-to-kanban`. If it is unset, onboarding fails rather
than registering an unreachable URL. Existing installs migrating from zrok must
run `--set-url` once and update the URL on their GitHub webhook.

## Chat

```
/github-kanban status   /github-kanban list   /github-kanban sync   /github-kanban help
```

## Bundled skill

The operating runbook ships **inside the plugin** and is registered via
`ctx.register_skill` as `github-kanban:github-kanban` — it installs with the
plugin, no separate flat-skill copy. Load it explicitly when you need the
bridge operating guide:

```
skill_view(name='github-kanban:github-kanban')
```

## Requirements

- `GITHUB_TOKEN` in `~/.hermes/.env`
- Hermes kanban board (`hermes kanban boards create agentic-foundation`)
- Webhook platform enabled (`platforms.webhook.enabled: true`)
- A public URL for the webhook (your own reverse proxy or tunnel)
- Cron job for the sweep (see `install.sh`)

## License

MIT