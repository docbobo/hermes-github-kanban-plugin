"""Tool schemas for the github-kanban plugin (what the LLM sees)."""

SCHEMAS = {
    "ghk_status": {
        "name": "ghk_status",
        "description": "Show GitHub-Kanban bridge status: webhook route, board, dispatcher, cron job, sync state. Use when checking if the bridge is healthy.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "ghk_list": {
        "name": "ghk_list",
        "description": "List kanban tasks on the agentic-foundation board (all statuses). Use to see what's queued, running, or done.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "ghk_create_task": {
        "name": "ghk_create_task",
        "description": "Create a kanban task on the board and assign it to a profile. Use to add work items without going through GitHub issues.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "body": {"type": "string", "description": "Task body / description"},
                "assignee": {"type": "string", "description": "Profile to assign (coder, orchestrator, researcher, writer, reviewer)"},
                "priority": {"type": "integer", "description": "Priority (default 50)"},
            },
            "required": ["title"],
        },
    },
    "ghk_sync": {
        "name": "ghk_sync",
        "description": "Run a sync sweep: scan done tasks and sync them back to GitHub (comment + close existing issues, backfill mirror issues for unlinked tasks). Use to force a sync instead of waiting for the cron job.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "ghk_assign": {
        "name": "ghk_assign",
        "description": "Reassign a kanban task to a different profile. Use to change who works on a task.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Kanban task ID (e.g. t_abc123)"},
                "assignee": {"type": "string", "description": "Profile to assign (coder, orchestrator, researcher, writer, reviewer)"},
            },
            "required": ["task_id", "assignee"],
        },
    },
    "ghk_prepare": {
        "name": "ghk_prepare",
        "description": "Configure the bridge: set style/mood for issue descriptions, label-to-profile mappings, auto-labeling rules, and flow stages. Use to set up how incoming issues are handled.",
        "parameters": {
            "type": "object",
            "properties": {
                "show": {"type": "boolean", "description": "Show current config"},
                "board_slug": {"type": "string", "description": "Kanban board slug"},
                "board_name": {"type": "string", "description": "Kanban board display name"},
                "default_profile": {"type": "string", "description": "Default profile for unassigned issues"},
                "tone": {"type": "string", "description": "Style: tone (e.g. 'concise, technical')"},
                "label_profile": {"type": "string", "description": "Map: label=profile (JSON dict)"},
                "auto_label_rule": {"type": "string", "description": "Auto-label rule: 'field contains TEXT => label1,label2'"},
                "flow_stage": {"type": "string", "description": "Flow stage: stage=description"},
                "reset": {"type": "boolean", "description": "Reset config to defaults"},
            },
            "required": [],
        },
    },
}