"""Configuration system for Nexus.

Provides settings management, path resolution, and API key handling.
"""

from nexus.config.paths import (
    get_config_dir,
    get_config_file_path,
    get_data_dir,
    get_logs_dir,
)
from nexus.config.settings import (
    ProviderProfile,
    Settings,
    auth_source_provider_name,
    default_auth_source_for_provider,
    default_provider_profiles,
    load_settings,
    save_settings,
)

__all__ = [
    "ProviderProfile",
    "Settings",
    "auth_source_provider_name",
    "default_auth_source_for_provider",
    "default_provider_profiles",
    "get_config_dir",
    "get_config_file_path",
    "get_data_dir",
    "get_logs_dir",
    "load_settings",
    "save_settings",
]
