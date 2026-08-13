"""Tool handlers for the github-kanban plugin."""

import json
import os
import subprocess

BOARD = os.environ.get("KANBAN_BOARD", "agentic-foundation")
SYNC_SWEEP = os.path.join(os.path.dirname(__file__), "..", "scripts", "kanban-sync-sweep.py")


def _kanban_cmd(args):
    """Run a hermes kanban command, return (stdout, stderr, exit_code)."""
    cmd = ["hermes", "kanban", "--board", BOARD] + args
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return res.stdout, res.stderr, res.returncode


def ghk_status(args, **kwargs):
    """Show bridge status: webhook, board, cron, sync state."""
    parts = []

    # Webhook
    try:
        r = subprocess.run(["hermes", "webhook", "list"], capture_output=True, text=True, timeout=10)
        lines = [l for l in r.stdout.splitlines() if "github-issues-to-kanban" in l or "◆" in l]
        parts.append("Webhook: " + (lines[0].strip() if lines else "not found"))
    except Exception:
        parts.append("Webhook: error")

    # Board
    stdout, _, rc = _kanban_cmd(["list"])
    parts.append(f"Board: {BOARD} (exit={rc})")
    task_lines = [l for l in stdout.splitlines() if l.strip() and not l.startswith("Board")]
    parts.append(f"Tasks: {len(task_lines)}")

    # Sync state
    state_file = os.path.expanduser("~/.hermes/kanban-sync-state.json")
    synced = 0
    if os.path.exists(state_file):
        try:
            state = json.load(open(state_file))
            synced = len(state)
        except Exception:
            pass
    parts.append(f"Synced: {synced} tasks tracked")

    # Cron
    try:
        r = subprocess.run(["hermes", "cron", "list"], capture_output=True, text=True, timeout=10)
        has_cron = "kanban-github-sync" in r.stdout
        parts.append(f"Cron: {'kanban-github-sync (active)' if has_cron else 'not found'}")
    except Exception:
        parts.append("Cron: error")

    return json.dumps({"status": "ok", "details": parts})


def ghk_list(args, **kwargs):
    """List kanban tasks on the board."""
    stdout, stderr, rc = _kanban_cmd(["list"])
    if rc != 0:
        return json.dumps({"error": stderr.strip()})
    return json.dumps({"tasks": stdout.strip()})


def ghk_create_task(args, **kwargs):
    """Create a kanban task."""
    title = args.get("title")
    body = args.get("body", "")
    assignee = args.get("assignee", "orchestrator")
    priority = args.get("priority", 50)

    cmd = ["hermes", "kanban", "--board", BOARD, "create", title,
           "--body", body, "--assignee", assignee,
           "--priority", str(priority), "--json"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        return json.dumps({"error": res.stderr.strip()[:500]})
    try:
        task = json.loads(res.stdout)
        return json.dumps({"created": True, "task": task})
    except json.JSONDecodeError:
        return json.dumps({"created": True, "raw": res.stdout.strip()})


def ghk_sync(args, **kwargs):
    """Run a sync sweep immediately."""
    env = dict(os.environ)
    # Ensure GITHUB_TOKEN is loaded
    if not env.get("GITHUB_TOKEN"):
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            for line in open(env_path):
                if line.strip().startswith("GITHUB_TOKEN="):
                    env["GITHUB_TOKEN"] = line.strip().split("=", 1)[1]
                    break

    sweep = os.path.abspath(SYNC_SWEEP)
    res = subprocess.run(["python3", sweep], capture_output=True, text=True, timeout=120, env=env)
    return json.dumps({
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip()[:500] if res.stderr else "",
        "exit_code": res.returncode,
    })


def ghk_assign(args, **kwargs):
    """Reassign a kanban task."""
    task_id = args.get("task_id")
    assignee = args.get("assignee")
    if not task_id or not assignee:
        return json.dumps({"error": "task_id and assignee required"})

    cmd = ["hermes", "kanban", "--board", BOARD, "reassign", task_id, assignee]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        return json.dumps({"error": res.stderr.strip()[:500]})
    return json.dumps({"assigned": True, "task_id": task_id, "assignee": assignee})