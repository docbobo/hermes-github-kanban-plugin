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


def ghk_prepare(args, **kwargs):
    """Configure the bridge: style, labels, flow criteria."""
    CONFIG_PATH = os.path.expanduser("~/.hermes/scripts/ghk-bridge-config.json")

    def default_config():
        return {
            "board_slug": "agentic-foundation",
            "board_name": "Agentic Foundation",
            "default_profile": "scala-coder",
            "label_profiles": {
                "bug": "scala-coder", "feature": "scala-coder", "refactor": "scala-coder",
                "research": "researcher", "docs": "writer", "review": "reviewer",
            },
            "auto_label_rules": [],
            "flow_labels": {},
            "style": {"tone": "concise, technical, direct", "format": "markdown", "language": "english"},
        }

    if args.get("reset"):
        config = default_config()
        json.dump(config, open(CONFIG_PATH, "w"), indent=2)
        return json.dumps({"reset": True})

    # Load existing
    if os.path.exists(CONFIG_PATH):
        try:
            config = json.load(open(CONFIG_PATH))
        except Exception:
            config = default_config()
    else:
        config = default_config()

    if args.get("show"):
        return json.dumps(config)

    changed = False
    if args.get("board_slug"):
        config["board_slug"] = args["board_slug"]; changed = True
    if args.get("board_name"):
        config["board_name"] = args["board_name"]; changed = True
    if args.get("default_profile"):
        config["default_profile"] = args["default_profile"]; changed = True
    if args.get("tone"):
        config.setdefault("style", {})["tone"] = args["tone"]; changed = True
    if args.get("label_profile"):
        # label_profile is a JSON dict string like '{"bug": "coder"}'
        try:
            mapping = json.loads(args["label_profile"])
            config.setdefault("label_profiles", {}).update(mapping)
            changed = True
        except json.JSONDecodeError:
            return json.dumps({"error": "label_profile must be valid JSON"})
    if args.get("auto_label_rule"):
        import re
        m = re.match(r'(.+?)\s*=>\s*(.+)', args["auto_label_rule"])
        if m:
            config.setdefault("auto_label_rules", []).append({
                "match": m.group(1).strip(),
                "labels": [l.strip() for l in m.group(2).split(",")],
            })
            changed = True
    if args.get("flow_stage"):
        # flow_stage is "stage=description"
        if "=" in args["flow_stage"]:
            stage, desc = args["flow_stage"].split("=", 1)
            config.setdefault("flow_labels", {})[stage.strip()] = {
                "description": desc.strip(), "auto_labels": [stage.strip()],
            }
            changed = True

    if changed:
        json.dump(config, open(CONFIG_PATH, "w"), indent=2)
        return json.dumps({"updated": True, "board": config.get("board_slug")})
    return json.dumps({"no_changes": True, "message": "Use show=true to view config"})