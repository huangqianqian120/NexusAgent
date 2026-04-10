"""Unified authentication management for Nexus."""

from nexus.auth.flows import ApiKeyFlow, BrowserFlow, DeviceCodeFlow
from nexus.auth.manager import AuthManager
from nexus.auth.storage import (
    clear_provider_credentials,
    decrypt,
    encrypt,
    load_external_binding,
    load_credential,
    store_external_binding,
    store_credential,
)

__all__ = [
    "AuthManager",
    "ApiKeyFlow",
    "BrowserFlow",
    "DeviceCodeFlow",
    "store_credential",
    "load_credential",
    "store_external_binding",
    "load_external_binding",
    "clear_provider_credentials",
    "encrypt",
    "decrypt",
]
