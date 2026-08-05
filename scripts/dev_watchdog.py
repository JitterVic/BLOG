"""Dev watchdog for scripts/dev.ps1.

Spawns the Flask backend and Vite frontend inside a Windows job object with
JOB_OBJECT_LIMIT_KILL_ON_CLOSE, then blocks. When this process exits --
terminal closed, Ctrl+C, or Stop-Process -- the job handle closes and Windows
terminates every attached process automatically.
"""

import ctypes
import msvcrt
import os
import sys
import threading
import time
import urllib.request
import webbrowser
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / ".run"
BACKEND_PYTHON = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
FRONTEND_DIR = ROOT / "frontend"

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CREATE_NO_WINDOW = 0x08000000
STARTF_USESTDHANDLES = 0x00000100
CTRL_C_EVENT = 0
CTRL_CLOSE_EVENT = 2
JOB_OBJECT_LIMIT_KILL_ON_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerProcessJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
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


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.SetInformationJobObject.argtypes = [
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
]
kernel32.SetInformationJobObject.restype = wintypes.BOOL
kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
kernel32.CreateProcessW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
    wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
    ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION),
]
kernel32.CreateProcessW.restype = wintypes.BOOL
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.SetConsoleCtrlHandler.argtypes = [ctypes.c_void_p, wintypes.BOOL]
kernel32.SetConsoleCtrlHandler.restype = wintypes.BOOL
kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
kernel32.GetStdHandle.restype = wintypes.HANDLE
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

HANDLER_ROUTINE = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

stop_event = threading.Event()


def log(message):
    print(message, flush=True)


def console_handler(ctrl_type):
    if ctrl_type in (CTRL_C_EVENT, CTRL_CLOSE_EVENT):
        stop_event.set()
        return True
    return False


def create_kill_on_close_job():
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_CLOSE
    ok = kernel32.SetInformationJobObject(
        job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    return job


def spawn(job, command_line, cwd, stdout_path, stderr_path):
    startup = STARTUPINFOW()
    startup.cb = ctypes.sizeof(STARTUPINFOW)
    # Keep the historical .run/*.log files: send child output to log files.
    out_fd = os.open(stdout_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    err_fd = os.open(stderr_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    os.set_inheritable(out_fd, True)
    os.set_inheritable(err_fd, True)
    startup.dwFlags = STARTF_USESTDHANDLES
    startup.hStdInput = kernel32.GetStdHandle(0xFFFFFFF6)  # STD_INPUT_HANDLE
    startup.hStdOutput = wintypes.HANDLE(msvcrt.get_osfhandle(out_fd))
    startup.hStdError = wintypes.HANDLE(msvcrt.get_osfhandle(err_fd))
    proc_info = PROCESS_INFORMATION()
    ok = kernel32.CreateProcessW(
        None, command_line, None, None, True, CREATE_NO_WINDOW, None, cwd,
        ctypes.byref(startup), ctypes.byref(proc_info),
    )
    os.close(out_fd)
    os.close(err_fd)
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    kernel32.CloseHandle(proc_info.hThread)
    # Attach to the job; tolerate processes already living in another job.
    if not kernel32.AssignProcessToJobObject(job, proc_info.hProcess):
        log("警告: 无法将 PID={} 加入 Job Object，关闭终端时可能不会自动停止。".format(proc_info.dwProcessId))
    return proc_info


def wait_http_ok(url, timeout_seconds=30):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if 200 <= response.status < 500:
                    return True
        except Exception:
            time.sleep(0.6)
    return False


def write_pid(name, pid):
    (RUN_DIR / name).write_text(str(pid), encoding="ascii")


def read_admin_prefix():
    """Read BLOG_ADMIN_PREFIX from the repo .env so the printed entry is real."""
    env_file = ROOT / ".env"
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("BLOG_ADMIN_PREFIX="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'").rstrip("/")
                if value:
                    return value if value.startswith("/") else f"/{value}"
    return "/admin"


def main():
    RUN_DIR.mkdir(exist_ok=True)
    no_open = "--no-open" in sys.argv[1:]
    handler_ref = HANDLER_ROUTINE(console_handler)
    kernel32.SetConsoleCtrlHandler(handler_ref, True)

    job = create_kill_on_close_job()
    backend = frontend = None
    try:
        backend = spawn(
            job, '"{}" -m blog'.format(BACKEND_PYTHON), str(ROOT),
            str(RUN_DIR / "backend.out.log"), str(RUN_DIR / "backend.err.log"),
        )
        log("后端已启动 PID={}（已绑定 Job Object）".format(backend.dwProcessId))
        write_pid("backend.pid", backend.dwProcessId)
        frontend = spawn(
            job, 'npm.cmd run dev -- --host 127.0.0.1', str(FRONTEND_DIR),
            str(RUN_DIR / "frontend.out.log"), str(RUN_DIR / "frontend.err.log"),
        )
        log("前端已启动 PID={}（已绑定 Job Object）".format(frontend.dwProcessId))
        write_pid("frontend.pid", frontend.dwProcessId)

        log("正在等待服务就绪...")
        backend_ok = wait_http_ok("http://127.0.0.1:5000/api/health", 30)
        frontend_ok = wait_http_ok("http://127.0.0.1:5173", 45)
        log("后端: http://127.0.0.1:5000  " + ("正常" if backend_ok else "未确认就绪，请查看 .run/backend.err.log"))
        log("前端: http://127.0.0.1:5173  " + ("正常" if frontend_ok else "未确认就绪，请查看 .run/frontend.err.log"))
        log("后台: http://127.0.0.1:5000" + read_admin_prefix() + "/login")
        if not no_open and frontend_ok:
            webbrowser.open("http://127.0.0.1:5173")

        log("守护中：关闭此终端或按 Ctrl+C 将同时停止前后端。")
        while not stop_event.is_set():
            if kernel32.WaitForSingleObject(backend.hProcess, 500) == 0:
                log("后端进程已退出，停止全部服务。")
                break
            if kernel32.WaitForSingleObject(frontend.hProcess, 0) == 0:
                log("前端进程已退出，停止全部服务。")
                break
            stop_event.wait(0.5)
    finally:
        stop_event.set()
        for proc in (backend, frontend):
            if proc is not None:
                kernel32.TerminateProcess(proc.hProcess, 1)
                kernel32.WaitForSingleObject(proc.hProcess, 3000)
                kernel32.CloseHandle(proc.hProcess)
        # Closing the last job handle triggers KILL_ON_CLOSE for anything left.
        kernel32.CloseHandle(job)
        log("服务已全部停止。")


if __name__ == "__main__":
    main()
