"""Tests for Linux bubblewrap sandbox backend."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from scientificstate.modules.sandbox.base import SandboxConfig
from scientificstate.modules.sandbox.linux import BubblewrapSandbox


def _default_config(**overrides) -> SandboxConfig:
    defaults = dict(
        read_paths=["/data/input"],
        write_paths=["/data/output"],
        network_allowed=False,
        subprocess_allowed=False,
        max_cpu_seconds=60,
        max_memory_mb=1024,
    )
    defaults.update(overrides)
    return SandboxConfig(**defaults)


# ── is_available ─────────────────────────────────────────────────────────────


def test_bwrap_available_when_binary_found():
    with patch("shutil.which", return_value="/usr/bin/bwrap"):
        assert BubblewrapSandbox().is_available() is True


def test_bwrap_unavailable_when_binary_missing():
    with patch("shutil.which", return_value=None):
        assert BubblewrapSandbox().is_available() is False


# ── _build_args ──────────────────────────────────────────────────────────────


def test_build_args_pid_namespace_always_present():
    sb = BubblewrapSandbox()
    args = sb._build_args(["python", "run.py"], _default_config(), "/work")
    assert "--unshare-pid" in args


def test_build_args_network_isolated_by_default():
    sb = BubblewrapSandbox()
    args = sb._build_args(["cmd"], _default_config(network_allowed=False), "/w")
    assert "--unshare-net" in args


def test_build_args_network_allowed():
    sb = BubblewrapSandbox()
    args = sb._build_args(["cmd"], _default_config(network_allowed=True), "/w")
    assert "--unshare-net" not in args


def test_build_args_read_paths():
    sb = BubblewrapSandbox()
    cfg = _default_config(read_paths=["/a", "/b"])
    args = sb._build_args(["cmd"], cfg, "/w")
    assert "--ro-bind" in args
    idx = args.index("--ro-bind")
    assert args[idx + 1] == "/a"


def test_build_args_write_paths():
    sb = BubblewrapSandbox()
    cfg = _default_config(write_paths=["/out"])
    args = sb._build_args(["cmd"], cfg, "/w")
    assert "--bind" in args
    idx = args.index("--bind")
    assert args[idx + 1] == "/out"


def test_build_args_tmpfs():
    sb = BubblewrapSandbox()
    args = sb._build_args(["cmd"], _default_config(), "/w")
    assert "--tmpfs" in args
    idx = args.index("--tmpfs")
    assert args[idx + 1] == "/tmp"


def test_build_args_cwd():
    sb = BubblewrapSandbox()
    args = sb._build_args(["cmd"], _default_config(), "/my/dir")
    assert "--chdir" in args
    idx = args.index("--chdir")
    assert args[idx + 1] == "/my/dir"


def test_build_args_ipc_isolation_when_no_subprocess():
    sb = BubblewrapSandbox()
    args = sb._build_args(["cmd"], _default_config(subprocess_allowed=False), "/w")
    assert "--unshare-ipc" in args


def test_build_args_no_ipc_when_subprocess_allowed():
    sb = BubblewrapSandbox()
    args = sb._build_args(["cmd"], _default_config(subprocess_allowed=True), "/w")
    assert "--unshare-ipc" not in args


def test_build_args_command_after_separator():
    sb = BubblewrapSandbox()
    args = sb._build_args(["python", "-m", "module"], _default_config(), "/w")
    sep_idx = args.index("--")
    assert args[sep_idx + 1:] == ["python", "-m", "module"]


# ── execute (mocked) ────────────────────────────────────────────────────────


def test_execute_success():
    sb = BubblewrapSandbox()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "ok"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        result = sb.execute(["echo", "hi"], _default_config(), "/tmp")
        assert result.exit_code == 0
        assert result.stdout == "ok"


def test_execute_timeout():
    import subprocess

    sb = BubblewrapSandbox()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("bwrap", 60)):
        result = sb.execute(["long"], _default_config(max_cpu_seconds=60), "/tmp")
        assert result.exit_code == -1
        assert "timeout" in result.stderr


def test_execute_binary_not_found():
    sb = BubblewrapSandbox()
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = sb.execute(["cmd"], _default_config(), "/tmp")
        assert result.exit_code == -1
        assert "not found" in result.stderr
