#!/usr/bin/env python3
"""Periodic sync: completed kanban tasks -> GitHub issues.

Scans the agentic-foundation board for tasks in 'done' state, and for each one
that hasn't been synced yet (tracked in a state file), runs the sync-back to
update the originating GitHub issue. Idempotent — a task is only synced once.

Run on a schedule (cron). Prints a summary to stdout.
"""
import json, os, subprocess, sys

CONFIG_PATH = os.path.expanduser("~/.hermes/scripts/github-kanban-bridge-config.json")

def _load_board():
    """Read board slug from config, fall back to env/default."""
    if os.path.exists(CONFIG_PATH):
        try:
            cfg = json.load(open(CONFIG_PATH))
            return cfg.get("board_slug", "agentic-foundation")
        except Exception:
            pass
    return os.environ.get("KANBAN_BOARD", "agentic-foundation")

BOARD = _load_board()
STATE_FILE = os.path.expanduser("~/.hermes/kanban-sync-state.json")
SYNC_SCRIPT = os.path.expanduser("~/.hermes/scripts/kanban-sync-back.py")

def ensure_github_token():
    """Load GITHUB_TOKEN from ~/.hermes/.env if not already in the environment.

    Cron jobs run in a fresh environment without the token, so the sweep must
    source it itself or the sync-back fails silently.
    """
    if os.environ.get("GITHUB_TOKEN"):
        return
    env_path = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                os.environ["GITHUB_TOKEN"] = line.split("=", 1)[1]
                return
    print("warning: GITHUB_TOKEN not found in env or ~/.hermes/.env", file=sys.stderr)

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except Exception:
            return {}
    return {}

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), indent=2)

def list_done_tasks():
    cmd = ["hermes", "kanban", "--board", BOARD, "list", "--json"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        print(f"error listing: {res.stderr.strip()}", file=sys.stderr)
        return []
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError:
        return []
    tasks = data if isinstance(data, list) else data.get("tasks", [])
    return [t for t in tasks if t.get("status") == "done"]

def main():
    ensure_github_token()
    state = load_state()
    done = list_done_tasks()
    synced = 0
    for task in done:
        tid = task.get("id")
        if not tid or state.get(tid):
            continue
        # Run the sync-back for this task
        env = dict(os.environ)
        res = subprocess.run(
            [sys.executable, SYNC_SCRIPT, tid, "--board", BOARD],
            capture_output=True, text=True, timeout=60, env=env,
        )
        if res.returncode == 0:
            state[tid] = {"synced_at": None, "ok": True}
            synced += 1
            print(f"synced {tid}")
        else:
            # Don't mark as synced on failure so it retries next tick
            print(f"sync failed for {tid}: {res.stderr.strip()[:200]}", file=sys.stderr)
    if synced:
        save_state(state)
    print(f"done: {len(done)} completed, {synced} newly synced")

if __name__ == "__main__":
    main()
