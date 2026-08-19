# Agent instructions — hermes-github-kanban-plugin

Shared entry point for AI assistants working in this repository. Keep it
project-specific and safe to publish: no tokens, webhook secrets, private repo
names, board contents, machine paths, or local-only notes.

## Read first

1. `README.md` — what the bridge does and how to install it
2. `plugin/skills/github-kanban/SKILL.md` — the registered operating skill
3. `plugin/cli.py` — the verb list is the clearest map of the surface

## What this plugin is

A bidirectional bridge between **GitHub Issues** and the **Hermes Kanban** board. It
syncs issues onto a board, assigns work to profiles by label, dispatches it, and
syncs completed tasks back to GitHub — including a backfill sweep for tasks that
finished while nothing was listening.

Seven tools (`github_kanban_status`, `github_kanban_list`,
`github_kanban_create_task`, `github_kanban_sync`, `github_kanban_assign`,
`github_kanban_prepare`, `github_kanban_project`), a `/github-kanban` slash
command, a `hermes github-kanban` CLI, and a bundled skill registered as
`github-kanban:github-kanban`.

Unlike its sibling plugins, this one has **no third-party Python dependencies** (no
`requirements.txt`) and no `api.py`/`store.py` of its own — the work happens in
standalone scripts driven by webhooks and cron.

## Repo layout

`plugin/` is the single source of truth. The live plugin at
`$HERMES_HOME/plugins/github-kanban` is a **symlink** to it, so editing a file here
edits the running plugin.

| Path | Responsibility |
|---|---|
| `plugin/__init__.py` | `register(ctx)` — tools (from `SCHEMAS`), slash, CLI, skill |
| `plugin/schemas.py` | `SCHEMAS` dict: what the model reads when choosing a tool |
| `plugin/tools.py` | Tool handlers. JSON string in, JSON string out, never raise |
| `plugin/cli.py` | `hermes github-kanban` verbs, incl. `webhook`, `install-sweep`, `project` |
| `plugin/slash.py` | `/github-kanban` dispatch, delegating to the CLI module |
| `plugin/skills/github-kanban/SKILL.md` | Registered skill (`ctx.register_skill`) |
| `scripts/github-issue-to-kanban.py` | Webhook payload on stdin → kanban task |
| `scripts/github-project-manage.py` | Onboard / remove / list bridged repos |
| `scripts/kanban-sync-back.py` | Completed kanban task → GitHub issue update |
| `scripts/kanban-sync-sweep.py` | Periodic backfill of missed completions |

`register()` builds tools by looking each `SCHEMAS` key up in a name→handler dict.
A schema whose name has no matching entry is **silently skipped** — so a typo in
either place produces a tool that quietly does not exist. Check
`hermes tools` after adding one.

## Hard rules

This plugin writes to a public issue tracker and dispatches autonomous work. Both
directions are visible to other people.

1. **Tool handlers return a JSON string and never raise** — success and failure
   alike. A handler that raises takes the agent turn down.
2. **Sync must be idempotent in both directions.** A webhook can be redelivered, a
   cron sweep re-runs on a schedule, and a task can be completed twice. Nothing may
   create a duplicate task, post a duplicate comment, or reopen a closed issue on
   replay. Prove the guard; do not assume it.
3. **Never comment on, close, or label a GitHub issue as a side effect.** Writes to
   someone's tracker are public and often notify people. If the caller did not ask
   for the write, do not perform it.
4. **The sweep is the safety net — keep it conservative.** It exists to catch
   completions that were missed, so it must tolerate seeing an already-synced task
   without acting. A sweep that acts on ambiguity turns one missed event into a
   stream of noise.
5. **Webhook payloads are untrusted input.** They arrive over the network from
   outside. Validate the signature, validate the shape, and never interpolate a
   payload field into a shell command or a path.
6. **Never print the webhook secret or `GITHUB_TOKEN`.** `hermes github-kanban
   webhook` displays configuration by design — be deliberate about what it shows,
   and keep secrets out of logs, errors, and issue comments.
7. **Dispatch spawns real agents that spend real money.** Label-based assignment
   decides who runs. A change that widens which issues get dispatched, or which
   profile picks them up, is a behavioural change that needs saying out loud in the
   PR — not a refactor.
8. **Board is the hard isolation boundary.** Workers are pinned to a board via the
   environment; do not add a path that lets a task reach a board it was not
   assigned to.
9. **Paths go through `get_hermes_home()`.** Never a hardcoded `~/.hermes` — each
   Hermes profile owns its own board and config.
10. **Secrets in `.env`, behaviour in `config.yaml`.** `GITHUB_TOKEN` is a
    credential.
11. **`github_kanban_status` is the diagnostic.** It reports webhook, board, cron,
    and sync state, and must stay useful when the bridge is broken.

## Verification

There is no automated test suite in this repo yet. The idempotency guards in the
sync scripts are the single most valuable thing to cover if you add one — they are
pure functions over a payload and a board state, so they are testable without
network.

Verify the real surface, read-only first:

```bash
hermes github-kanban status          # webhook + board + cron + sync state
hermes github-kanban list            # board read
hermes github-kanban project list    # which repos are bridged
```

For the webhook path, feed a recorded payload to the script on stdin rather than
triggering a real GitHub event:

```bash
python scripts/github-issue-to-kanban.py < recorded-payload.json
```

Run `hermes github-kanban sync` only when you are willing to have it act. Test
sync-back against a scratch repo, never a repo other people watch.

New tests: stdlib + pytest + `unittest.mock` only, no network. Synthesize webhook
payloads; never commit a real one (they contain user data and repo internals).

## Working on the live plugin

The live plugin is already a symlink to `plugin/`, so edits here are live. Python
changes need a Hermes restart; skills and docs do not. Sweep changes need the cron
job re-installed — `hermes github-kanban install-sweep`, then confirm with
`hermes cron list`.

`install.sh` here does `cp -r plugin/* "$PLUGIN_DIR/"` rather than the
`rm -rf` its siblings use — so running it in a symlinked dev checkout copies files
*through* the symlink into this repo, which is confusing but not destructive.
Either way, don't run it in a dev checkout; it is for fresh installs.

## Contribution style

- One concern per PR. No drive-by reformatting or renames.
- For a bug fix, state the symptom, the exact `file:line` where it manifests, and
  why the change alters that line's behaviour.
- For anything touching sync, dispatch, or webhook handling, state the replay
  scenario you considered (redelivery, double completion, concurrent sweep) and how
  the change behaves under it.
- Update `README.md` and the registered SKILL.md in the same PR when a verb, tool
  parameter, or config key changes.
- Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.

## Things to know

- **Adding a model tool is expensive.** Seven tools already ship their schemas on
  every API call the agent makes, whether or not the board is involved that turn.
  Prefer extending an existing tool, a CLI verb, or the skill.
- **The scripts are the product; the tools are a thin front end.** Most real
  behaviour lives in `scripts/`, driven by a webhook or cron. When something
  misbehaves in production, the script and its cron entry are where to look, not
  `tools.py`.
- **Naming was unified deliberately.** An earlier `ghk` prefix was renamed to the
  full `github-kanban` / `github_kanban` form across CLI, slash, tools, and config.
  Do not reintroduce a short prefix for convenience.
- **Sibling plugins share the tools/schemas/slash/cli shape** but not the internals.
  This one has no `api.py`, `store.py`, `tables.py`, or `debug.py` — do not import a
  pattern from a sibling without checking it exists here.
