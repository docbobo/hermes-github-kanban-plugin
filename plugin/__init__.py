"""GitHub Issues <-> Hermes Kanban bridge plugin."""

__version__ = "1.0.0"

from .schemas import SCHEMAS
from .tools import github_kanban_status, github_kanban_list, github_kanban_create_task, github_kanban_sync, github_kanban_assign, github_kanban_prepare
from .slash import handle_slash
from .cli import setup_cli, handle_cli

TOOLSET = "github-kanban"


def register(ctx):
    """Wire all plugin components into Hermes."""

    # --- Tools (what the LLM sees) ---
    for name, schema in SCHEMAS.items():
        handler = {
            "github_kanban_status": github_kanban_status,
            "github_kanban_list": github_kanban_list,
            "github_kanban_create_task": github_kanban_create_task,
            "github_kanban_sync": github_kanban_sync,
            "github_kanban_assign": github_kanban_assign,
            "github_kanban_prepare": github_kanban_prepare,
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
        name="github-kanban",
        handler=handle_slash,
        description="GitHub-Kanban bridge: status, list, sync, assign",
        args_hint="<status|list|sync|help>",
    )

    # --- CLI subcommand ---
    ctx.register_cli_command(
        name="github-kanban",
        help="GitHub-Kanban bridge: sync GitHub issues to kanban and back",
        setup_fn=setup_cli,
        handler_fn=handle_cli,
    )

    # --- Bundled operating skill (resolvable as 'github-kanban:github-kanban') ---
    from pathlib import Path
    skill_path = Path(__file__).parent / "skills" / "github-kanban" / "SKILL.md"
    if skill_path.exists():
        ctx.register_skill("github-kanban", skill_path)