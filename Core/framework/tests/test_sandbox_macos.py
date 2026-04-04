"""Tests for macOS seatbelt sandbox backend."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from scientificstate.modules.sandbox.base import SandboxConfig
from scientificstate.modules.sandbox.macos import SeatbeltSandbox, generate_seatbelt_profile


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


def test_seatbelt_available_when_binary_found():
    with patch("shutil.which", return_value="/usr/bin/sandbox-exec"):
        assert SeatbeltSandbox().is_available() is True


def test_seatbelt_unavailable_when_binary_missing():
    with patch("shutil.which", return_value=None):
        assert SeatbeltSandbox().is_available() is False


# ── generate_seatbelt_profile ────────────────────────────────────────────────


def test_profile_contains_version():
    profile = generate_seatbelt_profile(_default_config())
    assert "(version 1)" in profile


def test_profile_deny_default():
    profile = generate_seatbelt_profile(_default_config())
    assert "(deny default)" in profile


def test_profile_read_paths():
    cfg = _default_config(read_paths=["/foo/bar"])
    profile = generate_seatbelt_profile(cfg)
    assert '(allow file-read* (subpath "/foo/bar"))' in profile


def test_profile_write_paths():
    cfg = _default_config(write_paths=["/out/dir"])
    profile = generate_seatbelt_profile(cfg)
    assert '(allow file-write* (subpath "/out/dir"))' in profile


def test_profile_network_denied():
    cfg = _default_config(network_allowed=False)
    profile = generate_seatbelt_profile(cfg)
    assert "(deny network*)" in profile


def test_profile_network_allowed():
    cfg = _default_config(network_allowed=True)
    profile = generate_seatbelt_profile(cfg)
    assert "(allow network*)" in profile


def test_profile_subprocess_denied():
    cfg = _default_config(subprocess_allowed=False)
    profile = generate_seatbelt_profile(cfg)
    assert "(deny process-fork)" in profile


def test_profile_subprocess_allowed():
    cfg = _default_config(subprocess_allowed=True)
    profile = generate_seatbelt_profile(cfg)
    assert "(allow process-fork)" in profile


def test_profile_tmp_always_allowed():
    profile = generate_seatbelt_profile(_default_config())
    assert '(subpath "/tmp")' in profile


def test_profile_multiple_read_paths():
    cfg = _default_config(read_paths=["/a", "/b", "/c"])
    profile = generate_seatbelt_profile(cfg)
    assert '(subpath "/a")' in profile
    assert '(subpath "/b")' in profile
    assert '(subpath "/c")' in profile


# ── execute (mocked) ────────────────────────────────────────────────────────


def test_execute_success():
    sb = SeatbeltSandbox()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "output"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result), \
         patch("tempfile.NamedTemporaryFile") as mock_tmpf:
        mock_tmpf.return_value.__enter__ = lambda s: MagicMock(name="/tmp/test.sb")
        mock_tmpf.return_value.__exit__ = lambda s, *a: None
        mock_tmpf.return_value.name = "/tmp/test.sb"
        mock_tmpf.return_value.write = MagicMock()

        with patch("pathlib.Path.unlink"):
            result = sb.execute(["echo", "hi"], _default_config(), "/tmp")
            assert result.exit_code == 0
            assert result.stdout == "output"


def test_execute_timeout():
    import subprocess

    sb = SeatbeltSandbox()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("sandbox-exec", 60)), \
         patch("tempfile.NamedTemporaryFile") as mock_tmpf, \
         patch("pathlib.Path.unlink"):
        mock_tmpf.return_value.__enter__ = lambda s: MagicMock(name="/tmp/t.sb")
        mock_tmpf.return_value.__exit__ = lambda s, *a: None
        mock_tmpf.return_value.name = "/tmp/t.sb"
        mock_tmpf.return_value.write = MagicMock()

        result = sb.execute(["long"], _default_config(max_cpu_seconds=60), "/tmp")
        assert result.exit_code == -1
        assert "timeout" in result.stderr
