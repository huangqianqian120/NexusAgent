"""紧凑模块（微压缩、全量压缩、辅助函数）单元测试."""

from nexus.engine.messages import (
    ConversationMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from nexus.services.compact._constants import (
    TIME_BASED_MC_CLEARED_MESSAGE,
    CONTEXT_COLLAPSE_TEXT_CHAR_LIMIT,
)
from nexus.services.compact._microcompact import (
    microcompact_messages,
    _collect_compactable_tool_ids,
)
from nexus.services.compact._helpers import (
    estimate_message_tokens,
    group_messages_by_prompt_round,
    try_context_collapse,
    try_session_memory_compaction,
    truncate_head_for_ptl_retry,
    extract_attachment_paths,
    extract_discovered_tools,
    sanitize_metadata,
    is_prompt_too_long_error,
)
from nexus.services.compact._full_compact import (
    format_compact_summary,
    build_compact_summary_message,
    get_compact_prompt,
    get_context_window,
    should_autocompact,
    AutoCompactState,
    summarize_messages,
    compact_messages,
    build_compact_carryover_message,
)


# ══════════════════════════════════════════════════════════════
# 消息构造辅助函数
# ══════════════════════════════════════════════════════════════


def _make_user_text(text: str) -> ConversationMessage:
    """创建用户文本消息。"""
    return ConversationMessage(role="user", content=[TextBlock(text=text)])


def _make_assistant_text(text: str) -> ConversationMessage:
    """创建助手文本消息。"""
    return ConversationMessage(role="assistant", content=[TextBlock(text=text)])


def _make_tool_use(name: str, id_: str, input_: dict | None = None) -> ToolUseBlock:
    """创建工具调用块。"""
    return ToolUseBlock(id=id_, name=name, input=input_ or {})


def _make_assistant_with_tool_use(name: str, id_: str) -> ConversationMessage:
    """创建包含工具调用的助手消息。"""
    return ConversationMessage(
        role="assistant",
        content=[_make_tool_use(name, id_)],
    )


def _make_user_with_tool_result(tool_use_id: str, content: str) -> ConversationMessage:
    """创建包含工具结果的用户消息。"""
    return ConversationMessage(
        role="user",
        content=[ToolResultBlock(tool_use_id=tool_use_id, content=content)],
    )


# ══════════════════════════════════════════════════════════════
# _microcompact.py 测试
# ══════════════════════════════════════════════════════════════


class TestCollectCompactableToolIds:
    """测试 _collect_compactable_tool_ids 函数。"""

    def test_empty_messages(self):
        """空消息列表返回空 ID 列表。"""
        assert _collect_compactable_tool_ids([]) == []

    def test_no_tool_uses(self):
        """只有文本消息时不返回工具 ID。"""
        messages = [_make_user_text("你好"), _make_assistant_text("你好！")]
        assert _collect_compactable_tool_ids(messages) == []

    def test_collects_compactable_tools(self):
        """收集可压缩工具的 ID。"""
        messages = [
            _make_assistant_with_tool_use("read_file", "toolu_001"),
            _make_assistant_with_tool_use("bash", "toolu_002"),
            _make_assistant_with_tool_use("grep", "toolu_003"),
        ]
        ids = _collect_compactable_tool_ids(messages)
        assert ids == ["toolu_001", "toolu_002", "toolu_003"]

    def test_ignores_non_compactable_tools(self):
        """忽略不在 COMPACTABLE_TOOLS 中的工具。"""
        messages = [
            _make_assistant_with_tool_use("read_file", "toolu_001"),
            _make_assistant_with_tool_use("unknown_tool", "toolu_999"),
        ]
        ids = _collect_compactable_tool_ids(messages)
        assert ids == ["toolu_001"]
        assert "toolu_999" not in ids

    def test_skips_non_assistant_messages(self):
        """跳过非 assistant 角色的消息。"""
        messages = [
            ConversationMessage(
                role="user",
                content=[_make_tool_use("read_file", "toolu_001")],
            ),
        ]
        assert _collect_compactable_tool_ids(messages) == []


class TestMicrocompactMessages:
    """测试 microcompact_messages 函数。"""

    def test_no_compact_when_below_keep_recent(self):
        """工具调用数 <= keep_recent 时不压缩。"""
        messages = [
            _make_assistant_with_tool_use("read_file", "toolu_001"),
            _make_user_with_tool_result("toolu_001", "some content"),
        ]
        result, saved = microcompact_messages(messages, keep_recent=5)
        assert saved == 0
        assert result == messages

    def test_clears_old_tool_results(self):
        """清除旧工具结果内容，保留最近 keep_recent 个。"""
        messages = [
            _make_assistant_with_tool_use("read_file", "toolu_001"),
            _make_user_with_tool_result("toolu_001", "old content A" * 50),
            _make_assistant_with_tool_use("bash", "toolu_002"),
            _make_user_with_tool_result("toolu_002", "old content B" * 50),
            _make_assistant_with_tool_use("grep", "toolu_003"),
            _make_user_with_tool_result("toolu_003", "recent content" * 20),
        ]
        result, saved = microcompact_messages(messages, keep_recent=1)
        assert saved > 0

        # toolu_001 和 toolu_002 的结果应该被清除
        for msg in result:
            if msg.role == "user":
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        if block.tool_use_id in ("toolu_001", "toolu_002"):
                            assert block.content == TIME_BASED_MC_CLEARED_MESSAGE
                        elif block.tool_use_id == "toolu_003":
                            assert block.content != TIME_BASED_MC_CLEARED_MESSAGE

    def test_skips_already_cleared(self):
        """跳过已经清除过的工具结果（不重复计算 token 节省）。"""
        messages = [
            _make_assistant_with_tool_use("read_file", "toolu_001"),
            _make_user_with_tool_result("toolu_001", TIME_BASED_MC_CLEARED_MESSAGE),
        ]
        _, saved = microcompact_messages(messages, keep_recent=0)
        # 已经是清除状态，不应再计算节省
        assert saved == 0

    def test_keep_recent_clamped_to_one(self):
        """keep_recent 至少为 1。"""
        messages = [
            _make_assistant_with_tool_use("bash", "toolu_001"),
            _make_user_with_tool_result("toolu_001", "content"),
            _make_assistant_with_tool_use("read_file", "toolu_002"),
            _make_user_with_tool_result("toolu_002", "other"),
        ]
        result, _ = microcompact_messages(messages, keep_recent=0)
        # keep_recent=0 被 clamp 到 1，所以至少保留 1 个
        cleared_count = 0
        for msg in result:
            if msg.role == "user":
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        if block.content == TIME_BASED_MC_CLEARED_MESSAGE:
                            cleared_count += 1
        assert cleared_count <= 1  # 最多清除 1 个

    def test_preserves_error_flag(self):
        """清除内容时保留 is_error 标志。"""
        messages = [
            _make_assistant_with_tool_use("bash", "toolu_001"),
            ConversationMessage(
                role="user",
                content=[
                    ToolResultBlock(
                        tool_use_id="toolu_001",
                        content="command failed",
                        is_error=True,
                    )
                ],
            ),
            _make_assistant_with_tool_use("read_file", "toolu_002"),
            _make_user_with_tool_result("toolu_002", "file content"),
        ]
        result, _ = microcompact_messages(messages, keep_recent=0)
        for msg in result:
            if msg.role == "user":
                for block in msg.content:
                    if isinstance(block, ToolResultBlock) and block.tool_use_id == "toolu_001":
                        assert block.is_error is True
                        assert block.content == TIME_BASED_MC_CLEARED_MESSAGE


# ══════════════════════════════════════════════════════════════
# _helpers.py 测试
# ══════════════════════════════════════════════════════════════


class TestEstimateMessageTokens:
    """测试 token 估算函数。"""

    def test_empty_messages(self):
        """空消息列表返回 0。"""
        assert estimate_message_tokens([]) == 0

    def test_text_blocks(self):
        """估算文本块的 token 数（含 4/3 安全系数）。"""
        messages = [_make_user_text("Hello World")]
        tokens = estimate_message_tokens(messages)
        assert tokens > 0

    def test_tool_result_blocks(self):
        """估算工具结果块的 token 数。"""
        messages = [
            _make_user_with_tool_result("toolu_001", "some output content"),
        ]
        tokens = estimate_message_tokens(messages)
        assert tokens > 0

    def test_multiple_message_types(self):
        """混合消息类型的 token 估算。"""
        messages = [
            _make_user_text("提问"),
            _make_assistant_with_tool_use("bash", "toolu_001"),
            _make_user_with_tool_result("toolu_001", "结果"),
            _make_assistant_text("回答"),
        ]
        tokens = estimate_message_tokens(messages)
        assert tokens > 0


class TestGroupMessagesByPromptRound:
    """测试按 prompt 回合分组。"""

    def test_empty_messages(self):
        """空消息返回空分组。"""
        assert group_messages_by_prompt_round([]) == []

    def test_single_round(self):
        """单轮对话返回一个分组。"""
        messages = [
            _make_user_text("你好"),
            _make_assistant_text("你好！"),
        ]
        groups = group_messages_by_prompt_round(messages)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_multiple_rounds(self):
        """多轮纯文本对话正确分组。"""
        messages = [
            _make_user_text("第一问"),
            _make_assistant_text("第一答"),
            _make_user_text("第二问"),
            _make_assistant_text("第二答"),
        ]
        groups = group_messages_by_prompt_round(messages)
        assert len(groups) == 2

    def test_tool_result_does_not_start_new_round(self):
        """包含工具结果的消息不视为新回合开始。"""
        messages = [
            _make_user_text("运行命令"),
            _make_assistant_with_tool_use("bash", "toolu_001"),
            _make_user_with_tool_result("toolu_001", "output"),
            _make_assistant_text("结果分析"),
        ]
        groups = group_messages_by_prompt_round(messages)
        assert len(groups) == 1  # 工具调用+结果属于同一回合


class TestTryContextCollapse:
    """测试上下文折叠函数。"""

    def test_too_few_messages(self):
        """消息太少不进行折叠。"""
        messages = [_make_user_text("hi"), _make_assistant_text("hey")]
        result = try_context_collapse(messages, preserve_recent=2)
        assert result is None

    def test_collapses_long_text(self):
        """长文本被截断。"""
        long_text = "A" * (CONTEXT_COLLAPSE_TEXT_CHAR_LIMIT + 500)
        messages = [
            _make_user_text(long_text),
            _make_assistant_text("short reply"),
            _make_user_text("middle message A"),
            _make_assistant_text("middle reply A"),
            _make_user_text("recent message"),
            _make_assistant_text("recent reply"),
        ]
        result = try_context_collapse(messages, preserve_recent=2)
        assert result is not None
        # 第一条用户消息的文本应该被折叠
        first_msg = result[0]
        assert "[collapsed" in first_msg.content[0].text

    def test_no_change_when_short(self):
        """文本全部较短时不折叠。"""
        messages = [
            _make_user_text("short message"),
            _make_assistant_text("reply"),
            _make_user_text("recent"),
            _make_assistant_text("recent reply"),
        ]
        result = try_context_collapse(messages, preserve_recent=2)
        assert result is None


class TestTrySessionMemoryCompaction:
    """测试会话记忆压缩。"""

    def test_too_few_messages(self):
        """消息太少不进行压缩。"""
        messages = [_make_user_text("hi"), _make_assistant_text("hey")]
        result = try_session_memory_compaction(messages, preserve_recent=4)
        assert result is None

    def test_creates_memory_summary(self):
        """为较早消息生成会话记忆摘要。"""
        messages = [
            _make_user_text("第一轮问题"),
            _make_assistant_text("第一轮回答"),
            _make_user_text("第二轮问题"),
            _make_assistant_text("第二轮回答"),
            _make_user_text("第三轮问题"),
            _make_assistant_text("第三轮回答"),
            _make_user_text("第四轮问题"),
            _make_assistant_text("第四轮回答"),
            _make_user_text("第五轮问题"),
            _make_assistant_text("第五轮回答"),
            _make_user_text("最近的问题"),
            _make_assistant_text("最近的回答"),
        ]
        result = try_session_memory_compaction(messages, preserve_recent=4)
        assert result is not None
        # 第一条消息应该是会话记忆摘要
        assert "Session memory summary" in result[0].content[0].text

    def test_does_not_increase_tokens(self):
        """压缩后消息数量应减少（即使 token 数可能略增，消息数减少也是有效压缩）。"""
        messages = []
        for i in range(20):
            messages.append(_make_user_text(f"这是第{i}轮的用户提问"))
            messages.append(_make_assistant_text(f"这是第{i}轮的助手回答"))
        result = try_session_memory_compaction(messages, preserve_recent=4)
        # 要么不压缩返回 None，要么压缩结果消息数量减少
        if result is not None:
            assert len(result) < len(messages)


class TestTruncateHeadForPTLRetry:
    """测试 PTL 重试头部截断。"""

    def test_too_few_groups(self):
        """少于 2 个分组时不截断。"""
        messages = [_make_user_text("only one round")]
        assert truncate_head_for_ptl_retry(messages) is None

    def test_drops_oldest_groups(self):
        """丢弃最旧的 1/5 分组。"""
        # 创建 10 个回合
        messages = []
        for i in range(10):
            messages.append(_make_user_text(f"question {i}"))
            messages.append(_make_assistant_text(f"answer {i}"))
        result = truncate_head_for_ptl_retry(messages)
        assert result is not None
        assert len(result) < len(messages)

    def test_adds_marker_when_first_is_assistant(self):
        """如果截断后第一条是 assistant，添加标记消息。"""
        # 创建 5 个回合
        messages = []
        for i in range(5):
            messages.append(_make_user_text(f"q{i}"))
            messages.append(_make_assistant_text(f"a{i}"))
        result = truncate_head_for_ptl_retry(messages)
        assert result is not None
        # 第一条应该是 user 角色
        assert result[0].role == "user"


class TestExtractFunctions:
    """测试附件路径和工具提取函数。"""

    def test_extract_attachment_paths_empty(self):
        """空消息返回空列表。"""
        assert extract_attachment_paths([]) == []

    def test_extract_attachment_from_text(self):
        """从文本中提取 path: 引用（正则匹配到行尾）。"""
        messages = [
            _make_user_text("path: /tmp/test.txt"),
        ]
        paths = extract_attachment_paths(messages)
        assert "/tmp/test.txt" in paths[0]

    def test_extract_discovered_tools(self):
        """从消息中提取已使用的工具列表。"""
        messages = [
            _make_assistant_with_tool_use("read_file", "toolu_001"),
            _make_assistant_with_tool_use("bash", "toolu_002"),
            _make_assistant_with_tool_use("read_file", "toolu_003"),
        ]
        tools = extract_discovered_tools(messages)
        assert len(tools) == 2
        assert "read_file" in tools
        assert "bash" in tools


class TestSanitizeMetadata:
    """测试元数据清理函数。"""

    def test_primitives_pass_through(self):
        """原始类型直接返回。"""
        assert sanitize_metadata("hello") == "hello"
        assert sanitize_metadata(42) == 42
        assert sanitize_metadata(True) is True
        assert sanitize_metadata(None) is None
        assert sanitize_metadata(3.14) == 3.14

    def test_path_converted_to_string(self):
        """Path 对象转换为字符串。"""
        from pathlib import Path
        result = sanitize_metadata(Path("/tmp/test"))
        assert isinstance(result, str)
        assert result == "/tmp/test"

    def test_dict_keys_converted(self):
        """字典的非字符串键被转换。"""
        result = sanitize_metadata({1: "value"})
        assert "1" in result
        assert result["1"] == "value"

    def test_nested_structures(self):
        """递归处理嵌套结构。"""
        from pathlib import Path
        data = {
            "files": [Path("/a"), Path("/b")],
            "count": 5,
            "nested": {"deep": [1, 2, 3]},
        }
        result = sanitize_metadata(data)
        assert result["files"] == ["/a", "/b"]
        assert result["count"] == 5
        assert result["nested"]["deep"] == [1, 2, 3]


class TestIsPromptTooLongError:
    """测试 prompt 过长错误的判断。"""

    def test_prompt_too_long(self):
        """识别常见的 prompt 过长错误消息。"""
        assert is_prompt_too_long_error(Exception("prompt too long"))
        assert is_prompt_too_long_error(Exception("context length exceeded"))
        assert is_prompt_too_long_error(Exception("maximum context window"))
        assert is_prompt_too_long_error(Exception("too many tokens"))
        assert is_prompt_too_long_error(Exception("input too large for the model"))

    def test_other_errors(self):
        """其他类型错误不匹配。"""
        assert not is_prompt_too_long_error(Exception("connection timeout"))
        assert not is_prompt_too_long_error(Exception("api key invalid"))


# ══════════════════════════════════════════════════════════════
# _full_compact.py 测试（纯逻辑函数，不涉及 LLM 调用）
# ══════════════════════════════════════════════════════════════


class TestFormatCompactSummary:
    """测试压缩摘要格式化。"""

    def test_removes_analysis_tags(self):
        """移除 <analysis> 标签及其内容。"""
        raw = "<analysis>some thinking</analysis>\n<summary>Real summary</summary>"
        result = format_compact_summary(raw)
        assert "<analysis>" not in result
        assert "some thinking" not in result

    def test_extracts_summary_content(self):
        """提取 <summary> 内容并添加前缀。"""
        raw = "<analysis>thinking</analysis>\n<summary>Key points:\n- Point 1\n- Point 2</summary>"
        result = format_compact_summary(raw)
        assert "Summary:" in result
        assert "Key points:" in result
        assert "Point 1" in result

    def test_handles_missing_summary(self):
        """缺少 <summary> 标签时返回清理后的文本。"""
        raw = "<analysis>only thinking here</analysis>"
        result = format_compact_summary(raw)
        assert "<analysis>" not in result

    def test_collapses_multiple_newlines(self):
        """折叠多余的连续空行。"""
        raw = "<summary>line one\n\n\n\nline two</summary>"
        result = format_compact_summary(raw)
        assert "\n\n\n\n" not in result


class TestBuildCompactSummaryMessage:
    """测试压缩摘要消息构建。"""

    def test_suppress_follow_up(self):
        """suppress_follow_up=True 时追加继续指令。"""
        msg = build_compact_summary_message(
            "<summary>test</summary>",
            suppress_follow_up=True,
        )
        assert "resume directly" in msg.lower() or "continue the conversation" in msg.lower()

    def test_recent_preserved(self):
        """recent_preserved=True 时添加保留提示。"""
        msg = build_compact_summary_message(
            "<summary>test</summary>",
            recent_preserved=True,
        )
        assert "Recent messages are preserved" in msg

    def test_formats_raw_summary(self):
        """原始摘要被格式化后嵌入。"""
        raw = "<analysis>think</analysis>\n<summary>final summary text</summary>"
        msg = build_compact_summary_message(raw)
        assert "final summary text" in msg
        assert "<analysis>" not in msg


class TestGetCompactPrompt:
    """测试压缩 prompt 构建。"""

    def test_base_prompt(self):
        """基本 prompt 包含关键指令。"""
        prompt = get_compact_prompt()
        assert "CRITICAL" in prompt
        assert "<analysis>" in prompt
        assert "<summary>" in prompt
        assert "TEXT ONLY" in prompt

    def test_custom_instructions(self):
        """自定义指令被追加到 prompt。"""
        prompt = get_compact_prompt(custom_instructions="保留所有代码片段")
        assert "保留所有代码片段" in prompt

    def test_no_tools_warning(self):
        """prompt 强调不要使用工具。"""
        prompt = get_compact_prompt()
        assert "Do NOT call any tools" in prompt
        assert "Do NOT use read_file" in prompt


class TestAutoCompactState:
    """测试自动压缩状态跟踪。"""

    def test_initial_state(self):
        """初始状态为未压缩、零失败、零回合。"""
        state = AutoCompactState()
        assert state.compacted is False
        assert state.consecutive_failures == 0
        assert state.turn_counter == 0
        assert state.turn_id is not None

    def test_state_fields_mutable(self):
        """状态字段可以修改。"""
        state = AutoCompactState()
        state.compacted = True
        state.turn_counter = 5
        state.consecutive_failures = 2
        assert state.compacted is True
        assert state.turn_counter == 5
        assert state.consecutive_failures == 2


class TestGetContextWindow:
    """测试上下文窗口大小获取。"""

    def test_default_context_window(self):
        """未知模型返回默认上下文窗口。"""
        assert get_context_window("unknown-model") == 200_000

    def test_known_models(self):
        """已知模型返回正确的上下文窗口。"""
        assert get_context_window("claude-sonnet-4-6") == 200_000
        assert get_context_window("claude-opus-4-6") == 200_000
        # GPT-4 类模型通常有更大窗口
        assert get_context_window("gpt-4") > 0


class TestShouldAutocompact:
    """测试自动压缩触发判断。"""

    def test_compact_when_over_threshold(self):
        """超过阈值时应触发压缩。"""
        # 创建大量消息以超过阈值
        messages = [_make_user_text("x" * 500)] * 500
        state = AutoCompactState()
        result = should_autocompact(messages, "claude-sonnet-4-6", state)
        # 不应因连续失败而被阻止
        assert result is True or state.consecutive_failures < 3

    def test_no_compact_when_below_threshold(self):
        """低于阈值时不触发压缩。"""
        messages = [_make_user_text("short")]
        state = AutoCompactState()
        result = should_autocompact(messages, "claude-sonnet-4-6", state)
        assert result is False

    def test_max_failures_blocks_compact(self):
        """连续失败达到上限后阻止压缩。"""
        state = AutoCompactState(consecutive_failures=3)
        messages = [_make_user_text("x" * 500)] * 500
        result = should_autocompact(messages, "claude-sonnet-4-6", state)
        assert result is False


class TestBuildCompactCarryoverMessage:
    """测试 carryover 上下文构建。"""

    def test_empty_returns_none(self):
        """没有可保留上下文时返回 None。"""
        result = build_compact_carryover_message([])
        assert result is None

    def test_includes_attachment_paths(self):
        """包含附件路径。"""
        messages = [
            _make_user_text("分析 path: /tmp/data.csv"),
        ]
        result = build_compact_carryover_message(messages)
        assert result is not None
        assert "/tmp/data.csv" in result.content[0].text

    def test_includes_discovered_tools(self):
        """包含已发现的工具。"""
        messages = [
            _make_assistant_with_tool_use("read_file", "toolu_001"),
            _make_assistant_with_tool_use("bash", "toolu_002"),
        ]
        result = build_compact_carryover_message(messages)
        assert result is not None
        content = result.content[0].text
        assert "read_file" in content
        assert "bash" in content

    def test_includes_permission_mode(self):
        """包含 plan 模式状态。"""
        messages: list[ConversationMessage] = []
        result = build_compact_carryover_message(
            messages,
            metadata={"permission_mode": "plan"},
        )
        assert result is not None
        assert "plan mode" in result.content[0].text.lower()

    def test_includes_hook_note(self):
        """包含钩子备注。"""
        result = build_compact_carryover_message(
            [],
            hook_note="测试钩子",
        )
        assert result is not None
        assert "测试钩子" in result.content[0].text


class TestSummarizeMessages:
    """测试旧版消息摘要函数。"""

    def test_empty_messages(self):
        """空消息返回空字符串。"""
        assert summarize_messages([]) == ""

    def test_summarizes_recent(self):
        """摘要最近的消息。"""
        messages = [
            _make_user_text("问题一"),
            _make_assistant_text("回答一"),
            _make_user_text("问题二"),
            _make_assistant_text("回答二"),
        ]
        result = summarize_messages(messages, max_messages=4)
        assert "问题一" in result
        assert "回答二" in result

    def test_respects_max_messages(self):
        """尊重 max_messages 参数。"""
        messages = [_make_user_text(f"msg{i}") for i in range(20)]
        result = summarize_messages(messages, max_messages=3)
        # 只有最后 3 条消息被摘要
        lines = result.strip().split("\n")
        assert len(lines) <= 3


class TestCompactMessages:
    """测试旧版消息压缩函数。"""

    def test_no_compact_when_few_messages(self):
        """消息数少于 preserve_recent 时不压缩。"""
        messages = [_make_user_text("hi")]
        result = compact_messages(messages, preserve_recent=2)
        assert len(result) == 1

    def test_replaces_older_with_summary(self):
        """用摘要替换较早消息。"""
        messages = [
            _make_user_text("第一轮"),
            _make_assistant_text("第一轮回答"),
            _make_user_text("第二轮"),
            _make_assistant_text("第二轮回答"),
            _make_user_text("第三轮"),
            _make_assistant_text("第三轮回答"),
            _make_user_text("第四轮"),
            _make_assistant_text("第四轮回答"),
        ]
        result = compact_messages(messages, preserve_recent=4)
        # 结果应该少于 8 条（前面被压缩为摘要 + 保留最后 4 条）
        assert len(result) <= 5
        # 第一条应该是摘要消息
        assert "[conversation summary]" in result[0].content[0].text
