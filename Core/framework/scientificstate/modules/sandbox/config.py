"""Permission manifest to SandboxConfig transformation.

The module-permission.schema.json uses a FLAT shape:
  {network, filesystem_read, filesystem_write, subprocess_spawn,
   max_memory_mb, max_cpu_seconds}

This module converts that flat dict into a typed SandboxConfig,
resolving path variables like $MODULE_DIR along the way.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scientificstate.modules.sandbox.base import SandboxConfig

# Variables that may appear in filesystem paths
_PATH_VARIABLES = {
    "$MODULE_DIR",
    "$WORKSPACE_DIR",
    "$DATA_DIR",
}


def _resolve_path(raw: str, variables: dict[str, str]) -> str:
    """Replace known path variables with concrete values."""
    result = raw
    for var, value in variables.items():
        result = result.replace(var, value)
    return result


def sandbox_config_from_permission(
    permission: dict[str, Any],
    *,
    module_dir: str | Path = "",
    workspace_dir: str | Path = "",
    data_dir: str | Path = "",
) -> SandboxConfig:
    """Build a SandboxConfig from a flat permission manifest dict.

    Args:
        permission: dict matching module-permission.schema.json (flat shape).
        module_dir: concrete path to substitute for $MODULE_DIR.
        workspace_dir: concrete path to substitute for $WORKSPACE_DIR.
        data_dir: concrete path to substitute for $DATA_DIR.

    Returns:
        SandboxConfig with resolved paths and resource limits.
    """
    variables = {
        "$MODULE_DIR": str(module_dir),
        "$WORKSPACE_DIR": str(workspace_dir),
        "$DATA_DIR": str(data_dir),
    }

    read_paths = [
        _resolve_path(p, variables)
        for p in permission.get("filesystem_read", [])
    ]
    write_paths = [
        _resolve_path(p, variables)
        for p in permission.get("filesystem_write", [])
    ]

    return SandboxConfig(
        read_paths=read_paths,
        write_paths=write_paths,
        network_allowed=bool(permission.get("network", False)),
        subprocess_allowed=bool(permission.get("subprocess_spawn", False)),
        max_cpu_seconds=int(permission.get("max_cpu_seconds", 300)),
        max_memory_mb=int(permission.get("max_memory_mb", 2048)),
    )
