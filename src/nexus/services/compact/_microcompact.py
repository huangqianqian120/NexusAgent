"""Microcompact：清除旧的工具结果以减少 token 数，无需 LLM 调用。"""

from __future__ import annotations

import logging

from nexus.engine.messages import (
    ConversationMessage,
    ContentBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from nexus.services.token_estimation import estimate_tokens
from nexus.services.compact._constants import (
    COMPACTABLE_TOOLS,
    TIME_BASED_MC_CLEARED_MESSAGE,
    DEFAULT_KEEP_RECENT,
)

log = logging.getLogger(__name__)


def _collect_compactable_tool_ids(messages: list[ConversationMessage]) -> list[str]:
    """遍历消息收集可被压缩的工具调用 ID。"""
    ids: list[str] = []
    for msg in messages:
        if msg.role != "assistant":
            continue
        for block in msg.content:
            if isinstance(block, ToolUseBlock) and block.name in COMPACTABLE_TOOLS:
                ids.append(block.id)
    return ids


def microcompact_messages(
    messages: list[ConversationMessage],
    *,
    keep_recent: int = DEFAULT_KEEP_RECENT,
) -> tuple[list[ConversationMessage], int]:
    """清除旧的工具结果，保留最近 *keep_recent* 个。

    这是廉价的第一道压缩——无需 LLM 调用。工具结果内容被替换为
    :data:`TIME_BASED_MC_CLEARED_MESSAGE`。

    Returns:
        (messages, tokens_saved) — messages 原地修改以提高效率。
    """
    keep_recent = max(1, keep_recent)
    all_ids = _collect_compactable_tool_ids(messages)

    if len(all_ids) <= keep_recent:
        return messages, 0

    keep_set = set(all_ids[-keep_recent:])
    clear_set = set(all_ids) - keep_set

    tokens_saved = 0
    for msg in messages:
        if msg.role != "user":
            continue
        new_content: list[ContentBlock] = []
        for block in msg.content:
            if (
                isinstance(block, ToolResultBlock)
                and block.tool_use_id in clear_set
                and block.content != TIME_BASED_MC_CLEARED_MESSAGE
            ):
                tokens_saved += estimate_tokens(block.content)
                new_content.append(
                    ToolResultBlock(
                        tool_use_id=block.tool_use_id,
                        content=TIME_BASED_MC_CLEARED_MESSAGE,
                        is_error=block.is_error,
                    )
                )
            else:
                new_content.append(block)
        msg.content = new_content

    if tokens_saved > 0:
        log.info("Microcompact 清除了 %d 个工具结果，节省约 %d tokens", len(clear_set), tokens_saved)

    return messages, tokens_saved
