"""Built-in tool registration."""

from nexus.tools.ask_user_question_tool import AskUserQuestionTool
from nexus.tools.agent_tool import AgentTool
from nexus.tools.bash_tool import BashTool
from nexus.tools.base import BaseTool, ToolExecutionContext, ToolRegistry, ToolResult
from nexus.tools.brief_tool import BriefTool
from nexus.tools.config_tool import ConfigTool
from nexus.tools.cron_create_tool import CronCreateTool
from nexus.tools.cron_delete_tool import CronDeleteTool
from nexus.tools.cron_list_tool import CronListTool
from nexus.tools.cron_toggle_tool import CronToggleTool
from nexus.tools.enter_plan_mode_tool import EnterPlanModeTool
from nexus.tools.enter_worktree_tool import EnterWorktreeTool
from nexus.tools.exit_plan_mode_tool import ExitPlanModeTool
from nexus.tools.exit_worktree_tool import ExitWorktreeTool
from nexus.tools.file_edit_tool import FileEditTool
from nexus.tools.file_read_tool import FileReadTool
from nexus.tools.file_write_tool import FileWriteTool
from nexus.tools.glob_tool import GlobTool
from nexus.tools.grep_tool import GrepTool
from nexus.tools.list_mcp_resources_tool import ListMcpResourcesTool
from nexus.tools.lsp_tool import LspTool
from nexus.tools.mcp_auth_tool import McpAuthTool
from nexus.tools.mcp_tool import McpToolAdapter
from nexus.tools.notebook_edit_tool import NotebookEditTool
from nexus.tools.read_mcp_resource_tool import ReadMcpResourceTool
from nexus.tools.remote_trigger_tool import RemoteTriggerTool
from nexus.tools.send_message_tool import SendMessageTool
from nexus.tools.skill_tool import SkillTool
from nexus.tools.sleep_tool import SleepTool
from nexus.tools.task_create_tool import TaskCreateTool
from nexus.tools.task_get_tool import TaskGetTool
from nexus.tools.task_list_tool import TaskListTool
from nexus.tools.task_output_tool import TaskOutputTool
from nexus.tools.task_stop_tool import TaskStopTool
from nexus.tools.task_update_tool import TaskUpdateTool
from nexus.tools.team_create_tool import TeamCreateTool
from nexus.tools.team_delete_tool import TeamDeleteTool
from nexus.tools.todo_write_tool import TodoWriteTool
from nexus.tools.tool_search_tool import ToolSearchTool
from nexus.tools.web_fetch_tool import WebFetchTool
from nexus.tools.web_search_tool import WebSearchTool


def create_default_tool_registry(mcp_manager=None) -> ToolRegistry:
    """Return the default built-in tool registry."""
    registry = ToolRegistry()
    for tool in (
        BashTool(),
        AskUserQuestionTool(),
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        NotebookEditTool(),
        LspTool(),
        McpAuthTool(),
        GlobTool(),
        GrepTool(),
        SkillTool(),
        ToolSearchTool(),
        WebFetchTool(),
        WebSearchTool(),
        ConfigTool(),
        BriefTool(),
        SleepTool(),
        EnterWorktreeTool(),
        ExitWorktreeTool(),
        TodoWriteTool(),
        EnterPlanModeTool(),
        ExitPlanModeTool(),
        CronCreateTool(),
        CronListTool(),
        CronDeleteTool(),
        CronToggleTool(),
        RemoteTriggerTool(),
        TaskCreateTool(),
        TaskGetTool(),
        TaskListTool(),
        TaskStopTool(),
        TaskOutputTool(),
        TaskUpdateTool(),
        AgentTool(),
        SendMessageTool(),
        TeamCreateTool(),
        TeamDeleteTool(),
    ):
        registry.register(tool)
    if mcp_manager is not None:
        registry.register(ListMcpResourcesTool(mcp_manager))
        registry.register(ReadMcpResourceTool(mcp_manager))
        for tool_info in mcp_manager.list_tools():
            registry.register(McpToolAdapter(mcp_manager, tool_info))
    return registry


__all__ = [
    "BaseTool",
    "ToolExecutionContext",
    "ToolRegistry",
    "ToolResult",
    "create_default_tool_registry",
]
