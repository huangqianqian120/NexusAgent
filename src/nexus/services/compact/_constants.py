"""Compaction 常量定义."""

from typing import Literal

COMPACTABLE_TOOLS: frozenset[str] = frozenset(
    {
        "read_file",
        "bash",
        "grep",
        "glob",
        "web_search",
        "web_fetch",
        "edit_file",
        "write_file",
    }
)

TIME_BASED_MC_CLEARED_MESSAGE = "[Old tool result content cleared]"

# 自动压缩阈值
AUTOCOMPACT_BUFFER_TOKENS = 13_000
MAX_OUTPUT_TOKENS_FOR_SUMMARY = 20_000
MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3
COMPACT_TIMEOUT_SECONDS = 25
MAX_COMPACT_STREAMING_RETRIES = 2
MAX_PTL_RETRIES = 3
SESSION_MEMORY_KEEP_RECENT = 12
SESSION_MEMORY_MAX_LINES = 48
SESSION_MEMORY_MAX_CHARS = 4_000
CONTEXT_COLLAPSE_TEXT_CHAR_LIMIT = 2_400
CONTEXT_COLLAPSE_HEAD_CHARS = 900
CONTEXT_COLLAPSE_TAIL_CHARS = 500
MAX_COMPACT_ATTACHMENTS = 6
MAX_DISCOVERED_TOOLS = 12

# 微压缩默认值
DEFAULT_KEEP_RECENT = 5
DEFAULT_GAP_THRESHOLD_MINUTES = 60

# Token 估算安全系数
TOKEN_ESTIMATION_PADDING = 4 / 3

# 默认上下文窗口大小
_DEFAULT_CONTEXT_WINDOW = 200_000
PTL_RETRY_MARKER = "[earlier conversation truncated for compaction retry]"
ERROR_MESSAGE_INCOMPLETE_RESPONSE = "Compaction interrupted before a complete summary was returned."

CompactTrigger = Literal["auto", "manual", "reactive"]
