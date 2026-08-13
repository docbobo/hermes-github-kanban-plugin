#!/usr/bin/env python3
"""Kanban task -> GitHub issue sync-back.

When a kanban task on the agentic-foundation board is completed, this script
updates the originating GitHub issue: posts a comment with the result and
closes the issue.

Usage:
    kanban-sync-back.py <task_id> [--board <slug>]

Reads the task via `hermes kanban show`, extracts the GitHub issue URL from the
task body, and PATCHes the issue via the GitHub API (GITHUB_TOKEN from env).
"""
import json, os, re, subprocess, sys, urllib.request

BOARD = os.environ.get("KANBAN_BOARD", "agentic-foundation")
GITHUB_API = "https://api.github.com"
# Repo to backfill mirror issues into when a task has no GitHub link.
DEFAULT_REPO = os.environ.get("KANBAN_SYNC_REPO", "e8kor/agentic-foundation")

def get_task(task_id):
    cmd = ["hermes", "kanban", "--board", BOARD, "show", task_id, "--json"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        print(f"error: {res.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(res.stdout)
        # `kanban show --json` wraps the task under a "task" key
        return data.get("task", data)
    except json.JSONDecodeError:
        print(f"error: could not parse task: {res.stdout[:300]}", file=sys.stderr)
        sys.exit(1)

def extract_issue(task):
    """Find the GitHub issue URL in the task body."""
    body = task.get("body") or ""
    m = re.search(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", body)
    if not m:
        return None
    return {"owner": m.group(1), "repo": m.group(2), "number": int(m.group(3))}

def gh_request(method, path, payload=None):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        # Load from ~/.hermes/.env if not in the environment (cron runs fresh).
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            for line in open(env_path):
                line = line.strip()
                if line.startswith("GITHUB_TOKEN="):
                    token = line.split("=", 1)[1]
                    os.environ["GITHUB_TOKEN"] = token
                    break
    if not token:
        print("error: GITHUB_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    req = urllib.request.Request(
        f"{GITHUB_API}{path}",
        data=json.dumps(payload).encode() if payload else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def create_issue(task):
    """Backfill: create a GitHub issue mirroring a kanban task that has no link."""
    owner, repo = DEFAULT_REPO.split("/", 1)
    title = task.get("title") or f"Kanban task {task.get('id')}"
    body = task.get("body") or ""
    result = task.get("result") or ""
    issue_body = (
        f"Mirrored from Hermes kanban task `{task.get('id')}`.\n\n"
        f"**Status:** done\n\n"
        f"{body}\n\n"
        f"**Result:**\n{result}"
    )[:8000]
    created = gh_request(
        "POST",
        f"/repos/{owner}/{repo}/issues",
        {"title": title, "body": issue_body, "labels": ["kanban-mirror"]},
    )
    return {"owner": owner, "repo": repo, "number": created["number"]}

def main():
    if len(sys.argv) < 2:
        print("usage: kanban-sync-back.py <task_id> [--board <slug>]", file=sys.stderr)
        sys.exit(1)
    task_id = sys.argv[1]
    if "--board" in sys.argv:
        global BOARD
        BOARD = sys.argv[sys.argv.index("--board") + 1]

    task = get_task(task_id)
    issue = extract_issue(task)
    if not issue:
        # Backfill: no GitHub link on the task, so create a mirror issue.
        print("no GitHub issue link in task body; backfilling a mirror issue", file=sys.stderr)
        try:
            issue = create_issue(task)
            print(f"created mirror issue #{issue['number']}")
        except Exception as e:
            print(f"error creating mirror issue: {e}", file=sys.stderr)
            sys.exit(1)

    result = task.get("result") or ""
    summary = (result or task.get("body") or "")[:2000]
    comment = (
        f"✅ **Completed by Hermes kanban** (task `{task_id}`)\n\n"
        f"{summary}"
    )

    # Post a comment
    try:
        gh_request(
            "POST",
            f"/repos/{issue['owner']}/{issue['repo']}/issues/{issue['number']}/comments",
            {"body": comment},
        )
        print(f"commented on issue #{issue['number']}")
    except Exception as e:
        print(f"error commenting: {e}", file=sys.stderr)

    # Close the issue
    try:
        gh_request(
            "PATCH",
            f"/repos/{issue['owner']}/{issue['repo']}/issues/{issue['number']}",
            {"state": "closed"},
        )
        print(f"closed issue #{issue['number']}")
    except Exception as e:
        print(f"error closing: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
