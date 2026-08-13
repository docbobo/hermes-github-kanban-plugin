"""CLI subcommand tree for the github-kanban plugin: hermes ghk <verb>."""

import argparse
import json
import os
import subprocess

BOARD = os.environ.get("KANBAN_BOARD", "agentic-foundation")


def setup_cli(subparser):
    """Build the `hermes ghk` subcommand tree."""
    sub = subparser.add_subparsers(dest="ghk_action")

    # status
    sub.add_parser("status", help="Show bridge status (webhook, board, cron, sync)")

    # list
    sub.add_parser("list", help="List kanban tasks on the board")

    # create
    p_create = sub.add_parser("create", help="Create a kanban task")
    p_create.add_argument("title", help="Task title")
    p_create.add_argument("--body", default="", help="Task body")
    p_create.add_argument("--assignee", default="orchestrator", help="Profile to assign")
    p_create.add_argument("--priority", type=int, default=50, help="Priority")

    # sync
    sub.add_parser("sync", help="Run a sync sweep immediately")

    # assign
    p_assign = sub.add_parser("assign", help="Reassign a task")
    p_assign.add_argument("task_id", help="Task ID")
    p_assign.add_argument("assignee", help="Profile to assign")

    # webhook
    p_webhook = sub.add_parser("webhook", help="Show webhook info (URL, secret)")
    p_webhook.add_argument("--url", action="store_true", help="Print only the webhook URL")

    # sweep-install
    p_install = sub.add_parser("install-sweep", help="Install/update the cron sweep job")
    p_install.add_argument("--schedule", default="every 5m", help="Cron schedule (default: every 5m)")


def handle_cli(args):
    """Handle `hermes ghk <action>`."""
    action = getattr(args, "ghk_action", None)
    if not action:
        print("Usage: hermes ghk <status|list|create|sync|assign|webhook|install-sweep>")
        return

    if action == "status":
        _cli_status()
    elif action == "list":
        _cli_list()
    elif action == "create":
        _cli_create(args)
    elif action == "sync":
        _cli_sync()
    elif action == "assign":
        _cli_assign(args)
    elif action == "webhook":
        _cli_webhook(args)
    elif action == "install-sweep":
        _cli_install_sweep(args)


def _cli_status():
    r = subprocess.run(["hermes", "webhook", "list"], capture_output=True, text=True, timeout=10)
    for line in r.stdout.splitlines():
        if "github-issues-to-kanban" in line or "◆" in line:
            print(line.strip())
    print(f"\nBoard: {BOARD}")
    r2 = subprocess.run(["hermes", "kanban", "--board", BOARD, "list"], capture_output=True, text=True, timeout=10)
    print(r2.stdout.strip())
    state = os.path.expanduser("~/.hermes/kanban-sync-state.json")
    print(f"Sync state: {len(json.load(open(state))) if os.path.exists(state) else 0} tasks tracked")


def _cli_list():
    r = subprocess.run(["hermes", "kanban", "--board", BOARD, "list"], capture_output=True, text=True, timeout=10)
    print(r.stdout.strip())


def _cli_create(args):
    cmd = ["hermes", "kanban", "--board", BOARD, "create", args.title,
           "--body", args.body, "--assignee", args.assignee,
           "--priority", str(args.priority)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    print(r.stdout.strip() if r.returncode == 0 else f"Error: {r.stderr.strip()}")


def _cli_sync():
    env = dict(os.environ)
    if not env.get("GITHUB_TOKEN"):
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            for line in open(env_path):
                if line.strip().startswith("GITHUB_TOKEN="):
                    env["GITHUB_TOKEN"] = line.strip().split("=", 1)[1]
                    break
    sweep = os.path.join(os.path.dirname(__file__), "..", "scripts", "kanban-sync-sweep.py")
    sweep = os.path.abspath(sweep)
    r = subprocess.run(["python3", sweep], capture_output=True, text=True, timeout=120, env=env)
    print(r.stdout.strip())
    if r.stderr.strip():
        print(f"[stderr] {r.stderr.strip()[:300]}")


def _cli_assign(args):
    cmd = ["hermes", "kanban", "--board", BOARD, "reassign", args.task_id, args.assignee]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    print(r.stdout.strip() if r.returncode == 0 else f"Error: {r.stderr.strip()}")


def _cli_webhook(args):
    subs_path = os.path.expanduser("~/.hermes/webhook_subscriptions.json")
    if os.path.exists(subs_path):
        subs = json.load(open(subs_path))
        sub = subs.get("github-issues-to-kanban", {})
        if args.url:
            # Get the zrok URL from the systemd service log
            r = subprocess.run(
                ["journalctl", "--user", "-u", "zrok2-share.service", "--no-pager"],
                capture_output=True, text=True, timeout=10)
            import re
            urls = re.findall(r"([a-z0-9]+\.shares\.zrok\.io)", r.stdout)
            if urls:
                print(f"https://{urls[-1]}/webhooks/github-issues-to-kanban")
            else:
                print("http://localhost:8644/webhooks/github-issues-to-kanban")
        else:
            print(f"Route: github-issues-to-kanban")
            print(f"Events: {sub.get('events', [])}")
            print(f"Script: {sub.get('script', 'N/A')}")
            print(f"Secret: {sub.get('secret', 'N/A')[:8]}...")
    else:
        print("No webhook subscriptions found")


def _cli_install_sweep(args):
    """Install the cron sweep job via the hermes cron CLI."""
    print(f"To install the sweep cron job, use the cronjob tool or:")
    print(f"  hermes cron add --name kanban-github-sync --schedule '{args.schedule}' --script kanban-sync-sweep.py --no-agent")