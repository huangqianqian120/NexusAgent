"""命令注册模块（registry.py）单元测试."""

import pytest

from nexus.engine.messages import ConversationMessage, TextBlock
from nexus.commands.registry import (
    CommandRegistry,
    CommandResult,
    SlashCommand,
    _last_message_text,
    _rewind_turns,
    _render_plugin_command_prompt,
)


# ══════════════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════════════


def _make_user_text(text: str) -> ConversationMessage:
    return ConversationMessage(role="user", content=[TextBlock(text=text)])


def _make_assistant_text(text: str) -> ConversationMessage:
    return ConversationMessage(role="assistant", content=[TextBlock(text=text)])


# ══════════════════════════════════════════════════════════════
# CommandRegistry 测试
# ══════════════════════════════════════════════════════════════


class TestCommandRegistry:
    """测试 CommandRegistry 核心功能。"""

    def test_register_and_lookup(self):
        """注册命令后可通过 lookup 查找。"""
        registry = CommandRegistry()

        async def handler(_, __):
            return CommandResult(message="done")

        registry.register(SlashCommand(name="test", description="测试命令", handler=handler))

        cmd, args = registry.lookup("/test")
        assert cmd is not None
        assert cmd.name == "test"
        assert args == ""

    def test_lookup_with_args(self):
        """命令参数被正确提取。"""
        registry = CommandRegistry()

        async def handler(_, __):
            return CommandResult()

        registry.register(SlashCommand(name="foo", description="bar", handler=handler))

        cmd, args = registry.lookup("/foo arg1 arg2")
        assert cmd is not None
        assert args == "arg1 arg2"

    def test_lookup_missing_command(self):
        """不存在的命令返回 None。"""
        registry = CommandRegistry()
        result = registry.lookup("/nonexistent")
        assert result is None

    def test_lookup_non_slash(self):
        """非斜杠开头的内容不匹配。"""
        registry = CommandRegistry()
        result = registry.lookup("hello world")
        assert result is None

    def test_help_text(self):
        """help_text 包含所有已注册命令。"""
        registry = CommandRegistry()

        async def h1(_, __):
            return CommandResult()

        async def h2(_, __):
            return CommandResult()

        registry.register(SlashCommand(name="alpha", description="第一个", handler=h1))
        registry.register(SlashCommand(name="beta", description="第二个", handler=h2))

        text = registry.help_text()
        assert "/alpha" in text
        assert "/beta" in text
        assert "第一个" in text
        assert "第二个" in text

    def test_list_commands(self):
        """list_commands 返回已注册的命令列表。"""
        registry = CommandRegistry()

        async def h(_, __):
            return CommandResult()

        registry.register(SlashCommand(name="cmd1", description="desc1", handler=h))
        registry.register(SlashCommand(name="cmd2", description="desc2", handler=h))

        commands = registry.list_commands()
        assert len(commands) == 2
        assert {c.name for c in commands} == {"cmd1", "cmd2"}


# ══════════════════════════════════════════════════════════════
# CommandResult / CommandContext 测试
# ══════════════════════════════════════════════════════════════


class TestCommandResult:
    """测试 CommandResult 数据类。"""

    def test_default_values(self):
        """默认值正确。"""
        result = CommandResult()
        assert result.message is None
        assert result.should_exit is False
        assert result.clear_screen is False

    def test_custom_message(self):
        """自定义消息被保留。"""
        result = CommandResult(message="操作完成")
        assert result.message == "操作完成"

    def test_exit_flag(self):
        """退出标志。"""
        result = CommandResult(should_exit=True)
        assert result.should_exit is True

    def test_continue_pending(self):
        """继续挂起标志。"""
        result = CommandResult(continue_pending=True, continue_turns=3)
        assert result.continue_pending is True
        assert result.continue_turns == 3

    def test_submit_prompt(self):
        """提交 prompt。"""
        result = CommandResult(submit_prompt="帮我重构代码")
        assert result.submit_prompt == "帮我重构代码"


# ══════════════════════════════════════════════════════════════
# _last_message_text 测试
# ══════════════════════════════════════════════════════════════


class TestLastMessageText:
    """测试最后一条文本消息的提取。"""

    def test_returns_last_text(self):
        """返回最后一条有文本内容的消息。"""
        messages = [
            _make_user_text("第一条"),
            _make_assistant_text("第二条"),
            _make_user_text("最后一条"),
        ]
        assert _last_message_text(messages) == "最后一条"

    def test_skips_empty_text(self):
        """跳过文本为空的消息。"""
        messages = [
            _make_user_text("有效消息"),
            ConversationMessage(role="assistant", content=[TextBlock(text="")]),
            ConversationMessage(role="assistant", content=[TextBlock(text="   ")]),
        ]
        assert _last_message_text(messages) == "有效消息"

    def test_empty_messages(self):
        """全部为空返回空字符串。"""
        assert _last_message_text([]) == ""
        messages = [ConversationMessage(role="user", content=[TextBlock(text="")])]
        assert _last_message_text(messages) == ""


