"""CLI subcommand tree for the github-kanban plugin: hermes github-kanban <verb>."""

import argparse
import json
import os
import subprocess

BOARD = os.environ.get("KANBAN_BOARD", "agentic-foundation")


def setup_cli(subparser):
    """Build the `hermes github-kanban` subcommand tree."""
    sub = subparser.add_subparsers(dest="github_kanban_action")

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

    # prepare — configure style/mood/labels for issue handling
    p_prepare = sub.add_parser("prepare", help="Configure style, mood, labels, and flow criteria for issue handling")
    p_prepare.add_argument("--show", action="store_true", help="Show current config")
    p_prepare.add_argument("--board-slug", help="Kanban board slug (kebab-case)")
    p_prepare.add_argument("--board-name", help="Kanban board display name")
    p_prepare.add_argument("--default-profile", help="Default profile for unassigned issues")
    p_prepare.add_argument("--tone", help="Style: tone for issue descriptions (e.g. 'concise, technical')")
    p_prepare.add_argument("--format", default="markdown", help="Style: format (markdown, plain)")
    p_prepare.add_argument("--language", default="english", help="Style: language")
    p_prepare.add_argument("--label-profile", action="append", nargs=2, metavar=("LABEL", "PROFILE"),
                           help="Map a GitHub label to a Hermes profile (repeatable)")
    p_prepare.add_argument("--auto-label", action="append", metavar="RULE",
                           help='Add auto-label rule: "field contains TEXT => label1,label2" (repeatable)')
    p_prepare.add_argument("--flow-label", action="append", nargs=2, metavar=("STAGE", "DESCRIPTION"),
                           help="Define a flow stage with description (repeatable)")
    p_prepare.add_argument("--reset", action="store_true", help="Reset config to defaults")

    # project — onboard/remove/list GitHub repos wired into the bridge
    p_project = sub.add_parser("project", help="Manage onboarded GitHub projects (repos)")
    pj = p_project.add_subparsers(dest="project_action")
    pj_onboard = pj.add_parser("onboard", help="Onboard a GitHub repo: register webhook + add to config")
    pj_onboard.add_argument("repo", help="owner/repo")
    pj_onboard.add_argument("--url", help="Public webhook URL (default: auto-detect from zrok)")
    pj_remove = pj.add_parser("remove", help="Remove a GitHub repo: delete webhook + drop from config")
    pj_remove.add_argument("repo", help="owner/repo")
    pj.add_parser("list", help="List onboarded projects")


def handle_cli(args):
    """Handle `hermes github-kanban <action>`."""
    action = getattr(args, "github_kanban_action", None)
    if not action:
        print("Usage: hermes github-kanban <status|list|create|sync|assign|webhook|install-sweep>")
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
    elif action == "prepare":
        _cli_prepare(args)
    elif action == "project":
        _cli_project(args)


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


def _cli_prepare(args):
    """Configure style, mood, labels, and flow criteria for issue handling."""
    CONFIG_PATH = os.path.expanduser("~/.hermes/scripts/github-kanban-bridge-config.json")

    if args.reset:
        # Reset to defaults
        config = _default_config()
        json.dump(config, open(CONFIG_PATH, "w"), indent=2)
        print("Config reset to defaults.")
        return

    # Load existing or defaults
    if os.path.exists(CONFIG_PATH):
        try:
            config = json.load(open(CONFIG_PATH))
        except Exception:
            config = _default_config()
    else:
        config = _default_config()

    if args.show:
        print(json.dumps(config, indent=2))
        return

    changed = False

    # Board settings
    if args.board_slug:
        config["board_slug"] = args.board_slug
        changed = True
    if args.board_name:
        config["board_name"] = args.board_name
        changed = True
    if args.default_profile:
        config["default_profile"] = args.default_profile
        changed = True

    # Style
    if args.tone:
        config.setdefault("style", {})
        config["style"]["tone"] = args.tone
        changed = True
    if args.format:
        config.setdefault("style", {})
        config["style"]["format"] = args.format
        changed = True
    if args.language:
        config.setdefault("style", {})
        config["style"]["language"] = args.language
        changed = True

    # Label profiles
    if args.label_profile:
        config.setdefault("label_profiles", {})
        for label, profile in args.label_profile:
            config["label_profiles"][label] = profile
        changed = True

    # Auto-label rules
    if args.auto_label:
        config.setdefault("auto_label_rules", [])
        for rule_str in args.auto_label:
            # Parse: "field contains TEXT => label1,label2"
            m = __import__("re").match(r'(.+?)\s*=>\s*(.+)', rule_str)
            if m:
                match_expr = m.group(1).strip()
                labels = [l.strip() for l in m.group(2).split(",")]
                config["auto_label_rules"].append({"match": match_expr, "labels": labels})
        changed = True

    # Flow labels
    if args.flow_label:
        config.setdefault("flow_labels", {})
        for stage, desc in args.flow_label:
            config["flow_labels"][stage] = {
                "description": desc,
                "auto_labels": [stage],
            }
        changed = True

    if changed:
        json.dump(config, open(CONFIG_PATH, "w"), indent=2)
        print(f"Config updated: {CONFIG_PATH}")
        print(f"  Board: {config.get('board_slug')}")
        print(f"  Default profile: {config.get('default_profile')}")
        print(f"  Tone: {config.get('style', {}).get('tone', 'N/A')}")
        print(f"  Label profiles: {len(config.get('label_profiles', {}))} mappings")
        print(f"  Auto-label rules: {len(config.get('auto_label_rules', []))} rules")
        print(f"  Flow stages: {len(config.get('flow_labels', {}))} stages")
    else:
        print("No changes. Use --show to view current config, or pass options to update.")


def _cli_project(args):
    """Onboard / remove / list GitHub projects wired into the bridge."""
    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "github-project-manage.py")
    script = os.path.abspath(script)
    action = getattr(args, "project_action", None)
    if not action:
        print("Usage: hermes github-kanban project <onboard|remove|list>")
        return
    cmd = ["python3", script, action]
    if action in ("onboard", "remove"):
        cmd.append(args.repo)
        if action == "onboard" and getattr(args, "url", None):
            cmd += ["--url", args.url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    print(r.stdout.strip())
    if r.stderr.strip():
        print(f"[stderr] {r.stderr.strip()[:300]}")


def _default_config():
    """Built-in default config (matches the shipped github-kanban-bridge-config.json)."""
    return {
        "board_slug": "agentic-foundation",
        "board_name": "Agentic Foundation",
        "default_profile": "scala-coder",
        "projects": [],
        "label_profiles": {
            "bug": "scala-coder", "feature": "scala-coder", "refactor": "scala-coder",
            "research": "researcher", "docs": "writer", "review": "reviewer",
            "orchestrator": "orchestrator",
        },
        "auto_label_rules": [],
        "flow_labels": {},
        "style": {"tone": "concise, technical, direct", "format": "markdown", "language": "english"},
    }