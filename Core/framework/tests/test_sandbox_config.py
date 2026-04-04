"""Tests for permission manifest to SandboxConfig transformation."""
from __future__ import annotations

from scientificstate.modules.sandbox.base import SandboxConfig
from scientificstate.modules.sandbox.config import sandbox_config_from_permission


# ── Basic transformation ────────────────────────────────────────────────────


def test_empty_permission_returns_defaults():
    config = sandbox_config_from_permission({})
    assert config.read_paths == []
    assert config.write_paths == []
    assert config.network_allowed is False
    assert config.subprocess_allowed is False
    assert config.max_cpu_seconds == 300
    assert config.max_memory_mb == 2048


def test_full_permission():
    perm = {
        "network": True,
        "filesystem_read": ["/data/input"],
        "filesystem_write": ["/data/output"],
        "subprocess_spawn": True,
        "max_memory_mb": 4096,
        "max_cpu_seconds": 600,
    }
    config = sandbox_config_from_permission(perm)
    assert config.network_allowed is True
    assert config.subprocess_allowed is True
    assert config.read_paths == ["/data/input"]
    assert config.write_paths == ["/data/output"]
    assert config.max_memory_mb == 4096
    assert config.max_cpu_seconds == 600


def test_network_false():
    config = sandbox_config_from_permission({"network": False})
    assert config.network_allowed is False


def test_subprocess_false():
    config = sandbox_config_from_permission({"subprocess_spawn": False})
    assert config.subprocess_allowed is False


# ── Path variable resolution ────────────────────────────────────────────────


def test_module_dir_variable():
    perm = {"filesystem_read": ["$MODULE_DIR/data"]}
    config = sandbox_config_from_permission(perm, module_dir="/modules/polymer")
    assert config.read_paths == ["/modules/polymer/data"]


def test_workspace_dir_variable():
    perm = {"filesystem_write": ["$WORKSPACE_DIR/output"]}
    config = sandbox_config_from_permission(perm, workspace_dir="/ws/exp1")
    assert config.write_paths == ["/ws/exp1/output"]


def test_data_dir_variable():
    perm = {"filesystem_read": ["$DATA_DIR/datasets"]}
    config = sandbox_config_from_permission(perm, data_dir="/shared/data")
    assert config.read_paths == ["/shared/data/datasets"]


def test_multiple_variables_in_one_path():
    perm = {"filesystem_read": ["$MODULE_DIR/$DATA_DIR"]}
    config = sandbox_config_from_permission(perm, module_dir="/m", data_dir="sub")
    assert config.read_paths == ["/m/sub"]


def test_no_variable_passthrough():
    perm = {"filesystem_read": ["/absolute/path"]}
    config = sandbox_config_from_permission(perm)
    assert config.read_paths == ["/absolute/path"]


# ── Multiple paths ──────────────────────────────────────────────────────────


def test_multiple_read_paths():
    perm = {"filesystem_read": ["/a", "/b", "/c"]}
    config = sandbox_config_from_permission(perm)
    assert config.read_paths == ["/a", "/b", "/c"]


def test_multiple_write_paths():
    perm = {"filesystem_write": ["/x", "/y"]}
    config = sandbox_config_from_permission(perm)
    assert config.write_paths == ["/x", "/y"]


# ── Type coercion ───────────────────────────────────────────────────────────


def test_string_max_memory():
    """Integer fields should be coerced from strings."""
    config = sandbox_config_from_permission({"max_memory_mb": "512"})
    assert config.max_memory_mb == 512


def test_string_max_cpu():
    config = sandbox_config_from_permission({"max_cpu_seconds": "120"})
    assert config.max_cpu_seconds == 120


# ── Return type ─────────────────────────────────────────────────────────────


def test_returns_sandbox_config_instance():
    config = sandbox_config_from_permission({})
    assert isinstance(config, SandboxConfig)


def test_config_is_frozen():
    config = sandbox_config_from_permission({})
    try:
        config.network_allowed = True  # type: ignore[misc]
        assert False, "should have raised"
    except AttributeError:
        pass  # frozen dataclass
