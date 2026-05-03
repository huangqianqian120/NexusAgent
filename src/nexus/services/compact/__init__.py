"""对话压缩——微压缩与基于 LLM 的全量摘要。

忠实翻译自 Claude Code 的压缩系统：
- Microcompact：低成本清除旧工具结果以减少 token 数
- Full compact：调用 LLM 对较早消息生成结构化摘要
- Auto-compact：token 数超过阈值时自动触发压缩
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════
# 公共 API（仅导出外部消费者实际使用的符号）
# ══════════════════════════════════════════════════════════════

from nexus.services.compact._constants import CompactTrigger as CompactTrigger

from nexus.services.compact._helpers import (
    CompactProgressCallback as CompactProgressCallback,
    estimate_conversation_tokens as estimate_conversation_tokens,
    estimate_message_tokens as estimate_message_tokens,
    try_context_collapse as try_context_collapse,
    try_session_memory_compaction as try_session_memory_compaction,
)

from nexus.services.compact._microcompact import (
    microcompact_messages as microcompact_messages,
)

from nexus.services.compact._full_compact import (
    AutoCompactState as AutoCompactState,
    auto_compact_if_needed as auto_compact_if_needed,
    compact_conversation as compact_conversation,
    compact_messages as compact_messages,
    get_context_window as get_context_window,
    summarize_messages as summarize_messages,
)
