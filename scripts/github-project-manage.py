#!/usr/bin/env python3
"""Onboard / remove / list GitHub projects wired into the kanban bridge.

A "project" is a GitHub repo (owner/name) whose issues flow into the Hermes
kanban board. Onboarding registers a GitHub webhook on that repo (pointing at
the bridge's configured public URL) AND records the repo in the bridge config's
`projects` list, so the webhook script only creates kanban tasks for onboarded
repos. Removing deletes the webhook and drops the repo from the list.

Usage:
    github-project-manage.py onboard <owner/repo> [--url <public-webhook-url>]
    github-project-manage.py remove  <owner/repo>
    github-project-manage.py list
    github-project-manage.py webhook-url          # print the configured public URL

The public URL comes from `webhook_base_url` in the bridge config. Set it with:
    hermes github-kanban webhook --set-url https://your.domain

GITHUB_TOKEN is read from the environment or ~/.hermes/.env.
"""
import json, os, sys, urllib.error, urllib.request

GITHUB_API = "https://api.github.com"
CONFIG_PATH = os.path.expanduser("~/.hermes/scripts/github-kanban-bridge-config.json")
WEBHOOK_ROUTE = "github-issues-to-kanban"


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


def get_token():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            for line in open(env_path):
                line = line.strip()
                if line.startswith("GITHUB_TOKEN="):
                    token = line.split("=", 1)[1]
                    os.environ["GITHUB_TOKEN"] = token
                    break
    if not token:
        print("error: GITHUB_TOKEN not set (env or ~/.hermes/.env)", file=sys.stderr)
        sys.exit(1)
    return token


def gh_request(method, path, payload=None):
    token = get_token()
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
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r) if r.status != 204 else {}
    except urllib.error.HTTPError as e:
        try:
            body = json.load(e)
        except Exception:
            body = {}
        return e.code, body


def _route_suffix():
    return f"/webhooks/{WEBHOOK_ROUTE}"


def resolve_webhook_url(override=None):
    """Resolve the public webhook URL from an override or the bridge config.

    Returns None (after printing an actionable error) when no URL is
    configured. Never falls back to localhost.
    """
    if override:
        url = override.strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            print("error: webhook URL must be an absolute http(s) URL, "
                  "e.g. https://kanban.example.com", file=sys.stderr)
            return None
        if "/webhooks/" in url:
            return url
        return f"{url}{_route_suffix()}"

    base = (load_config().get("webhook_base_url") or "").strip().rstrip("/")
    if not base:
        print("error: no webhook_base_url configured; cannot register a webhook.", file=sys.stderr)
        print("Set it with: hermes github-kanban webhook --set-url https://your.domain", file=sys.stderr)
        return None
    if base.endswith(_route_suffix()):
        return base
    return f"{base}{_route_suffix()}"


def find_webhook(owner, repo):
    """Return the existing bridge webhook id on a repo, or None."""
    status, data = gh_request("GET", f"/repos/{owner}/{repo}/hooks")
    if status != 200:
        return None
    for hook in data:
        if hook.get("config", {}).get("url", "").endswith(f"/webhooks/{WEBHOOK_ROUTE}"):
            return hook.get("id")
    return None


def onboard(owner, repo, url):
    cfg = load_config()
    projects = cfg.setdefault("projects", [])
    if repo in projects:
        print(f"already onboarded: {repo}")
        return 0

    # Register the GitHub webhook on the repo (issues events).
    status, data = gh_request(
        "POST", f"/repos/{owner}/{repo}/hooks",
        {
            "name": "web",
            "active": True,
            "events": ["issues"],
            "config": {
                "url": url,
                "content_type": "json",
                "insecure_ssl": "0",
            },
        },
    )
    if status not in (200, 201):
        print(f"error registering webhook on {repo}: {status} {data.get('message', data)}", file=sys.stderr)
        return 1

    projects.append(repo)
    save_config(cfg)
    print(f"onboarded {repo} (webhook id {data.get('id')})")
    return 0


def remove(owner, repo):
    cfg = load_config()
    projects = cfg.get("projects", [])
    if repo not in projects:
        print(f"not onboarded: {repo}")
        return 0

    # Delete the GitHub webhook if present.
    hook_id = find_webhook(owner, repo)
    if hook_id is not None:
        status, _ = gh_request("DELETE", f"/repos/{owner}/{repo}/hooks/{hook_id}")
        if status not in (200, 204):
            print(f"warning: could not delete webhook {hook_id} on {repo} ({status})", file=sys.stderr)

    projects.remove(repo)
    save_config(cfg)
    print(f"removed {repo}")
    return 0


def list_projects():
    cfg = load_config()
    projects = cfg.get("projects", [])
    if not projects:
        print("no projects onboarded")
        return 0
    for p in projects:
        print(p)
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]

    if cmd == "webhook-url":
        url = resolve_webhook_url()
        if not url:
            return 1
        print(url)
        return 0

    if cmd == "list":
        return list_projects()

    if cmd in ("onboard", "remove"):
        if len(sys.argv) < 3:
            print(f"usage: github-project-manage.py {cmd} <owner/repo>", file=sys.stderr)
            sys.exit(1)
        repo = sys.argv[2].strip().strip("/")
        if "/" not in repo:
            print(f"error: expected owner/repo, got '{repo}'", file=sys.stderr)
            sys.exit(1)
        owner, name = repo.split("/", 1)
        if cmd == "onboard":
            override = None
            if "--url" in sys.argv:
                override = sys.argv[sys.argv.index("--url") + 1]
            url = resolve_webhook_url(override)
            if not url:
                return 1
            return onboard(owner, name, url)
        else:
            return remove(owner, name)

    print(f"unknown command: {cmd}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
