"""平台检测和功能测试."""

import pytest
from nexus.platforms import (
    detect_platform,
    get_platform_capabilities,
)


class TestDetectPlatform:
    """detect_platform 函数测试."""

    def test_macos(self):
        result = detect_platform(system_name="Darwin")
        assert result == "macos"

    def test_linux(self):
        result = detect_platform(system_name="Linux")
        assert result == "linux"

    def test_windows(self):
        result = detect_platform(system_name="Windows")
        assert result == "windows"

    def test_wsl(self):
        result = detect_platform(system_name="Linux", release="microsoft-WSL2")
        assert result == "wsl"

    def test_wsl_by_env_wsl_distro(self):
        """通过 WSL_DISTRO_NAME 环境变量检测 WSL."""
        result = detect_platform(
            system_name="Linux",
            release="5.10.0",
            env={"WSL_DISTRO_NAME": "Ubuntu"},
        )
        assert result == "wsl"

    def test_wsl_by_env_wsl_interop(self):
        """通过 WSL_INTEROP 环境变量检测 WSL."""
        result = detect_platform(
            system_name="Linux",
            release="5.10.0",
            env={"WSL_INTEROP": "/run/WSL/1_interop"},
        )
        assert result == "wsl"

    def test_unknown(self):
        result = detect_platform(system_name="FreeBSD")
        assert result == "unknown"

    def test_case_insensitive_system_name(self):
        result = detect_platform(system_name="darwin")
        assert result == "macos"


class TestPlatformCapabilities:
    """get_platform_capabilities 函数测试."""

    def test_macos_capabilities(self):
        caps = get_platform_capabilities("macos")
        assert caps.name == "macos"
        assert caps.supports_posix_shell is True
        assert caps.supports_native_windows_shell is False
        assert caps.supports_tmux is True
        assert caps.supports_swarm_mailbox is True
        assert caps.supports_sandbox_runtime is True

    def test_linux_capabilities(self):
        caps = get_platform_capabilities("linux")
        assert caps.name == "linux"
        assert caps.supports_posix_shell is True
        assert caps.supports_tmux is True

    def test_wsl_capabilities(self):
        caps = get_platform_capabilities("wsl")
        assert caps.name == "wsl"
        assert caps.supports_posix_shell is True
        assert caps.supports_tmux is True

    def test_windows_capabilities(self):
        caps = get_platform_capabilities("windows")
        assert caps.name == "windows"
        assert caps.supports_posix_shell is False
        assert caps.supports_native_windows_shell is True
        assert caps.supports_tmux is False
        assert caps.supports_swarm_mailbox is False
        assert caps.supports_sandbox_runtime is False

    def test_unknown_capabilities(self):
        caps = get_platform_capabilities("unknown")
        assert caps.supports_posix_shell is False
        assert caps.supports_native_windows_shell is False
        assert caps.supports_tmux is False

    def test_default_uses_current_platform(self):
        """不传参数时使用当前平台."""
        caps = get_platform_capabilities()
        assert caps.name in ("macos", "linux", "windows", "wsl", "unknown")

    def test_capability_is_frozen_dataclass(self):
        caps = get_platform_capabilities("macos")
        with pytest.raises(Exception):
            caps.supports_posix_shell = False
