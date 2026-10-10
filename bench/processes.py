"""Own a CLI process group independently of whether its root process is still alive."""

import ctypes
import os
import signal
import subprocess
import time
from ctypes import wintypes


# Windows jobs contain descendants even after their original parent exits; kill-on-close covers failures.
class OwnedProcessTree:
    def __init__(self):
        self.process = None
        self.job = None
        if os.name != 'nt':
            return
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]

        class BasicLimits(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                        ('flags', wintypes.DWORD), ('min_working_set', ctypes.c_size_t),
                        ('max_working_set', ctypes.c_size_t), ('active_limit', wintypes.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [('basic', BasicLimits), ('io', ctypes.c_uint64 * 6),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]

        self.job = self.kernel.CreateJobObjectW(None, None)
        if not self.job:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.kernel.CloseHandle(self.job)
            self.job = None
            raise error

    # Suspend the initial Windows thread until it belongs to the job, preventing an early child-spawn race.
    def spawn(self, command, **kwargs):
        if os.name != 'nt':
            self.process = subprocess.Popen(command, start_new_session=True, **kwargs)
            return self.process
        self.process = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP | 0x4, **kwargs)
        process_handle = int(self.process._handle)
        if not self.kernel.AssignProcessToJobObject(self.job, process_handle):
            error = ctypes.WinError(ctypes.get_last_error())
            self.process.kill()
            self.process.wait(timeout=10)
            raise error
        ntdll = ctypes.WinDLL('ntdll')
        ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
        ntdll.NtResumeProcess.restype = wintypes.LONG
        status = ntdll.NtResumeProcess(process_handle)
        if status != 0:
            raise OSError(f'NtResumeProcess failed: {status}')
        return self.process

    # Terminate only this owned job/group, then verify that it contains no surviving processes.
    def stop(self):
        try:
            if self.process is None:
                return
            if os.name == 'nt':
                if not self.kernel.TerminateJobObject(self.job, 124):
                    raise ctypes.WinError(ctypes.get_last_error())
                accounting = ctypes.create_string_buffer(48)
                deadline = time.monotonic() + 10
                while True:
                    if not self.kernel.QueryInformationJobObject(self.job, 1, accounting, len(accounting), None):
                        raise ctypes.WinError(ctypes.get_last_error())
                    active = wintypes.DWORD.from_buffer(accounting, 40).value
                    if active == 0:
                        break
                    if time.monotonic() > deadline:
                        raise TimeoutError(f'{active} processes remain in the owned job')
                    time.sleep(0.05)
            else:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass  # The owned group has already exited; this is the expected successful state.
                self.process.wait(timeout=10)
                try:
                    os.killpg(self.process.pid, 0)
                except ProcessLookupError:
                    return
                os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=10)
        finally:
            if self.job:
                self.kernel.CloseHandle(self.job)
                self.job = None