# ══════════════════════════════════════════════════════════════
# _rewind_turns 测试
# ══════════════════════════════════════════════════════════════


class TestRewindTurns:
    """测试对话回合回退功能。"""

    def test_rewind_one_turn(self):
        """回退一个回合移除最后一个 user→assistant 轮次。"""
        messages = [
            _make_user_text("问题1"),
            _make_assistant_text("回答1"),
            _make_user_text("问题2"),
            _make_assistant_text("回答2"),
        ]
        result = _rewind_turns(messages, turns=1)
        assert len(result) == 2
        assert result[0].content[0].text == "问题1"
        assert result[1].content[0].text == "回答1"

    def test_rewind_zero_turns(self):
        """回退 0 回合不改变列表。"""
        messages = [_make_user_text("问题"), _make_assistant_text("回答")]
        result = _rewind_turns(messages, turns=0)
        assert len(result) == 2

    def test_rewind_more_than_available(self):
        """回退回合数超过实际不崩溃。"""
        messages = [_make_user_text("唯一问题")]
        result = _rewind_turns(messages, turns=10)
        assert len(result) == 0

    def test_negative_turns_treated_as_zero(self):
        """负数回合被视为 0。"""
        messages = [_make_user_text("问题"), _make_assistant_text("回答")]
        result = _rewind_turns(messages, turns=-1)
        assert len(result) == 2

    def test_preserves_tool_messages(self):
        """保留工具调用和结果消息。"""
        from nexus.engine.messages import ToolUseBlock, ToolResultBlock

        messages = [
            _make_user_text("运行命令"),
            ConversationMessage(
                role="assistant",
                content=[ToolUseBlock(id="toolu_1", name="bash", input={})],
            ),
            ConversationMessage(
                role="user",
                content=[ToolResultBlock(tool_use_id="toolu_1", content="output")],
            ),
            _make_assistant_text("结果分析"),
            _make_user_text("继续"),
        ]
        result = _rewind_turns(messages, turns=1)
        # 应移除了最后一个 user 轮次及其后面
        assert len(result) <= 4


# ══════════════════════════════════════════════════════════════
# _render_plugin_command_prompt 测试
# ══════════════════════════════════════════════════════════════


class TestRenderPluginCommandPrompt:
    """测试插件命令 prompt 渲染。"""

    @pytest.fixture
    def basic_command(self):
        """创建一个基本的命令定义 mock。"""
        from unittest.mock import MagicMock

        cmd = MagicMock()
        cmd.content = "请执行 ${ARGUMENTS}"
        cmd.is_skill = False
        cmd.base_dir = None
        return cmd

    def test_substitutes_arguments(self, basic_command):
        """替换 ${ARGUMENTS} 占位符。"""
        result = _render_plugin_command_prompt(basic_command, "任务描述")
        assert "任务描述" in result
        assert "${ARGUMENTS}" not in result

    def test_substitutes_dollar_arguments(self, basic_command):
        """替换 $ARGUMENTS 占位符。"""
        basic_command.content = "执行 $ARGUMENTS"
        result = _render_plugin_command_prompt(basic_command, "测试")
        assert "执行 测试" in result

    def test_appends_arguments_when_no_placeholder(self, basic_command):
        """无占位符时在 prompt 末尾追加参数。"""
        basic_command.content = "运行任务"
        result = _render_plugin_command_prompt(basic_command, "额外参数")
        assert "Arguments: 额外参数" in result

    def test_no_args_no_placeholder(self, basic_command):
        """无参数且无占位符时不追加内容。"""
        basic_command.content = "简单任务"
        result = _render_plugin_command_prompt(basic_command, "")
        assert result == "简单任务"

    def test_skill_adds_base_dir(self, basic_command):
        """技能类型的命令添加 base_dir 前缀。"""
        basic_command.is_skill = True
        basic_command.base_dir = "/path/to/skill"
        basic_command.content = "运行技能"
        result = _render_plugin_command_prompt(basic_command, "")
        assert "Base directory for this skill: /path/to/skill" in result

    def test_replaces_session_id(self, basic_command):
        """替换 ${CLAUDE_SESSION_ID} 占位符。"""
        basic_command.content = "会话: ${CLAUDE_SESSION_ID}"
        result = _render_plugin_command_prompt(basic_command, "", session_id="sess_123")
        assert "sess_123" in result
        assert "${CLAUDE_SESSION_ID}" not in result

    def test_no_session_id_replacement_when_none(self, basic_command):
        """不传入 session_id 时占位符保留。"""
        basic_command.content = "会话: ${CLAUDE_SESSION_ID}"
        result = _render_plugin_command_prompt(basic_command, "")
        assert "${CLAUDE_SESSION_ID}" in result
