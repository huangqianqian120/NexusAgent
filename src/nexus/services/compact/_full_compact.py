"""Full compact：LLM 驱动的对话压缩、carryover 上下文构建、自动压缩调度。"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from nexus.engine.messages import ConversationMessage, TextBlock
from nexus.hooks import HookEvent, HookExecutor
from nexus.services.compact._constants import (
    AUTOCOMPACT_BUFFER_TOKENS,
    MAX_OUTPUT_TOKENS_FOR_SUMMARY,
    MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES,
    COMPACT_TIMEOUT_SECONDS,
    MAX_COMPACT_STREAMING_RETRIES,
    MAX_PTL_RETRIES,
    SESSION_MEMORY_KEEP_RECENT,
    DEFAULT_KEEP_RECENT,
    ERROR_MESSAGE_INCOMPLETE_RESPONSE,
    _DEFAULT_CONTEXT_WINDOW,
    CompactTrigger,
)
from nexus.services.compact._helpers import (
    estimate_message_tokens,
    record_compact_checkpoint,
    emit_progress,
    is_prompt_too_long_error,
    extract_attachment_paths,
    extract_discovered_tools,
    try_context_collapse,
    try_session_memory_compaction,
    truncate_head_for_ptl_retry,
    CompactProgressCallback,
)
from nexus.services.compact._microcompact import microcompact_messages

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Carryover 上下文构建
# ══════════════════════════════════════════════════════════════


def build_compact_carryover_message(
    messages: list[ConversationMessage],
    *,
    metadata: dict[str, Any] | None = None,
    hook_note: str | None = None,
) -> ConversationMessage | None:
    """保留压缩后应存活的轻量级运行时上下文。"""
    metadata = metadata or {}
    attachment_paths = extract_attachment_paths(messages)
    discovered_tools = extract_discovered_tools(messages)
    permission_mode = str(metadata.get("permission_mode") or "").strip().lower()
    read_file_state = metadata.get("read_file_state")
    invoked_skills = metadata.get("invoked_skills")
    async_agent_state = metadata.get("async_agent_state")
    compact_last = metadata.get("compact_last")

    lines: list[str] = []
    if permission_mode == "plan":
        lines.extend([
            "Plan mode is still active for this session.",
            "Do not execute mutating tools until the user exits plan mode.",
        ])
    if attachment_paths:
        lines.append("Recent local attachments to keep in mind:")
        lines.extend(f"- {path}" for path in attachment_paths)
    if discovered_tools:
        lines.append("Tools already discovered or used in this session:")
        lines.append("- " + ", ".join(discovered_tools))
    if isinstance(read_file_state, list) and read_file_state:
        lines.append("Recently read files to keep in working memory:")
        for entry in read_file_state[-4:]:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "").strip()
            span = str(entry.get("span") or "").strip()
            preview = str(entry.get("preview") or "").strip()
            if not path:
                continue
            bullet = f"- {path}"
            if span:
                bullet += f" ({span})"
            lines.append(bullet)
            if preview:
                lines.append(f"  Preview: {preview}")
    if isinstance(invoked_skills, list) and invoked_skills:
        lines.append("Skills invoked earlier in the session:")
        lines.append("- " + ", ".join(str(skill) for skill in invoked_skills[-8:]))
    if isinstance(async_agent_state, list) and async_agent_state:
        lines.append("Async agent / background task state:")
        lines.extend(f"- {entry}" for entry in async_agent_state[-6:])
    if isinstance(compact_last, dict) and compact_last:
        checkpoint = str(compact_last.get("checkpoint") or "").strip()
        token_count = compact_last.get("token_count")
        if checkpoint:
            if token_count is not None:
                lines.append(f"Last compact checkpoint: {checkpoint} (token_count={token_count})")
            else:
                lines.append(f"Last compact checkpoint: {checkpoint}")
    if hook_note:
        lines.append("Compact hook note:")
        lines.append(hook_note)

    if not lines:
        return None
    return ConversationMessage.from_user_text(
        "Carry-over context preserved after compaction:\n" + "\n".join(lines)
    )


# ══════════════════════════════════════════════════════════════
# 压缩 Prompt 构建
# ══════════════════════════════════════════════════════════════

NO_TOOLS_PREAMBLE = """\
CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.

