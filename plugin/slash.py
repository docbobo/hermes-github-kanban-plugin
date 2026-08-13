"""Slash command handler for /github-kanban."""

from . import cli as cli_mod


def handle_slash(raw_args: str) -> str:
    """Handle /github-kanban <action> in-session."""
    parts = raw_args.strip().split(None, 1) if raw_args else []
    action = parts[0] if parts else "status"
    rest = parts[1] if len(parts) > 1 else ""

    if action == "status":
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli_mod._cli_status()
        return buf.getvalue()

    elif action == "list":
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli_mod._cli_list()
        return buf.getvalue()

    elif action == "sync":
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli_mod._cli_sync()
        return buf.getvalue()

    elif action == "help" or not action:
        return (
            "/github-kanban <action>\n\n"
            "Actions:\n"
            "  status  - Show bridge status (webhook, board, cron, sync)\n"
            "  list    - List kanban tasks\n"
            "  sync    - Run a sync sweep immediately\n"
            "  help    - Show this help\n"
        )

    return f"Unknown action: {action}. Try /github-kanban help"