"""Own a hidden Windows process tree with a kill-on-close Job Object."""

import ctypes
from ctypes import wintypes as w
import os
from pathlib import Path
import subprocess
import time

if os.name != "nt":
    raise RuntimeError("This controller requires Windows.")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")


class IO(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "reads", "writes", "other", "read_bytes", "write_bytes", "other_bytes")]


class Basic(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                ("flags", w.DWORD), ("minimum", ctypes.c_size_t), ("maximum", ctypes.c_size_t),
                ("active_limit", w.DWORD), ("affinity", ctypes.c_size_t),
                ("priority", w.DWORD), ("scheduling", w.DWORD)]


class Limits(ctypes.Structure):
    _fields_ = [("basic", Basic), ("io", IO)] + [(name, ctypes.c_size_t) for name in (
        "process_memory", "job_memory", "peak_process_memory", "peak_job_memory")]


class Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_longlong) for name in (
        "user_time", "kernel_time", "period_user", "period_kernel")] + [
        (name, w.DWORD) for name in ("page_faults", "total", "active", "terminated")]


k32.CreateJobObjectW.argtypes = [w.LPVOID, w.LPCWSTR]
k32.CreateJobObjectW.restype = w.HANDLE
for name, args in {
    "SetInformationJobObject": [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD],
    "QueryInformationJobObject": [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, w.LPVOID],
    "AssignProcessToJobObject": [w.HANDLE, w.HANDLE],
    "TerminateJobObject": [w.HANDLE, w.UINT], "CloseHandle": [w.HANDLE],
}.items():
    getattr(k32, name).argtypes = args
    getattr(k32, name).restype = w.BOOL
ntdll.NtResumeProcess.argtypes = [w.HANDLE]
ntdll.NtResumeProcess.restype = ctypes.c_long


def checked(value):
    if not value:
        raise ctypes.WinError(ctypes.get_last_error())
    return value


class OwnedProcess:
    def __init__(self, command, log, env=None, cwd=None):
        self.job = checked(k32.CreateJobObjectW(None, None))
        self.proc = None
        self.closed = False
        self.shutdown_confirmed = False
        self.log = Path(log).open("wb")
        try:
            limits = Limits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            checked(k32.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
            self.proc = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, env=env, cwd=cwd,
                creationflags=subprocess.CREATE_NO_WINDOW | 0x4)  # CREATE_SUSPENDED
            checked(k32.AssignProcessToJobObject(self.job, int(self.proc._handle)))
            status = ntdll.NtResumeProcess(int(self.proc._handle))
            if status != 0:
                raise OSError(f"Could not resume owned process: NTSTATUS {status:#x}")
        except BaseException:
            if self.proc is not None:
                self.proc.kill()
                self.proc.wait(timeout=5)
            self.close()
            raise

    def active(self):
        information = Accounting()
        checked(k32.QueryInformationJobObject(self.job, 1, ctypes.byref(information),
                                              ctypes.sizeof(information), None))
        return information.active

    def close(self):
        if self.closed:
            return
        try:
            checked(k32.TerminateJobObject(self.job, 125))
            deadline = time.monotonic() + 5
            while self.active() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.shutdown_confirmed = self.active() == 0
            if self.proc is not None:
                self.proc.wait(timeout=5)
            if not self.shutdown_confirmed:
                raise RuntimeError("Owned process-tree shutdown could not be confirmed.")
        finally:
            k32.CloseHandle(self.job)
            self.log.close()
            self.closed = True

    def wait(self, timeout, observe=None, cancel=None):
        started = time.monotonic()
        next_observation = 0
        try:
            while self.proc.poll() is None:
                elapsed = time.monotonic() - started
                if cancel and Path(cancel).exists():
                    raise InterruptedError("Cancellation file detected.")
                if elapsed >= timeout:
                    raise TimeoutError(f"Stage exceeded its {timeout}-second deadline.")
                if observe and elapsed >= next_observation:
                    observe(self.proc.pid, elapsed)
                    next_observation = elapsed + 5
                time.sleep(0.2)
            return self.proc.returncode
        finally:
            self.close()
