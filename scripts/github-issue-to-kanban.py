#!/usr/bin/env python3
"""GitHub issue -> kanban task bridge.

Reads a GitHub webhook payload (JSON) on stdin, and if it's a new/opened issue,
creates a kanban task on the agentic-foundation board and assigns it to a
profile based on labels. Prints JSON to stdout so the webhook route can use it.

Exit 0 + JSON stdout  -> proceed (agent runs / task created)
Exit 0 + empty stdout  -> ignore (webhook returns 200, no agent run)
Exit nonzero          -> ignore
"""
import json, subprocess, sys, os

BOARD = "agentic-foundation"

# label -> profile assignment (fall back to scala-coder)
LABEL_PROFILE = {
    # language-specific coders
    "scala": "scala-coder",
    "spark": "scala-coder",
    "python": "python-coder",
    "rust": "rust-coder",
    # generic work types -> scala-coder (the original coder profile)
    "bug": "scala-coder",
    "feature": "scala-coder",
    "refactor": "scala-coder",
    # non-coding roles
    "research": "researcher",
    "docs": "writer",
    "review": "reviewer",
}
DEFAULT_PROFILE = "scala-coder"

def main():
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    # Only act on issue events (opened / reopened)
    action = payload.get("action", "")
    issue = payload.get("issue")
    if not issue or action not in ("opened", "reopened"):
        sys.exit(0)

    number = issue.get("number")
    title = issue.get("title", "")
    body = (issue.get("body") or "")[:2000]
    labels = [l.get("name", "").lower() for l in issue.get("labels", [])]
    repo = payload.get("repository", {}).get("full_name", "unknown/repo")
    url = issue.get("html_url", "")

    # Pick profile from labels
    profile = DEFAULT_PROFILE
    for lab in labels:
        if lab in LABEL_PROFILE:
            profile = LABEL_PROFILE[lab]
            break

    # Build the kanban task body with GitHub context
    task_body = (
        f"GitHub issue #{number} from {repo}\n"
        f"URL: {url}\n"
        f"Labels: {', '.join(labels) or 'none'}\n\n"
        f"{body}"
    )

    # Create the kanban task, assigned to the profile
    cmd = [
        "hermes", "kanban", "--board", BOARD, "create", title,
        "--body", task_body,
        "--assignee", profile,
        "--priority", "50",
        "--json",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(0)

    if res.returncode != 0:
        # Idempotency: if the task already exists, don't create a duplicate
        print(json.dumps({"error": res.stderr.strip()[:500]}))
        sys.exit(0)

    try:
        task = json.loads(res.stdout)
    except json.JSONDecodeError:
        task = {"raw": res.stdout.strip()}

    # Emit a summary for the agent prompt
    out = {
        "created": True,
        "issue_number": number,
        "title": title,
        "assigned_to": profile,
        "kanban_task": task,
        "board": BOARD,
    }
    # Print the summary to stderr for debugging/logs.
    print(json.dumps(out), file=sys.stderr)
    # Print [SILENT] to stdout so the webhook returns 200 with NO agent run —
    # the kanban dispatcher (daemon) picks up the task and assigns the profile.
    print("[SILENT]")

if __name__ == "__main__":
    main()
