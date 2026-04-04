"""macOS kernel sandbox — seatbelt / sandbox-exec backend.

Uses Apple's sandbox-exec(1) with a generated Scheme profile to
restrict filesystem, network, and process-fork capabilities.

Note: sandbox-exec is technically deprecated by Apple but remains
functional on all shipping macOS versions (as of macOS 15).
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from scientificstate.modules.sandbox.base import SandboxBackend, SandboxConfig, SandboxResult


def generate_seatbelt_profile(config: SandboxConfig) -> str:
    """Generate a Scheme seatbelt profile from a SandboxConfig.

    Returns:
        String containing the sandbox profile (Scheme s-expression).
    """
    rules: list[str] = [
        "(version 1)",
        "(deny default)",
        # Always allow basic process execution
        "(allow process-exec)",
        "(allow process-fork)" if config.subprocess_allowed else "(deny process-fork)",
        # sysctl / mach-lookup needed for basic operation
        "(allow sysctl-read)",
        "(allow mach-lookup)",
    ]

    # -- Filesystem read --
    for rpath in config.read_paths:
        rules.append(f'(allow file-read* (subpath "{rpath}"))')

    # -- Filesystem write --
    for wpath in config.write_paths:
        rules.append(f'(allow file-write* (subpath "{wpath}"))')

    # -- Temp directory (always allow) --
    rules.append('(allow file-read* file-write* (subpath "/tmp"))')
    rules.append('(allow file-read* file-write* (subpath "/private/tmp"))')

    # -- Network --
    if config.network_allowed:
        rules.append("(allow network*)")
    else:
        rules.append("(deny network*)")

    return "\n".join(rules) + "\n"


class SeatbeltSandbox(SandboxBackend):
    """macOS sandbox using sandbox-exec(1)."""

    def is_available(self) -> bool:
        return shutil.which("sandbox-exec") is not None

    def execute(
        self,
        command: list[str],
        config: SandboxConfig,
        cwd: str,
    ) -> SandboxResult:
        profile = generate_seatbelt_profile(config)

        # Write profile to a temp file (sandbox-exec reads from file or stdin)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sb", delete=False, prefix="ss_sandbox_"
        ) as f:
            f.write(profile)
            profile_path = f.name

        try:
            args = ["sandbox-exec", "-f", profile_path, *command]
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=config.max_cpu_seconds or None,
            )
            return SandboxResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=f"sandbox timeout after {config.max_cpu_seconds}s",
            )
        except FileNotFoundError:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr="sandbox-exec binary not found",
            )
        finally:
            Path(profile_path).unlink(missing_ok=True)
