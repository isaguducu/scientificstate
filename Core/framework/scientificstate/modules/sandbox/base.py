"""Sandbox backend ABC and configuration — kernel-level process isolation.

Each platform implements SandboxBackend to enforce resource limits and
filesystem/network isolation for untrusted module code.

Permission manifest (module-permission.schema.json) uses a FLAT shape:
  network, filesystem_read, filesystem_write, subprocess_spawn,
  max_memory_mb, max_cpu_seconds.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SandboxConfig:
    """Immutable sandbox configuration derived from a module permission manifest.

    All fields map directly to the flat permission schema.
    """

    read_paths: list[str] = field(default_factory=list)
    write_paths: list[str] = field(default_factory=list)
    network_allowed: bool = False
    subprocess_allowed: bool = False
    max_cpu_seconds: int = 300
    max_memory_mb: int = 2048


@dataclass
class SandboxResult:
    """Result of a sandboxed command execution."""

    exit_code: int
    stdout: str
    stderr: str


class SandboxBackend(ABC):
    """Abstract base for platform-specific sandbox implementations."""

    @abstractmethod
    def execute(
        self,
        command: list[str],
        config: SandboxConfig,
        cwd: str,
    ) -> SandboxResult:
        """Run *command* inside a sandboxed environment.

        Args:
            command: program + arguments to execute.
            config: resource and isolation constraints.
            cwd: working directory for the child process.

        Returns:
            SandboxResult with exit code, stdout, stderr.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backend tooling is present on this system."""
        ...

    @property
    def name(self) -> str:
        """Human-readable backend name (used in logs/errors)."""
        return type(self).__name__
