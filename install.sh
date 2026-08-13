#!/usr/bin/env bash
# Install the github-kanban plugin into Hermes.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PLUGIN_DIR="$HERMES_HOME/plugins/github-kanban"
SCRIPT_DIR="$HERMES_HOME/scripts"

echo "Installing github-kanban plugin..."

# Create plugin dir
mkdir -p "$PLUGIN_DIR"

# Copy plugin source
cp -r plugin/* "$PLUGIN_DIR/"

# Copy scripts
mkdir -p "$SCRIPT_DIR"
cp scripts/*.py "$SCRIPT_DIR/"

# The operating skill is BUNDLED inside the plugin (plugin/skills/github-kanban/)
# and registered via ctx.register_skill as 'github-kanban:github-kanban'.
# It is copied with the plugin source above — no separate flat-skill install.

echo ""
echo "Plugin installed to: $PLUGIN_DIR"
echo "Scripts installed to: $SCRIPT_DIR"
echo ""
echo "Next steps:"
echo "  1. hermes plugins enable github-kanban"
echo "  2. hermes kanban boards create agentic-foundation"
echo "  3. hermes webhook subscribe github-issues-to-kanban --events issues --script github-issue-to-kanban.py --prompt 'Issue #{issue.number}: {issue.title}' --description 'GitHub issues to kanban'"
echo "  4. Start the zrok tunnel: systemctl --user start zrok2-share.service"
echo "  5. Register the webhook in your GitHub repo (Settings → Webhooks) with the zrok URL + secret"
echo "  6. Install the cron sweep: hermes cron add --name kanban-github-sync --schedule 'every 5m' --script kanban-sync-sweep.py --no-agent"
echo ""
echo "Done. Restart Hermes for the plugin to take effect."