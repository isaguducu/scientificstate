"""Tests for Windows AppContainer sandbox backend."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from scientificstate.modules.sandbox.base import SandboxConfig
from scientificstate.modules.sandbox.windows import AppContainerSandbox, _apply_job_limits


def _default_config(**overrides) -> SandboxConfig:
    defaults = dict(
        read_paths=[],
        write_paths=[],
        network_allowed=False,
        subprocess_allowed=False,
        max_cpu_seconds=60,
        max_memory_mb=1024,
    )
    defaults.update(overrides)
    return SandboxConfig(**defaults)


# ── is_available ─────────────────────────────────────────────────────────────


def test_windows_available_on_win32():
    with patch.object(sys, "platform", "win32"):
        assert AppContainerSandbox().is_available() is True


def test_windows_unavailable_on_darwin():
    with patch.object(sys, "platform", "darwin"):
        assert AppContainerSandbox().is_available() is False


def test_windows_unavailable_on_linux():
    with patch.object(sys, "platform", "linux"):
        assert AppContainerSandbox().is_available() is False


# ── _apply_job_limits ────────────────────────────────────────────────────────


def test_apply_job_limits_non_windows():
    """On non-Windows, _apply_job_limits returns False."""
    result = _apply_job_limits(12345, _default_config())
    if sys.platform != "win32":
        assert result is False


# ── execute (mocked) ────────────────────────────────────────────────────────


def test_execute_success_mock():
    sb = AppContainerSandbox()
    mock_proc = MagicMock()
    mock_proc.pid = 1234
    mock_proc.communicate.return_value = ("output", "")
    mock_proc.returncode = 0

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("scientificstate.modules.sandbox.windows._apply_job_limits", return_value=True):
        result = sb.execute(["echo", "hi"], _default_config(), "/tmp")
        assert result.exit_code == 0
        assert result.stdout == "output"


def test_execute_timeout_mock():
    import subprocess

    sb = AppContainerSandbox()
    mock_proc = MagicMock()
    mock_proc.pid = 1234
    mock_proc.communicate.side_effect = subprocess.TimeoutExpired("cmd", 60)
    mock_proc.kill = MagicMock()

    # After kill, communicate should succeed
    def kill_then_communicate(*a, **kw):
        mock_proc.communicate.side_effect = None
        mock_proc.communicate.return_value = ("", "")

    mock_proc.kill.side_effect = kill_then_communicate

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("scientificstate.modules.sandbox.windows._apply_job_limits", return_value=True):
        result = sb.execute(["long"], _default_config(max_cpu_seconds=60), "/tmp")
        assert result.exit_code == -1
        assert "timeout" in result.stderr


def test_execute_command_not_found():
    sb = AppContainerSandbox()
    with patch("subprocess.Popen", side_effect=FileNotFoundError):
        result = sb.execute(["nonexistent"], _default_config(), "/tmp")
        assert result.exit_code == -1
        assert "not found" in result.stderr


def test_name_property():
    sb = AppContainerSandbox()
    assert sb.name == "AppContainerSandbox"
