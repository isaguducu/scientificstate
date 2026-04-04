"""Kernel-level sandbox — platform dispatcher.

Selects the appropriate sandbox backend for the current OS:
  - Linux  : BubblewrapSandbox  (bwrap)
  - macOS  : SeatbeltSandbox    (sandbox-exec)
  - Windows: AppContainerSandbox (Job Objects)
  - Other  : FallbackSandbox    (resource.setrlimit, P1 behaviour)
"""
from __future__ import annotations

import platform
import resource
import subprocess

from scientificstate.modules.sandbox.base import SandboxBackend, SandboxConfig, SandboxResult


class FallbackSandbox(SandboxBackend):
    """Minimal sandbox using POSIX setrlimit — P1 fallback behaviour.

    This does NOT provide filesystem or network isolation, only
    CPU and memory limits via resource.setrlimit (Unix-like systems).
    """

    def is_available(self) -> bool:
        return hasattr(resource, "setrlimit")

    def execute(
        self,
        command: list[str],
        config: SandboxConfig,
        cwd: str,
    ) -> SandboxResult:
        def _preexec() -> None:
            """Set resource limits in the child process before exec."""
            if config.max_cpu_seconds > 0:
                resource.setrlimit(
                    resource.RLIMIT_CPU,
                    (config.max_cpu_seconds, config.max_cpu_seconds),
                )
            if config.max_memory_mb > 0:
                mem_bytes = config.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=config.max_cpu_seconds or None,
                preexec_fn=_preexec,
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
                stderr=f"fallback sandbox timeout after {config.max_cpu_seconds}s",
            )
        except FileNotFoundError:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=f"command not found: {command[0] if command else '(empty)'}",
            )


def get_sandbox() -> SandboxBackend:
    """Return the best available sandbox backend for this platform."""
    system = platform.system()

    if system == "Linux":
        from scientificstate.modules.sandbox.linux import BubblewrapSandbox

        backend = BubblewrapSandbox()
        if backend.is_available():
            return backend

    elif system == "Darwin":
        from scientificstate.modules.sandbox.macos import SeatbeltSandbox

        backend = SeatbeltSandbox()
        if backend.is_available():
            return backend

    elif system == "Windows":
        from scientificstate.modules.sandbox.windows import AppContainerSandbox

        backend = AppContainerSandbox()
        if backend.is_available():
            return backend

    # Fallback for all platforms when native tooling is missing
    return FallbackSandbox()
