"""GitHub Issues <-> Hermes Kanban bridge plugin."""

__version__ = "1.0.0"

from .schemas import SCHEMAS
from .tools import ghk_status, ghk_list, ghk_create_task, ghk_sync, ghk_assign, ghk_prepare
from .slash import handle_slash
from .cli import setup_cli, handle_cli

TOOLSET = "github-kanban"


def register(ctx):
    """Wire all plugin components into Hermes."""

    # --- Tools (what the LLM sees) ---
    for name, schema in SCHEMAS.items():
        handler = {
            "ghk_status": ghk_status,
            "ghk_list": ghk_list,
            "ghk_create_task": ghk_create_task,
            "ghk_sync": ghk_sync,
            "ghk_assign": ghk_assign,
            "ghk_prepare": ghk_prepare,
        }.get(name)
        if handler:
            ctx.register_tool(
                name=name,
                toolset=TOOLSET,
                schema=schema,
                handler=handler,
            )

    # --- Slash command ---
    ctx.register_command(
        name="ghk",
        handler=handle_slash,
        description="GitHub-Kanban bridge: status, list, sync, assign",
        args_hint="<status|list|sync|help>",
    )

    # --- CLI subcommand ---
    ctx.register_cli_command(
        name="ghk",
        help="GitHub-Kanban bridge: sync GitHub issues to kanban and back",
        setup_fn=setup_cli,
        handler_fn=handle_cli,
    )