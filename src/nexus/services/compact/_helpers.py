"""Compaction 辅助函数：token 估算、元数据处理、进度发送、消息分组、上下文折叠."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Awaitable

from nexus.engine.messages import (
    ConversationMessage,
    ContentBlock,
    ImageBlock,
    TextBlock,
    ToolResultBlock,
)
from nexus.engine.stream_events import CompactProgressEvent
from nexus.services.token_estimation import estimate_tokens
from nexus.services.compact._constants import (
    CONTEXT_COLLAPSE_TEXT_CHAR_LIMIT,
    CONTEXT_COLLAPSE_HEAD_CHARS,
    CONTEXT_COLLAPSE_TAIL_CHARS,
    MAX_COMPACT_ATTACHMENTS,
    MAX_DISCOVERED_TOOLS,
    SESSION_MEMORY_MAX_LINES,
    SESSION_MEMORY_MAX_CHARS,
    TOKEN_ESTIMATION_PADDING,
    CompactTrigger,
)

CompactProgressCallback = Callable[[CompactProgressEvent], Awaitable[None]]


# ══════════════════════════════════════════════════════════════
# Token 估算
# ══════════════════════════════════════════════════════════════


def estimate_message_tokens(messages: list[ConversationMessage]) -> int:
    """估算对话的总 token 数，包含 4/3 安全系数。"""
    total = 0
    for msg in messages:
        for block in msg.content:
            if isinstance(block, TextBlock):
                total += estimate_tokens(block.text)
            elif isinstance(block, ToolResultBlock):
                total += estimate_tokens(block.content)
            elif hasattr(block, 'name') and hasattr(block, 'input'):
                total += estimate_tokens(block.name)
                total += estimate_tokens(str(block.input))
    return int(total * TOKEN_ESTIMATION_PADDING)


def estimate_conversation_tokens(messages: list[ConversationMessage]) -> int:
    """向后兼容的别名。"""
    return estimate_message_tokens(messages)


# ══════════════════════════════════════════════════════════════
# 元数据处理
# ══════════════════════════════════════════════════════════════


def sanitize_metadata(value: Any) -> Any:
    """递归清理元数据使其可 JSON 序列化。"""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): sanitize_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_metadata(item) for item in value]
    return str(value)


def record_compact_checkpoint(
    carryover_metadata: dict[str, Any] | None,
    *,
    checkpoint: str,
    trigger: CompactTrigger,
    message_count: int,
    token_count: int,
    attempt: int | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """记录压缩检查点到 carryover metadata 中。"""
    payload: dict[str, Any] = {
        "checkpoint": checkpoint,
        "trigger": trigger,
        "message_count": message_count,
        "token_count": token_count,
    }
    if attempt is not None:
        payload["attempt"] = attempt
    if details:
        payload.update(sanitize_metadata(details))
    if carryover_metadata is not None:
        checkpoints = carryover_metadata.setdefault("compact_checkpoints", [])
        if isinstance(checkpoints, list):
            checkpoints.append(payload)
        carryover_metadata["compact_last"] = payload
    return payload


# ══════════════════════════════════════════════════════════════
# 进度发送
# ══════════════════════════════════════════════════════════════


async def emit_progress(
    callback: CompactProgressCallback | None,
    *,
    phase: str,
    trigger: CompactTrigger,
    message: str | None = None,
    attempt: int | None = None,
    checkpoint: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """向回调发送压缩进度事件。"""
    if callback is None:
        return
    await callback(
        CompactProgressEvent(
            phase=phase,
            trigger=trigger,
            message=message,
            attempt=attempt,
            checkpoint=checkpoint,
            metadata=sanitize_metadata(metadata) if metadata else None,
        )
    )


# ══════════════════════════════════════════════════════════════
# 错误检测
# ══════════════════════════════════════════════════════════════


def is_prompt_too_long_error(exc: Exception) -> bool:
    """判断异常是否由 prompt 过长导致。"""
    text = str(exc).lower()
    return any(
        needle in text
        for needle in (
            "prompt too long",
            "context length",
            "maximum context",
            "context window",
            "too many tokens",
            "too large for the model",
        )
    )


# ══════════════════════════════════════════════════════════════
# 消息分组
# ══════════════════════════════════════════════════════════════


def group_messages_by_prompt_round(
    messages: list[ConversationMessage],
) -> list[list[ConversationMessage]]:
    """按 prompt 回合将消息分组。"""
    groups: list[list[ConversationMessage]] = []
    current: list[ConversationMessage] = []
    for message in messages:
        starts_new_round = (
            message.role == "user"
            and not any(isinstance(block, ToolResultBlock) for block in message.content)
            and bool(message.text.strip())
        )
        if starts_new_round and current:
            groups.append(current)
            current = []
        current.append(message)
    if current:
        groups.append(current)
    return groups


# ══════════════════════════════════════════════════════════════
# 上下文折叠
# ══════════════════════════════════════════════════════════════


def _collapse_text(text: str) -> str:
    """截断过长文本，保留头尾。"""
    if len(text) <= CONTEXT_COLLAPSE_TEXT_CHAR_LIMIT:
        return text
    omitted = len(text) - CONTEXT_COLLAPSE_HEAD_CHARS - CONTEXT_COLLAPSE_TAIL_CHARS
    head = text[:CONTEXT_COLLAPSE_HEAD_CHARS].rstrip()
    tail = text[-CONTEXT_COLLAPSE_TAIL_CHARS:].lstrip()
    return f"{head}\n...[collapsed {omitted} chars]...\n{tail}"


def try_context_collapse(
    messages: list[ConversationMessage],
    *,
    preserve_recent: int,
) -> list[ConversationMessage] | None:
    """在全量压缩前，确定性缩小过大的文本块。"""
    if len(messages) <= preserve_recent + 2:
        return None

    older = messages[:-preserve_recent]
    newer = messages[-preserve_recent:]
    changed = False
    collapsed_older: list[ConversationMessage] = []
    for message in older:
        new_blocks: list[ContentBlock] = []
        for block in message.content:
            if isinstance(block, TextBlock):
                collapsed = _collapse_text(block.text)
                if collapsed != block.text:
                    changed = True
                new_blocks.append(TextBlock(text=collapsed))
            else:
                new_blocks.append(block)
        collapsed_older.append(ConversationMessage(role=message.role, content=new_blocks))

    if not changed:
        return None

    result = [*collapsed_older, *newer]
    if estimate_message_tokens(result) >= estimate_message_tokens(messages):
        return None
    return result


def truncate_head_for_ptl_retry(
    messages: list[ConversationMessage],
) -> list[ConversationMessage] | None:
    """当压缩请求本身过大时，丢弃最旧的 prompt 回合。"""
    from nexus.services.compact._constants import PTL_RETRY_MARKER

    groups = group_messages_by_prompt_round(messages)
    if len(groups) < 2:
        return None

    drop_count = max(1, len(groups) // 5)
    drop_count = min(drop_count, len(groups) - 1)
    retained = [message for group in groups[drop_count:] for message in group]
    if not retained:
        return None
    if retained[0].role == "assistant":
        return [ConversationMessage.from_user_text(PTL_RETRY_MARKER), *retained]
    return retained


# ══════════════════════════════════════════════════════════════
# 附件和工具提取
# ══════════════════════════════════════════════════════════════


def extract_attachment_paths(messages: list[ConversationMessage]) -> list[str]:
    """从消息中提取附件路径。"""
    found: list[str] = []
    seen: set[str] = set()
    path_pattern = re.compile(r"path:\s*([^)\\n]+)")
    attachment_pattern = re.compile(r"\[attachment:\s*([^\]]+)\]")
    for message in messages:
        for block in message.content:
            if isinstance(block, ImageBlock) and block.source_path:
                path = str(Path(block.source_path).expanduser())
                if path not in seen:
                    seen.add(path)
                    found.append(path)
            elif isinstance(block, TextBlock):
                for match in path_pattern.findall(block.text):
                    path = match.strip()
                    if path and path not in seen:
                        seen.add(path)
                        found.append(path)
                for match in attachment_pattern.findall(block.text):
                    path = match.strip()
                    if path and "download failed" not in path and path not in seen:
                        seen.add(path)
                        found.append(path)
            if len(found) >= MAX_COMPACT_ATTACHMENTS:
                return found
    return found


def extract_discovered_tools(messages: list[ConversationMessage]) -> list[str]:
    """从消息中提取已发现的工具列表。"""
    discovered: list[str] = []
    seen: set[str] = set()
    for message in messages:
        for tool_use in message.tool_uses:
            if tool_use.name and tool_use.name not in seen:
                seen.add(tool_use.name)
                discovered.append(tool_use.name)
            if len(discovered) >= MAX_DISCOVERED_TOOLS:
                return discovered
    return discovered


# ══════════════════════════════════════════════════════════════
# Session Memory
# ══════════════════════════════════════════════════════════════


def _summarize_message_for_memory(message: ConversationMessage) -> str:
    """为会话记忆生成单条消息摘要。"""
    text = " ".join(message.text.split())
    if text:
        text = text[:160]
        return f"{message.role}: {text}"
    tool_uses = [block.name for block in message.tool_uses]
    if tool_uses:
        return f"{message.role}: tool calls -> {', '.join(tool_uses[:4])}"
    if any(isinstance(block, ToolResultBlock) for block in message.content):
        return f"{message.role}: tool results returned"
    return f"{message.role}: [non-text content]"


def _build_session_memory_message(messages: list[ConversationMessage]) -> ConversationMessage | None:
    """将会话历史压缩为轻量级会话记忆消息。"""
    lines: list[str] = []
    total_chars = 0
    for message in messages:
        line = _summarize_message_for_memory(message)
        if not line:
            continue
        projected = total_chars + len(line) + 1
        if lines and (len(lines) >= SESSION_MEMORY_MAX_LINES or projected >= SESSION_MEMORY_MAX_CHARS):
            lines.append("... earlier context condensed ...")
            break
        lines.append(line)
        total_chars = projected
    if not lines:
        return None
    body = "\n".join(lines)
    return ConversationMessage.from_user_text(
        "Session memory summary from earlier in this conversation:\n" + body
    )


def try_session_memory_compaction(
    messages: list[ConversationMessage],
    *,
    preserve_recent: int = 12,
) -> list[ConversationMessage] | None:
    """在全量 LLM 压缩前，进行轻量级确定性压缩。"""
    if len(messages) <= preserve_recent + 4:
        return None
    older = messages[:-preserve_recent]
    newer = messages[-preserve_recent:]
    summary_message = _build_session_memory_message(older)
    if summary_message is None:
        return None
    result = [summary_message, *newer]
    if (
        estimate_message_tokens(result) >= estimate_message_tokens(messages)
        and len(result) >= len(messages)
    ):
        return None
    return result
