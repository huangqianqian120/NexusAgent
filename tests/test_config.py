"""Tests for configuration system."""

import pytest
from nexus.platforms import detect_platform, get_platform_capabilities, PlatformName


class TestPlatforms:
    """Test platform detection."""

    def test_detect_platform_macos(self):
        """Test platform detection on macOS."""
        result = detect_platform(system_name="Darwin")
        assert result == "macos"

    def test_detect_platform_linux(self):
        """Test platform detection on Linux."""
        result = detect_platform(system_name="Linux")
        assert result == "linux"

    def test_detect_platform_windows(self):
        """Test platform detection on Windows."""
        result = detect_platform(system_name="Windows")
        assert result == "windows"

    def test_platform_capabilities_posix(self):
        """Test POSIX platform capabilities."""
        caps = get_platform_capabilities("macos")
        assert caps.supports_posix_shell is True
        assert caps.supports_tmux is True
