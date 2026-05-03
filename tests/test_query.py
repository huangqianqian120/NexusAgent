"""查询引擎模块（query.py）单元测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nexus.engine.query import (
    MAX_TRACKED_READ_FILES,
    MAX_TRACKED_SKILLS,
    MAX_TRACKED_ASYNC_AGENT_EVENTS,
    MaxTurnsExceeded,
    QueryContext,
    _extract_permission_command,
    _is_prompt_too_long_error,
    _record_tool_carryover,
    _remember_async_agent_activity,
    _remember_read_file,
    _remember_skill_invocation,
    _resolve_permission_file_path,
    _tool_metadata_bucket,
    _update_plan_mode,
)


# ══════════════════════════════════════════════════════════════
# _is_prompt_too_long_error 测试
# ══════════════════════════════════════════════════════════════


class TestIsPromptTooLongError:
    """测试 prompt too long 错误检测。"""

    @pytest.mark.parametrize(
        "message",
        [
            "prompt too long",
            "context length exceeded",
            "maximum context reached",
            "context window full",
            "too many tokens",
            "too large for the model",
            "exceeds maximum context length",
            "PROMPT TOO LONG",
            "Error: Prompt Too Long for model",
        ],
    )
    def test_detects_prompt_too_long(self, message):
        """检测各种 prompt too long 错误消息。"""
        assert _is_prompt_too_long_error(Exception(message)) is True

    @pytest.mark.parametrize(
        "message",
        [
            "connection timeout",
            "invalid api key",
            "internal server error",
            "rate limit exceeded",
            "",
            "model not found",
        ],
    )
    def test_rejects_other_errors(self, message):
        """其他错误消息返回 False。"""
        assert _is_prompt_too_long_error(Exception(message)) is False


# ══════════════════════════════════════════════════════════════
# MaxTurnsExceeded 测试
# ══════════════════════════════════════════════════════════════


class TestMaxTurnsExceeded:
    """测试 MaxTurnsExceeded 异常。"""

    def test_is_runtime_error(self):
        """MaxTurnsExceeded 是 RuntimeError 的子类。"""
        exc = MaxTurnsExceeded(200)
        assert isinstance(exc, RuntimeError)

    def test_message_contains_max_turns(self):
        """异常消息包含 max_turns 值。"""
        exc = MaxTurnsExceeded(50)
        assert "50" in str(exc)

    def test_stores_max_turns(self):
        """异常对象保存 max_turns 属性。"""
        exc = MaxTurnsExceeded(100)
        assert exc.max_turns == 100


# ══════════════════════════════════════════════════════════════
# QueryContext 测试
# ══════════════════════════════════════════════════════════════


class TestQueryContext:
    """测试 QueryContext 数据类。"""

    def test_default_max_turns(self):
        """默认 max_turns 为 200。"""
        ctx = QueryContext(
            api_client=MagicMock(),
            tool_registry=MagicMock(),
            permission_checker=MagicMock(),
            cwd=Path("/tmp"),
            model="test-model",
            system_prompt="",
            max_tokens=4096,
        )
        assert ctx.max_turns == 200

    def test_default_optional_fields(self):
        """可选字段默认为 None。"""
        ctx = QueryContext(
            api_client=MagicMock(),
            tool_registry=MagicMock(),
            permission_checker=MagicMock(),
            cwd=Path("/tmp"),
            model="test-model",
            system_prompt="",
            max_tokens=4096,
        )
        assert ctx.permission_prompt is None
        assert ctx.ask_user_prompt is None
        assert ctx.hook_executor is None
        assert ctx.tool_metadata is None

    def test_custom_values(self):
        """自定义值被正确保存。"""
        mock_client = MagicMock()
        mock_registry = MagicMock()
        mock_checker = MagicMock()
        ctx = QueryContext(
            api_client=mock_client,
            tool_registry=mock_registry,
            permission_checker=mock_checker,
            cwd=Path("/home/user"),
            model="claude-sonnet-4-6",
            system_prompt="你是助手",
            max_tokens=8192,
            max_turns=100,
            permission_prompt=lambda a, t: None,
            ask_user_prompt=lambda q: None,
            hook_executor=MagicMock(),
            tool_metadata={"read_file_state": []},
        )
        assert ctx.api_client is mock_client
        assert ctx.model == "claude-sonnet-4-6"
        assert ctx.max_tokens == 8192
        assert ctx.max_turns == 100
        assert ctx.cwd == Path("/home/user")
        assert ctx.tool_metadata == {"read_file_state": []}


# ══════════════════════════════════════════════════════════════
# _tool_metadata_bucket 测试
# ══════════════════════════════════════════════════════════════


class TestToolMetadataBucket:
    """测试工具元数据桶函数。"""

    def test_none_metadata_returns_empty(self):
        """metadata 为 None 时返回空列表。"""
        assert _tool_metadata_bucket(None, "any_key") == []

    def test_creates_bucket_when_missing(self):
        """键不存在时创建新列表。"""
        metadata: dict[str, object] = {}
        result = _tool_metadata_bucket(metadata, "test_key")
        assert result == []
        assert "test_key" in metadata

    def test_returns_existing_bucket(self):
        """返回已存在的列表。"""
        existing = ["a", "b"]
        metadata = {"items": existing}
        result = _tool_metadata_bucket(metadata, "items")
        assert result is existing

    def test_replaces_non_list_value(self):
        """非列表值被替换为空列表。"""
        metadata = {"items": "not_a_list"}
        result = _tool_metadata_bucket(metadata, "items")
        assert result == []
        assert metadata["items"] == []


# ══════════════════════════════════════════════════════════════
# _remember_read_file 测试
# ══════════════════════════════════════════════════════════════


class TestRememberReadFile:
    """测试文件读取记录。"""

    def test_adds_read_file_entry(self):
        """添加文件读取记录到 metadata。"""
        metadata: dict[str, object] = {}
        _remember_read_file(
            metadata,
            path="/tmp/test.py",
            offset=0,
            limit=100,
            output="line1\nline2\nline3\n",
        )
        bucket = metadata.get("read_file_state")
        assert bucket is not None
        assert len(bucket) == 1
        assert bucket[0]["path"] == "/tmp/test.py"
        assert "line1" in bucket[0]["preview"]

    def test_none_metadata_noop(self):
        """metadata 为 None 不抛异常。"""
        _remember_read_file(None, path="/tmp/x.py", offset=0, limit=10, output="")

    def test_truncates_when_exceeds_limit(self):
        """超过 MAX_TRACKED_READ_FILES 时截断旧记录。"""
        metadata: dict[str, object] = {}
        for i in range(MAX_TRACKED_READ_FILES + 3):
            _remember_read_file(
                metadata,
                path=f"/tmp/file_{i}.py",
                offset=0,
                limit=10,
                output=f"file {i} content",
            )
        bucket = metadata["read_file_state"]
        assert len(bucket) == MAX_TRACKED_READ_FILES
        # 保留的是最新的文件
        assert bucket[-1]["path"] == f"/tmp/file_{MAX_TRACKED_READ_FILES + 2}.py"


# ══════════════════════════════════════════════════════════════
# _remember_skill_invocation 测试
# ══════════════════════════════════════════════════════════════


class TestRememberSkillInvocation:
    """测试技能调用记录。"""

    def test_adds_skill_name(self):
        """添加技能名称。"""
        metadata: dict[str, object] = {}
        _remember_skill_invocation(metadata, skill_name="code-review")
        assert "code-review" in metadata["invoked_skills"]

    def test_skips_empty_name(self):
        """空名称不添加。"""
        metadata: dict[str, object] = {}
        _remember_skill_invocation(metadata, skill_name="")
        assert metadata.get("invoked_skills", []) == []

    def test_skips_whitespace_name(self):
        """纯空格名称不添加。"""
        metadata: dict[str, object] = {}
        _remember_skill_invocation(metadata, skill_name="   ")
        assert metadata.get("invoked_skills", []) == []

    def test_deduplicates_by_moving_to_end(self):
        """重复技能移动到列表末尾。"""
        metadata: dict[str, object] = {}
        _remember_skill_invocation(metadata, skill_name="skill-a")
        _remember_skill_invocation(metadata, skill_name="skill-b")
        _remember_skill_invocation(metadata, skill_name="skill-a")
        bucket = metadata["invoked_skills"]
        assert bucket == ["skill-b", "skill-a"]

    def test_truncates_when_exceeds_limit(self):
        """超过最大技能数时截断。"""
        metadata: dict[str, object] = {}
        for i in range(MAX_TRACKED_SKILLS + 5):
            _remember_skill_invocation(metadata, skill_name=f"skill-{i}")
        assert len(metadata["invoked_skills"]) == MAX_TRACKED_SKILLS
        # 保留的是最新的技能
        assert "skill-0" not in metadata["invoked_skills"]

    def test_none_metadata_noop(self):
        """metadata 为 None 不抛异常。"""
        _remember_skill_invocation(None, skill_name="test")


# ══════════════════════════════════════════════════════════════
# _remember_async_agent_activity 测试
# ══════════════════════════════════════════════════════════════


class TestRememberAsyncAgentActivity:
    """测试异步 agent 活动记录。"""

    def test_agent_tool_with_description(self):
        """使用 description 参数的 agent 工具。"""
        metadata: dict[str, object] = {}
        _remember_async_agent_activity(
            metadata,
            tool_name="agent",
            tool_input={"description": "分析代码"},
            output="分析完成",
        )
        bucket = metadata["async_agent_state"]
        assert len(bucket) == 1
        assert "分析代码" in bucket[0]
        assert "分析完成" in bucket[0]

    def test_agent_tool_with_prompt_fallback(self):
        """agent 工具无 description 时使用 prompt 字段。"""
        metadata: dict[str, object] = {}
        _remember_async_agent_activity(
            metadata,
            tool_name="agent",
            tool_input={"prompt": "运行测试"},
            output="",
        )
        assert "运行测试" in metadata["async_agent_state"][0]

    def test_send_message_tool(self):
        """send_message 工具记录。"""
        metadata: dict[str, object] = {}
        _remember_async_agent_activity(
            metadata,
            tool_name="send_message",
            tool_input={"task_id": "task_123"},
            output="",
        )
        assert "task_123" in metadata["async_agent_state"][0]

    def test_unknown_tool_uses_output(self):
        """未知工具使用 output 作为摘要。"""
        metadata: dict[str, object] = {}
        _remember_async_agent_activity(
            metadata,
            tool_name="some_other_tool",
            tool_input={},
            output="自定义输出",
        )
        assert "自定义输出" in metadata["async_agent_state"][0]

    def test_truncates_when_exceeds_limit(self):
        """超过最大事件数时截断。"""
        metadata: dict[str, object] = {}
        for i in range(MAX_TRACKED_ASYNC_AGENT_EVENTS + 3):
            _remember_async_agent_activity(
                metadata,
                tool_name="agent",
                tool_input={"description": f"任务{i}"},
                output="",
            )
        assert len(metadata["async_agent_state"]) == MAX_TRACKED_ASYNC_AGENT_EVENTS

    def test_none_metadata_noop(self):
        """metadata 为 None 不抛异常。"""
        _remember_async_agent_activity(
            None,
            tool_name="agent",
            tool_input={},
            output="",
        )


# ══════════════════════════════════════════════════════════════
# _update_plan_mode 测试
# ══════════════════════════════════════════════════════════════


class TestUpdatePlanMode:
    """测试计划模式更新。"""

    def test_sets_permission_mode(self):
        """设置 permission_mode 键。"""
        metadata: dict[str, object] = {}
        _update_plan_mode(metadata, "plan")
        assert metadata["permission_mode"] == "plan"

    def test_overwrites_existing_mode(self):
        """覆盖已存在的模式。"""
        metadata: dict[str, object] = {"permission_mode": "default"}
        _update_plan_mode(metadata, "plan")
        assert metadata["permission_mode"] == "plan"

    def test_none_metadata_noop(self):
        """metadata 为 None 不抛异常。"""
        _update_plan_mode(None, "plan")


# ══════════════════════════════════════════════════════════════
# _record_tool_carryover 测试
# ══════════════════════════════════════════════════════════════


def _make_context(metadata=None):
    return QueryContext(
        api_client=MagicMock(),
        tool_registry=MagicMock(),
        permission_checker=MagicMock(),
        cwd=Path("/tmp"),
        model="test-model",
        system_prompt="",
        max_tokens=4096,
        tool_metadata=metadata,
    )


class TestRecordToolCarryover:
    """测试工具 carryover 记录。"""

    def test_read_file_triggers_remember(self):
        """read_file 工具触发文件记录。"""
        metadata: dict[str, object] = {}
        ctx = _make_context(metadata)
        _record_tool_carryover(
            ctx,
            tool_name="read_file",
            tool_input={"offset": 10, "limit": 50},
            tool_output="content line 1\ncontent line 2",
            is_error=False,
            resolved_file_path="/tmp/code.py",
        )
        bucket = metadata.get("read_file_state")
        assert bucket is not None
        assert len(bucket) == 1
        assert bucket[0]["path"] == "/tmp/code.py"

    def test_skill_triggers_remember(self):
        """skill 工具触发技能记录。"""
        metadata: dict[str, object] = {}
        ctx = _make_context(metadata)
        _record_tool_carryover(
            ctx,
            tool_name="skill",
            tool_input={"name": "code-review"},
            tool_output="",
            is_error=False,
            resolved_file_path=None,
        )
        assert "code-review" in metadata["invoked_skills"]

    def test_agent_triggers_remember(self):
        """agent 工具触发异步活动记录。"""
        metadata: dict[str, object] = {}
        ctx = _make_context(metadata)
        _record_tool_carryover(
            ctx,
            tool_name="agent",
            tool_input={"description": "子任务"},
            tool_output="",
            is_error=False,
            resolved_file_path=None,
        )
        assert len(metadata["async_agent_state"]) == 1

    def test_send_message_triggers_remember(self):
        """send_message 工具触发异步活动记录。"""
        metadata: dict[str, object] = {}
        ctx = _make_context(metadata)
        _record_tool_carryover(
            ctx,
            tool_name="send_message",
            tool_input={"task_id": "agent_1"},
            tool_output="",
            is_error=False,
            resolved_file_path=None,
        )
        assert len(metadata["async_agent_state"]) == 1

    def test_error_skips_recording(self):
        """is_error 为 True 时跳过记录。"""
        metadata: dict[str, object] = {}
        ctx = _make_context(metadata)
        _record_tool_carryover(
            ctx,
            tool_name="read_file",
            tool_input={"offset": 0, "limit": 10},
            tool_output="error output",
            is_error=True,
            resolved_file_path="/tmp/fail.py",
        )
        assert "read_file_state" not in metadata

    def test_enter_plan_mode(self):
        """enter_plan_mode 工具更新模式。"""
        metadata: dict[str, object] = {}
        ctx = _make_context(metadata)
        _record_tool_carryover(
            ctx,
            tool_name="enter_plan_mode",
            tool_input={},
            tool_output="",
            is_error=False,
            resolved_file_path=None,
        )
        assert metadata["permission_mode"] == "plan"

    def test_exit_plan_mode(self):
        """exit_plan_mode 工具恢复默认模式。"""
        metadata: dict[str, object] = {"permission_mode": "plan"}
        ctx = _make_context(metadata)
        _record_tool_carryover(
            ctx,
            tool_name="exit_plan_mode",
            tool_input={},
            tool_output="",
            is_error=False,
            resolved_file_path=None,
        )
        assert metadata["permission_mode"] == "default"

    def test_none_metadata_noop(self):
        """metadata 为 None 时不抛异常。"""
        ctx = _make_context(None)
        _record_tool_carryover(
            ctx,
            tool_name="read_file",
            tool_input={"offset": 0, "limit": 10},
            tool_output="content",
            is_error=False,
            resolved_file_path="/tmp/f.py",
        )

    def test_unknown_tool_noop(self):
        """未知工具不记录任何内容。"""
        metadata: dict[str, object] = {}
        ctx = _make_context(metadata)
        _record_tool_carryover(
            ctx,
            tool_name="bash",
            tool_input={},
            tool_output="done",
            is_error=False,
            resolved_file_path=None,
        )
        assert metadata == {}


# ══════════════════════════════════════════════════════════════
# _resolve_permission_file_path 测试
# ══════════════════════════════════════════════════════════════


class TestResolvePermissionFilePath:
    """测试权限文件路径解析。"""

    def test_from_raw_input_file_path(self):
        """从 raw_input 的 file_path 键提取。"""
        cwd = Path("/tmp")
        result = _resolve_permission_file_path(cwd, {"file_path": "/etc/hosts"}, None)
        assert result == str(Path("/etc/hosts").resolve())

    def test_from_raw_input_path(self):
        """从 raw_input 的 path 键提取。"""
        cwd = Path("/tmp")
        result = _resolve_permission_file_path(cwd, {"path": "/var/log/syslog"}, None)
        assert result == str(Path("/var/log/syslog").resolve())

    def test_file_path_priority_over_path(self):
        """file_path 优先于 path。"""
        cwd = Path("/tmp")
        result = _resolve_permission_file_path(
            cwd, {"file_path": "/etc/hosts", "path": "/var/log/syslog"}, None
        )
        assert result == str(Path("/etc/hosts").resolve())

    def test_relative_path_resolved(self):
        """相对路径相对于 cwd 解析。"""
        cwd = Path("/home/user")
        result = _resolve_permission_file_path(cwd, {"path": "config.json"}, None)
        exp = str((cwd / "config.json").resolve())
        assert result == exp

    def test_expanduser_tilde(self):
        """路径中的 ~ 被展开。"""
        cwd = Path("/tmp")
        raw_input = {"file_path": "~/dotfiles/.zshrc"}
        result = _resolve_permission_file_path(cwd, raw_input, None)
        assert result.startswith("/")
        assert result.endswith("/.zshrc")

    def test_from_parsed_input_file_path(self):
        """从 parsed_input 的 file_path 属性提取。"""
        cwd = Path("/tmp")
        parsed = MagicMock()
        parsed.file_path = "/opt/config.ini"
        result = _resolve_permission_file_path(cwd, {}, parsed)
        assert result == "/opt/config.ini"

    def test_from_parsed_input_path(self):
        """从 parsed_input 的 path 属性提取。"""
        cwd = Path("/tmp")
        parsed = MagicMock()
        parsed.path = "/usr/local/etc/app.conf"
        result = _resolve_permission_file_path(cwd, {}, parsed)
        assert result == "/usr/local/etc/app.conf"

    def test_returns_none_when_not_found(self):
        """无路径时返回 None。"""
        cwd = Path("/tmp")
        result = _resolve_permission_file_path(cwd, {}, None)
        assert result is None

    def test_empty_string_ignored(self):
        """空字符串被忽略。"""
        cwd = Path("/tmp")
        result = _resolve_permission_file_path(cwd, {"path": ""}, None)
        assert result is None

    def test_whitespace_string_ignored(self):
        """纯空格字符串被忽略。"""
        cwd = Path("/tmp")
        parsed = MagicMock()
        parsed.file_path = "   "
        result = _resolve_permission_file_path(cwd, {}, parsed)
        assert result is None


# ══════════════════════════════════════════════════════════════
# _extract_permission_command 测试
# ══════════════════════════════════════════════════════════════


class TestExtractPermissionCommand:
    """测试权限命令提取。"""

    def test_from_raw_input(self):
        """从 raw_input 提取命令。"""
        result = _extract_permission_command({"command": "git status"}, None)
        assert result == "git status"

    def test_from_parsed_input(self):
        """从 parsed_input 提取命令。"""
        parsed = MagicMock()
        parsed.command = "npm install"
        result = _extract_permission_command({}, parsed)
        assert result == "npm install"

    def test_raw_input_priority(self):
        """raw_input 优先于 parsed_input。"""
        parsed = MagicMock()
        parsed.command = "parsed command"
        result = _extract_permission_command({"command": "raw command"}, parsed)
        assert result == "raw command"

    def test_returns_none_when_not_found(self):
        """无命令时返回 None。"""
        result = _extract_permission_command({}, None)
        assert result is None

    def test_empty_string_ignored(self):
        """空字符串被忽略。"""
        result = _extract_permission_command({"command": ""}, None)
        assert result is None

    def test_whitespace_string_ignored(self):
        """纯空格被忽略。"""
        result = _extract_permission_command({"command": "   "}, None)
        assert result is None

    def test_parsed_empty_string_fallback(self):
        """raw_input 无命令时回退到 parsed_input。"""
        parsed = MagicMock()
        parsed.command = "fallback command"
        result = _extract_permission_command({"command": ""}, parsed)
        assert result == "fallback command"
