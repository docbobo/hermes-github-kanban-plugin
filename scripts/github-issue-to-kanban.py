#!/usr/bin/env python3
"""GitHub issue -> kanban task bridge (config-driven).

Reads a GitHub webhook payload (JSON) on stdin, and if it's a new/opened issue,
creates a kanban task on the configured board (auto-creating it if missing) and
assigns it to a profile based on labels. Applies flow labels from config.

Exit 0 + [SILENT] stdout  -> webhook returns 200, no agent run (dispatcher picks up task)
Exit 0 + empty stdout     -> ignore (webhook returns 200, no action)
Exit nonzero              -> ignore
"""
import json, subprocess, sys, os, re

CONFIG_PATH = os.path.expanduser("~/.hermes/scripts/ghk-bridge-config.json")

def load_config():
    """Load bridge config, with built-in defaults."""
    defaults = {
        "board_slug": "agentic-foundation",
        "board_name": "Agentic Foundation",
        "default_profile": "scala-coder",
        "label_profiles": {
            "bug": "scala-coder", "feature": "scala-coder", "refactor": "scala-coder",
            "research": "researcher", "docs": "writer", "review": "reviewer",
            "orchestrator": "orchestrator",
        },
        "auto_label_rules": [],
        "flow_labels": {},
        "style": {"tone": "concise, technical, direct"},
    }
    if os.path.exists(CONFIG_PATH):
        try:
            user_cfg = json.load(open(CONFIG_PATH))
            # Deep merge: user config overrides defaults
            for k, v in user_cfg.items():
                if isinstance(v, dict) and isinstance(defaults.get(k), dict):
                    defaults[k].update(v)
                else:
                    defaults[k] = v
        except Exception:
            pass
    return defaults

def ensure_board(slug, name):
    """Create the kanban board if it doesn't exist."""
    # Check if board exists
    res = subprocess.run(
        ["hermes", "kanban", "boards", "list", "--json"],
        capture_output=True, text=True, timeout=15)
    if res.returncode == 0:
        try:
            boards = json.loads(res.stdout)
            if isinstance(boards, list):
                existing = [b.get("slug") for b in boards]
            elif isinstance(boards, dict):
                existing = [b.get("slug") for b in boards.get("boards", [boards])]
            else:
                existing = []
            if slug in existing:
                return True
        except Exception:
            pass
    # Create the board
    res = subprocess.run(
        ["hermes", "kanban", "boards", "create", slug, "--name", name],
        capture_output=True, text=True, timeout=15)
    return res.returncode == 0

def apply_auto_labels(title, body, existing_labels, rules):
    """Apply auto-labeling rules from config."""
    labels = list(existing_labels)
    title_l = title.lower()
    body_l = (body or "").lower()
    for rule in rules:
        match = rule.get("match", "")
        add_labels = rule.get("labels", [])
        # Parse match expression: "field contains TEXT" or "label includes TEXT"
        m = re.match(r"(title|body|label)\s+(contains|includes)\s+(.+)", match, re.I)
        if m:
            field, op, text = m.groups()
            text = text.strip().strip('"').lower()
            if field == "title" and text in title_l:
                for l in add_labels:
                    if l not in labels:
                        labels.append(l)
            elif field == "body" and text in body_l:
                for l in add_labels:
                    if l not in labels:
                        labels.append(l)
            elif field == "label":
                for existing in existing_labels:
                    if text in existing.lower():
                        for l in add_labels:
                            if l not in labels:
                                labels.append(l)
    return labels

def pick_profile(labels, label_profiles, default_profile):
    """Pick the profile based on the first matching label."""
    for lab in labels:
        if lab in label_profiles:
            return label_profiles[lab]
    return default_profile

def main():
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    action = payload.get("action", "")
    issue = payload.get("issue")
    if not issue or action not in ("opened", "reopened"):
        sys.exit(0)

    config = load_config()

    number = issue.get("number")
    title = issue.get("title", "")
    body = (issue.get("body") or "")[:2000]
    gh_labels = [l.get("name", "").lower() for l in issue.get("labels", [])]
    repo = payload.get("repository", {}).get("full_name", "unknown/repo")
    url = issue.get("html_url", "")

    # Apply auto-labeling rules
    all_labels = apply_auto_labels(title, body, gh_labels, config.get("auto_label_rules", []))

    # Determine flow stage: if no flow label, add 'triage'
    flow_labels = config.get("flow_labels", {})
    has_flow = any(lab in flow_labels for lab in all_labels)
    if not has_flow and flow_labels:
        all_labels.append("triage")

    # Pick profile
    profile = pick_profile(all_labels, config.get("label_profiles", {}), config.get("default_profile", "orchestrator"))

    # Ensure board exists
    board_slug = config.get("board_slug", "agentic-foundation")
    board_name = config.get("board_name", "Agentic Foundation")
    ensure_board(board_slug, board_name)

    # Build the kanban task body with GitHub context
    task_body = (
        f"GitHub issue #{number} from {repo}\n"
        f"URL: {url}\n"
        f"Labels: {', '.join(all_labels) or 'none'}\n\n"
        f"{body}"
    )

    # Create the kanban task
    cmd = [
        "hermes", "kanban", "--board", board_slug, "create", title,
        "--body", task_body,
        "--assignee", profile,
        "--priority", "50",
        "--json",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(0)

    if res.returncode != 0:
        print(json.dumps({"error": res.stderr.strip()[:500]}), file=sys.stderr)
        sys.exit(0)

    try:
        task = json.loads(res.stdout)
    except json.JSONDecodeError:
        task = {"raw": res.stdout.strip()}

    out = {
        "created": True,
        "issue_number": number,
        "title": title,
        "labels": all_labels,
        "assigned_to": profile,
        "board": board_slug,
        "kanban_task": task,
    }
    print(json.dumps(out), file=sys.stderr)
    print("[SILENT]")

if __name__ == "__main__":
    main()