- Do NOT use read_file, bash, grep, glob, edit_file, write_file, or ANY other tool.
- You already have all the context you need in the conversation above.
- Tool calls will be REJECTED and will waste your only turn — you will fail the task.
- Your entire response must be plain text: an <analysis> block followed by a <summary> block.

"""

BASE_COMPACT_PROMPT = """\
Your task is to create a detailed summary of the conversation so far. This summary will replace the earlier messages, so it must capture all important information.

First, draft your analysis inside <analysis> tags. Walk through the conversation chronologically and extract:
- Every user request and intent (explicit and implicit)
- The approach taken and technical decisions made
- Specific code, files, and configurations discussed (with paths and line numbers where available)
- All errors encountered and how they were fixed
- Any user feedback or corrections

Then, produce a structured summary inside <summary> tags with these sections:

1. **Primary Request and Intent**: All user requests in full detail, including nuances and constraints.
2. **Key Technical Concepts**: Technologies, frameworks, patterns, and conventions discussed.
3. **Files and Code Sections**: Every file examined or modified, with specific code snippets and line numbers.
4. **Errors and Fixes**: Every error encountered, its cause, and how it was resolved.
5. **Problem Solving**: Problems solved and approaches that worked vs. didn't work.
6. **All User Messages**: Non-tool-result user messages (preserve exact wording for context).
7. **Pending Tasks**: Explicitly requested work that hasn't been completed yet.
8. **Current Work**: Detailed description of the last task being worked on before compaction.
9. **Optional Next Step**: The single most logical next step, directly aligned with the user's recent request.
"""

NO_TOOLS_TRAILER = """
REMINDER: Do NOT call any tools. Respond with plain text only — an <analysis> block followed by a <summary> block. Tool calls will be rejected and you will fail the task."""


def get_compact_prompt(custom_instructions: str | None = None) -> str:
    """构建发送给模型的完整压缩 prompt。"""
    prompt = NO_TOOLS_PREAMBLE + BASE_COMPACT_PROMPT
    if custom_instructions and custom_instructions.strip():
        prompt += f"\n\nAdditional Instructions:\n{custom_instructions}"
    prompt += NO_TOOLS_TRAILER
    return prompt


def format_compact_summary(raw_summary: str) -> str:
    """移除 <analysis> 草稿区，提取 <summary> 内容。"""
    text = re.sub(r"<analysis>[\s\S]*?</analysis>", "", raw_summary)
    m = re.search(r"<summary>([\s\S]*?)</summary>", text)
    if m:
        text = text.replace(m.group(0), f"Summary:\n{m.group(1).strip()}")
    text = re.sub(r"\n\n+", "\n\n", text)
    return text.strip()


def build_compact_summary_message(
    summary: str,
    *,
    suppress_follow_up: bool = False,
    recent_preserved: bool = False,
) -> str:
    """创建替换压缩历史的消息文本。"""
    formatted = format_compact_summary(summary)
    text = (
        "This session is being continued from a previous conversation that ran "
        "out of context. The summary below covers the earlier portion of the "
        "conversation.\n\n"
        f"{formatted}"
    )
    if recent_preserved:
        text += "\n\nRecent messages are preserved verbatim."
    if suppress_follow_up:
        text += (
            "\nContinue the conversation from where it left off without asking "
            "the user any further questions. Resume directly — do not acknowledge "
            "the summary, do not recap what was happening, do not preface with "
            '"I\'ll continue" or similar. Pick up the last task as if the break '
            "never happened."
        )
    return text


# ══════════════════════════════════════════════════════════════
# 自动压缩状态与阈值
# ══════════════════════════════════════════════════════════════


@dataclass
class AutoCompactState:
    """跨查询循环回合持续的可变状态。"""
    compacted: bool = False
    turn_counter: int = 0
    turn_id: str = ""
    consecutive_failures: int = 0


def get_context_window(model: str) -> int:
    """返回模型的上下文窗口大小（保守默认值）。"""
    m = model.lower()
    if "opus" in m:
        return 200_000
    if "sonnet" in m:
        return 200_000
    if "haiku" in m:
        return 200_000
    return _DEFAULT_CONTEXT_WINDOW


def get_autocompact_threshold(model: str) -> int:
    """计算触发自动压缩的 token 阈值。"""
    context_window = get_context_window(model)
    reserved = min(MAX_OUTPUT_TOKENS_FOR_SUMMARY, 20_000)
    effective = context_window - reserved
    return effective - AUTOCOMPACT_BUFFER_TOKENS


def should_autocompact(
    messages: list[ConversationMessage],
    model: str,
    state: AutoCompactState,
) -> bool:
    """判断对话是否应触发自动压缩。"""
    if state.consecutive_failures >= MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES:
        return False
    token_count = estimate_message_tokens(messages)
    threshold = get_autocompact_threshold(model)
    return token_count >= threshold


# ══════════════════════════════════════════════════════════════
# Full Compact 执行（调用 LLM）
# ══════════════════════════════════════════════════════════════


async def compact_conversation(
    messages: list[ConversationMessage],
    *,
    api_client: Any,
    model: str,
    system_prompt: str = "",
    preserve_recent: int = 6,
    custom_instructions: str | None = None,
    suppress_follow_up: bool = True,
    trigger: CompactTrigger = "manual",
    progress_callback: CompactProgressCallback | None = None,
    emit_hooks_start: bool = True,
    hook_executor: HookExecutor | None = None,
    carryover_metadata: dict[str, Any] | None = None,
) -> list[ConversationMessage]:
    """通过 LLM 生成摘要来压缩对话。

    1. 先执行 microcompact（廉价 token 减少）。
    2. 分为旧消息（需要摘要）和近期消息（需要保留）。
    3. 调用 LLM 生成结构化摘要。
    4. 用摘要 + 保留的近期消息替换旧消息。
    """
    from nexus.api.client import ApiMessageRequest, ApiMessageCompleteEvent

    if len(messages) <= preserve_recent:
        return list(messages)

    # 步骤 1：microcompact 廉价减少 token
    messages, tokens_freed = microcompact_messages(messages, keep_recent=DEFAULT_KEEP_RECENT)

    pre_compact_tokens = estimate_message_tokens(messages)
    log.info("开始压缩对话：%d 条消息，约 %d tokens", len(messages), pre_compact_tokens)

    # 步骤 2：分为旧消息和新消息
    older = messages[:-preserve_recent]
    newer = messages[-preserve_recent:]

    # 步骤 3：构建压缩请求
    compact_prompt = get_compact_prompt(custom_instructions)
    compact_messages = list(older) + [ConversationMessage.from_user_text(compact_prompt)]
    attachment_paths = extract_attachment_paths(older)
    discovered_tools = extract_discovered_tools(older)
    hook_payload = {
        "event": HookEvent.PRE_COMPACT.value,
        "trigger": trigger,
        "model": model,
        "message_count": len(messages),
        "token_count": pre_compact_tokens,
        "preserve_recent": preserve_recent,
        "attachments": attachment_paths,
        "discovered_tools": discovered_tools,
        **(carryover_metadata or {}),
    }
    start_checkpoint = record_compact_checkpoint(
        carryover_metadata,
        checkpoint="compact_prepare",
        trigger=trigger,
        message_count=len(messages),
        token_count=pre_compact_tokens,
        details={
            "preserve_recent": preserve_recent,
            "attachments": attachment_paths,
            "discovered_tools": discovered_tools,
        },
    )

    if emit_hooks_start:
        await emit_progress(
            progress_callback,
            phase="hooks_start",
            trigger=trigger,
            message="准备对话压缩。",
            checkpoint="compact_hooks_start",
            metadata=start_checkpoint,
        )
    if hook_executor is not None:
        hook_result = await hook_executor.execute(HookEvent.PRE_COMPACT, hook_payload)
        if hook_result.blocked:
            reason = hook_result.reason or "pre-compact hook 阻止了压缩"
            failed_checkpoint = record_compact_checkpoint(
                carryover_metadata,
                checkpoint="compact_failed",
                trigger=trigger,
                message_count=len(messages),
                token_count=pre_compact_tokens,
                details={"reason": reason},
            )
            await emit_progress(
                progress_callback,
                phase="compact_failed",
                trigger=trigger,
                message=reason,
                checkpoint="compact_failed",
                metadata=failed_checkpoint,
            )
            return messages

    compact_start_checkpoint = record_compact_checkpoint(
        carryover_metadata,
        checkpoint="compact_start",
        trigger=trigger,
        message_count=len(messages),
        token_count=pre_compact_tokens,
        details={"preserve_recent": preserve_recent},
    )
    await emit_progress(
        progress_callback,
        phase="compact_start",
        trigger=trigger,
        message="压缩对话记忆中。",
        checkpoint="compact_start",
        metadata=compact_start_checkpoint,
    )

    summary_text = ""
    retry_messages = compact_messages
    ptl_retries = 0

    async def _collect_summary(summary_request_messages: list[ConversationMessage]) -> str:
        collected = ""
        stream = api_client.stream_message(
            ApiMessageRequest(
                model=model,
                messages=summary_request_messages,
                system_prompt=system_prompt or "You are a conversation summarizer.",
                max_tokens=MAX_OUTPUT_TOKENS_FOR_SUMMARY,
                tools=[],
            )
        )
        if inspect.isawaitable(stream):
            stream = await stream
        if not hasattr(stream, "__aiter__"):
            raise RuntimeError("压缩客户端未提供流式响应。")
        async for event in stream:
            if isinstance(event, ApiMessageCompleteEvent):
                collected = event.message.text
        if collected.strip():
            return collected
        raise RuntimeError(ERROR_MESSAGE_INCOMPLETE_RESPONSE)

    for attempt in range(1, MAX_COMPACT_STREAMING_RETRIES + 2):
        try:
            summary_text = await asyncio.wait_for(
                _collect_summary(retry_messages),
                timeout=COMPACT_TIMEOUT_SECONDS,
            )
            break
        except Exception as exc:
            if is_prompt_too_long_error(exc) and ptl_retries < MAX_PTL_RETRIES:
                truncated = truncate_head_for_ptl_retry(retry_messages[:-1])
                if truncated:
                    ptl_retries += 1
                    retry_messages = [*truncated, retry_messages[-1]]
                    await emit_progress(
                        progress_callback,
                        phase="compact_retry",
                        trigger=trigger,
                        message="压缩 prompt 过长；裁剪较早的上下文后重试。",
                        attempt=ptl_retries,
                        checkpoint="compact_retry_prompt_too_long",
                        metadata=record_compact_checkpoint(
                            carryover_metadata,
                            checkpoint="compact_retry_prompt_too_long",
                            trigger=trigger,
                            message_count=len(retry_messages),
                            token_count=estimate_message_tokens(retry_messages),
                            attempt=ptl_retries,
                            details={"ptl_retries": ptl_retries},
                        ),
                    )
                    continue
            if attempt > MAX_COMPACT_STREAMING_RETRIES:
                await emit_progress(
                    progress_callback,
                    phase="compact_failed",
                    trigger=trigger,
                    message=str(exc),
                    attempt=attempt,
                    checkpoint="compact_failed",
                    metadata=record_compact_checkpoint(
                        carryover_metadata,
                        checkpoint="compact_failed",
                        trigger=trigger,
                        message_count=len(retry_messages),
                        token_count=estimate_message_tokens(retry_messages),
                        attempt=attempt,
                        details={"reason": str(exc)},
                    ),
                )
                raise
            await emit_progress(
                progress_callback,
                phase="compact_retry",
                trigger=trigger,
                message=str(exc),
                attempt=attempt,
                checkpoint="compact_retry",
                metadata=record_compact_checkpoint(
                    carryover_metadata,
                    checkpoint="compact_retry",
                    trigger=trigger,
                    message_count=len(retry_messages),
                    token_count=estimate_message_tokens(retry_messages),
                    attempt=attempt,
                    details={"reason": str(exc)},
                ),
            )

    if not summary_text:
        await emit_progress(
            progress_callback,
            phase="compact_failed",
            trigger=trigger,
            message=ERROR_MESSAGE_INCOMPLETE_RESPONSE,
            checkpoint="compact_failed",
            metadata=record_compact_checkpoint(
                carryover_metadata,
                checkpoint="compact_failed",
                trigger=trigger,
                message_count=len(messages),
                token_count=pre_compact_tokens,
                details={"reason": ERROR_MESSAGE_INCOMPLETE_RESPONSE},
            ),
        )
        log.warning("压缩摘要为空——返回原始消息")
        return messages

    # 步骤 4：构建新消息列表
    summary_content = build_compact_summary_message(
        summary_text,
        suppress_follow_up=suppress_follow_up,
        recent_preserved=len(newer) > 0,
    )
    summary_msg = ConversationMessage.from_user_text(summary_content)
    carryover_msg = build_compact_carryover_message(older, metadata=carryover_metadata)

    result = [summary_msg]
    if carryover_msg is not None:
        result.append(carryover_msg)
    result.extend(newer)
    post_compact_tokens = estimate_message_tokens(result)

    # post-compact hook
    if hook_executor is not None:
        post_hook_result = await hook_executor.execute(
            HookEvent.POST_COMPACT,
            {
                "event": HookEvent.POST_COMPACT.value,
                "trigger": trigger,
                "model": model,
                "pre_compact_message_count": len(messages),
                "post_compact_message_count": len(result),
                "pre_compact_tokens": pre_compact_tokens,
                "post_compact_tokens": post_compact_tokens,
                "attachments": attachment_paths,
                "discovered_tools": discovered_tools,
                **(carryover_metadata or {}),
            },
        )
        hook_note = post_hook_result.reason or "\n".join(
            r.output.strip() for r in post_hook_result.results if r.output.strip()
        )
        if hook_note:
            carryover_msg = build_compact_carryover_message(
                older, metadata=carryover_metadata, hook_note=hook_note,
            )
            result = [summary_msg]
            if carryover_msg is not None:
                result.append(carryover_msg)
            result.extend(newer)
            post_compact_tokens = estimate_message_tokens(result)

    log.info(
        "压缩完成：%d -> %d 条消息，约 %d -> %d tokens（节省约 %d）",
        len(messages), len(result),
        pre_compact_tokens, post_compact_tokens,
        pre_compact_tokens - post_compact_tokens,
    )
    await emit_progress(
        progress_callback,
        phase="compact_end",
        trigger=trigger,
        message="对话压缩完成。",
        checkpoint="compact_end",
        metadata=record_compact_checkpoint(
            carryover_metadata,
            checkpoint="compact_end",
            trigger=trigger,
            message_count=len(result),
            token_count=post_compact_tokens,
            details={
                "pre_compact_message_count": len(messages),
                "post_compact_message_count": len(result),
                "pre_compact_tokens": pre_compact_tokens,
                "post_compact_tokens": post_compact_tokens,
                "tokens_saved": pre_compact_tokens - post_compact_tokens,
                "attachments": attachment_paths,
                "discovered_tools": discovered_tools,
            },
        ),
    )
    return result


# ══════════════════════════════════════════════════════════════
# 自动压缩（由 query loop 调用）
# ══════════════════════════════════════════════════════════════


async def auto_compact_if_needed(
    messages: list[ConversationMessage],
    *,
    api_client: Any,
    model: str,
    system_prompt: str = "",
    state: AutoCompactState,
    preserve_recent: int = 6,
    progress_callback: CompactProgressCallback | None = None,
    force: bool = False,
    trigger: CompactTrigger = "auto",
    hook_executor: HookExecutor | None = None,
    carryover_metadata: dict[str, Any] | None = None,
) -> tuple[list[ConversationMessage], bool]:
    """检查是否需要自动压缩，如需要则执行。

    在每个查询循环回合开始时调用。

    Returns:
        (messages, was_compacted) — 如果压缩了，messages 是新列表。
    """
    if not force and not should_autocompact(messages, model, state):
        return messages, False

    log.info("自动压缩触发 (failures=%d)", state.consecutive_failures)
    record_compact_checkpoint(
        carryover_metadata,
        checkpoint=f"query_{trigger}_triggered",
        trigger=trigger,
        message_count=len(messages),
        token_count=estimate_message_tokens(messages),
        details={"consecutive_failures": state.consecutive_failures},
    )

    # 先尝试 microcompact
    messages, tokens_freed = microcompact_messages(messages)
    record_compact_checkpoint(
        carryover_metadata,
        checkpoint="query_microcompact_end",
        trigger=trigger,
        message_count=len(messages),
        token_count=estimate_message_tokens(messages),
        details={"tokens_freed": tokens_freed},
    )
    if tokens_freed > 0 and not should_autocompact(messages, model, state):
        log.info("Microcompact 释放约 %d tokens，不再需要全量压缩", tokens_freed)
        return messages, True

    # 上下文折叠
    context_collapsed = try_context_collapse(messages, preserve_recent=preserve_recent)
    if context_collapsed is not None:
        await emit_progress(
            progress_callback,
            phase="context_collapse_start",
            trigger=trigger,
            message="全量压缩前先折叠过长上下文。",
            checkpoint="query_context_collapse_start",
            metadata=record_compact_checkpoint(
                carryover_metadata,
                checkpoint="query_context_collapse_start",
                trigger=trigger,
                message_count=len(messages),
                token_count=estimate_message_tokens(messages),
            ),
        )
        messages = context_collapsed
        await emit_progress(
            progress_callback,
            phase="context_collapse_end",
            trigger=trigger,
            message="上下文折叠完成。",
            checkpoint="query_context_collapse_end",
            metadata=record_compact_checkpoint(
                carryover_metadata,
                checkpoint="query_context_collapse_end",
                trigger=trigger,
                message_count=len(messages),
                token_count=estimate_message_tokens(messages),
            ),
        )
        if not force and not should_autocompact(messages, model, state):
            return messages, True

    # 会话记忆压缩
    session_memory = try_session_memory_compaction(
        messages, preserve_recent=max(preserve_recent, SESSION_MEMORY_KEEP_RECENT)
    )
    if session_memory is not None:
        await emit_progress(
            progress_callback,
            phase="session_memory_start",
            trigger=trigger,
            message="将较早对话浓缩为会话记忆。",
            checkpoint="query_session_memory_start",
            metadata=record_compact_checkpoint(
                carryover_metadata,
                checkpoint="query_session_memory_start",
                trigger=trigger,
                message_count=len(messages),
                token_count=estimate_message_tokens(messages),
            ),
        )
        await emit_progress(
            progress_callback,
            phase="session_memory_end",
            trigger=trigger,
            message="会话记忆浓缩完成。",
            checkpoint="query_session_memory_end",
            metadata=record_compact_checkpoint(
                carryover_metadata,
                checkpoint="query_session_memory_end",
                trigger=trigger,
                message_count=len(session_memory),
                token_count=estimate_message_tokens(session_memory),
            ),
        )
        state.compacted = True
        state.turn_counter += 1
        state.turn_id = uuid4().hex
        state.consecutive_failures = 0
        return session_memory, True

    # 需要全量压缩
    try:
        result = await compact_conversation(
            messages,
            api_client=api_client,
            model=model,
            system_prompt=system_prompt,
            preserve_recent=preserve_recent,
            suppress_follow_up=True,
            trigger=trigger,
            progress_callback=progress_callback,
            hook_executor=hook_executor,
            carryover_metadata=carryover_metadata,
        )
        state.compacted = True
        state.turn_counter += 1
        state.turn_id = uuid4().hex
        state.consecutive_failures = 0
        return result, True
    except Exception as exc:
        state.consecutive_failures += 1
        record_compact_checkpoint(
            carryover_metadata,
            checkpoint=f"query_{trigger}_failed",
            trigger=trigger,
            message_count=len(messages),
            token_count=estimate_message_tokens(messages),
            details={"reason": str(exc), "consecutive_failures": state.consecutive_failures},
        )
        log.error(
            "自动压缩失败 (attempt %d/%d): %s",
            state.consecutive_failures,
            MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES,
            exc,
        )
        return messages, False


# ══════════════════════════════════════════════════════════════
# 兼容旧版 API
# ══════════════════════════════════════════════════════════════


def summarize_messages(
    messages: list[ConversationMessage],
    *,
    max_messages: int = 8,
) -> str:
    """生成近期消息的紧凑文本摘要（兼容旧版）。"""
    selected = messages[-max_messages:]
    lines: list[str] = []
    for message in selected:
        text = message.text.strip()
        if not text:
            continue
        lines.append(f"{message.role}: {text[:300]}")
    return "\n".join(lines)


def compact_messages(
    messages: list[ConversationMessage],
    *,
    preserve_recent: int = 6,
) -> list[ConversationMessage]:
    """用合成摘要替换较早的对话历史（兼容旧版）。"""
    if len(messages) <= preserve_recent:
        return list(messages)
    older = messages[:-preserve_recent]
    newer = messages[-preserve_recent:]
    summary = summarize_messages(older)
    if not summary:
        return list(newer)
    return [
        ConversationMessage(
            role="user",
            content=[TextBlock(text=f"[conversation summary]\n{summary}")],
        ),
        *newer,
    ]
