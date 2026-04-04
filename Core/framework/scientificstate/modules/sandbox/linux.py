"""Linux kernel sandbox — bubblewrap (bwrap) backend.

bubblewrap uses Linux namespaces (PID, network, mount) to isolate
module execution.  Minimum kernel: >= 3.8 (user namespaces).

Requirements:
  - ``bwrap`` binary on PATH (Fedora/Ubuntu: ``bubblewrap`` package).
"""
from __future__ import annotations

import shutil
import subprocess

from scientificstate.modules.sandbox.base import SandboxBackend, SandboxConfig, SandboxResult


class BubblewrapSandbox(SandboxBackend):
    """Linux sandbox using bubblewrap (bwrap)."""

    def is_available(self) -> bool:
        return shutil.which("bwrap") is not None

    def _build_args(self, command: list[str], config: SandboxConfig, cwd: str) -> list[str]:
        """Assemble the full bwrap command line."""
        args: list[str] = ["bwrap"]

        # -- PID namespace isolation (always) --
        args.append("--unshare-pid")

        # -- Network namespace isolation --
        if not config.network_allowed:
            args.append("--unshare-net")

        # -- Filesystem: read-only bind mounts --
        for rpath in config.read_paths:
            args.extend(["--ro-bind", rpath, rpath])

        # -- Filesystem: read-write bind mounts --
        for wpath in config.write_paths:
            args.extend(["--bind", wpath, wpath])

        # -- tmpfs for /tmp --
        args.extend(["--tmpfs", "/tmp"])

        # -- Working directory --
        args.extend(["--chdir", cwd])

        # -- Subprocess restriction via seccomp (if disallowed) --
        # Note: full seccomp filter requires a compiled BPF program.
        # For now we rely on PID namespace + no shell access.
        # A production deployment would load a seccomp JSON profile here.
        if not config.subprocess_allowed:
            args.append("--unshare-ipc")

        # -- Command to run inside the sandbox --
        args.extend(["--", *command])

        return args

    def execute(
        self,
        command: list[str],
        config: SandboxConfig,
        cwd: str,
    ) -> SandboxResult:
        args = self._build_args(command, config, cwd)

        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
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
                stderr="bwrap binary not found",
            )
