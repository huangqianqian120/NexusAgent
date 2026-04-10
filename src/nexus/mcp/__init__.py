"""MCP exports."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from nexus.mcp.client import McpClientManager, McpServerNotConnectedError
    from nexus.mcp.types import (
        McpConnectionStatus,
        McpHttpServerConfig,
        McpJsonConfig,
        McpResourceInfo,
        McpServerConfig,
        McpStdioServerConfig,
        McpToolInfo,
        McpWebSocketServerConfig,
    )

__all__ = [
    "McpClientManager",
    "McpConnectionStatus",
    "McpServerNotConnectedError",
    "McpHttpServerConfig",
    "McpJsonConfig",
    "McpResourceInfo",
    "McpServerConfig",
    "McpStdioServerConfig",
    "McpToolInfo",
    "McpWebSocketServerConfig",
    "load_mcp_server_configs",
]


def __getattr__(name: str):
    if name == "McpClientManager":
        from nexus.mcp.client import McpClientManager

        return McpClientManager
    if name == "McpServerNotConnectedError":
        from nexus.mcp.client import McpServerNotConnectedError

        return McpServerNotConnectedError
    if name == "load_mcp_server_configs":
        from nexus.mcp.config import load_mcp_server_configs

        return load_mcp_server_configs
    if name in {
        "McpConnectionStatus",
        "McpHttpServerConfig",
        "McpJsonConfig",
        "McpResourceInfo",
        "McpServerConfig",
        "McpStdioServerConfig",
        "McpToolInfo",
        "McpWebSocketServerConfig",
    }:
        from nexus.mcp.types import (
            McpConnectionStatus,
            McpHttpServerConfig,
            McpJsonConfig,
            McpResourceInfo,
            McpServerConfig,
            McpStdioServerConfig,
            McpToolInfo,
            McpWebSocketServerConfig,
        )

        return {
            "McpConnectionStatus": McpConnectionStatus,
            "McpHttpServerConfig": McpHttpServerConfig,
            "McpJsonConfig": McpJsonConfig,
            "McpResourceInfo": McpResourceInfo,
            "McpServerConfig": McpServerConfig,
            "McpStdioServerConfig": McpStdioServerConfig,
            "McpToolInfo": McpToolInfo,
            "McpWebSocketServerConfig": McpWebSocketServerConfig,
        }[name]
    raise AttributeError(name)
