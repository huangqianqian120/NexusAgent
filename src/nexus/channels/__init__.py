"""Nexus channels subsystem.

Provides a message-bus architecture for integrating chat platforms
(Telegram, Discord, Slack, etc.) with the Nexus query engine.

Usage::

    from nexus.channels import BaseChannel, ChannelManager, MessageBus
"""

from nexus.channels.bus.events import InboundMessage, OutboundMessage
from nexus.channels.bus.queue import MessageBus
from nexus.channels.impl.base import BaseChannel
from nexus.channels.impl.manager import ChannelManager

__all__ = [
    "BaseChannel",
    "ChannelManager",
    "InboundMessage",
    "MessageBus",
    "OutboundMessage",
]
