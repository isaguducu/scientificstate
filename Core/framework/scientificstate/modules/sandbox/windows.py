"""Windows sandbox — Job Objects for CPU/memory limits.

Job Objects provide kernel-enforced resource limits on Windows.
AppContainer token creation is optional (requires elevated privileges).

On non-Windows platforms, is_available() returns False.
"""
from __future__ import annotations

import subprocess
import sys

from scientificstate.modules.sandbox.base import SandboxBackend, SandboxConfig, SandboxResult


def _apply_job_limits(pid: int, config: SandboxConfig) -> bool:
    """Apply Job Object CPU/memory limits to a process.

    Returns True on success, False if Win32 API is unavailable.
    """
    if sys.platform != "win32":
        return False

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        # Create Job Object
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return False

        # JOBOBJECT_EXTENDED_LIMIT_INFORMATION structure (simplified)
        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
        JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
        JobObjectExtendedLimitInformation = 9

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = 0

        # Memory limit
        if config.max_memory_mb > 0:
            info.ProcessMemoryLimit = config.max_memory_mb * 1024 * 1024
            info.BasicLimitInformation.LimitFlags |= JOB_OBJECT_LIMIT_PROCESS_MEMORY

        # CPU time limit (100-nanosecond intervals)
        if config.max_cpu_seconds > 0:
            info.BasicLimitInformation.PerProcessUserTimeLimit = (
                config.max_cpu_seconds * 10_000_000
            )
            info.BasicLimitInformation.LimitFlags |= JOB_OBJECT_LIMIT_PROCESS_TIME

        kernel32.SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )

        # Assign process to job
        PROCESS_ALL_ACCESS = 0x001FFFFF
        process_handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if process_handle:
            kernel32.AssignProcessToJobObject(job, process_handle)
            kernel32.CloseHandle(process_handle)

        return True
    except Exception:  # noqa: BLE001
        return False


class AppContainerSandbox(SandboxBackend):
    """Windows sandbox using Job Objects for resource limits."""

    def is_available(self) -> bool:
        return sys.platform == "win32"

    def execute(
        self,
        command: list[str],
        config: SandboxConfig,
        cwd: str,
    ) -> SandboxResult:
        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                text=True,
            )

            # Apply Job Object limits to the running process
            _apply_job_limits(proc.pid, config)

            try:
                stdout, stderr = proc.communicate(
                    timeout=config.max_cpu_seconds or None
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                return SandboxResult(
                    exit_code=-1,
                    stdout="",
                    stderr=f"sandbox timeout after {config.max_cpu_seconds}s",
                )

            return SandboxResult(
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
            )
        except FileNotFoundError:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=f"command not found: {command[0] if command else '(empty)'}",
            )
