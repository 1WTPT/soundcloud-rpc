"""Bounded page reads and profile-safe process restart."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


class PageReader:
    def __init__(self, evaluate, timeout=3):
        self.evaluate, self.timeout = evaluate, timeout
        self.done = None
        self.result = None
        self.error = None

    def read(self):
        if self.done is None:
            self.done = threading.Event()
            self.started = time.monotonic()
            def read_once():
                try:
                    self.result = self.evaluate()
                except Exception as exc:
                    self.error = exc
                finally:
                    self.done.set()
            threading.Thread(target=read_once, name='page-snapshot', daemon=True).start()
        if not self.done.wait(self.timeout):
            raise TimeoutError('WebView2 did not respond; use Reload or Restart')
        result, error, stale = self.result, self.error, time.monotonic() - self.started > self.timeout
        self.done = self.result = self.error = None
        if error:
            raise error
        if stale:
            raise TimeoutError('Discarded stale page snapshot')
        return result


def launch_restart():
    command = [sys.executable]
    if not getattr(sys, 'frozen', False):
        command.append(str(Path(__file__).with_name('app.py')))
    command.extend(['--wait-for-parent', str(os.getpid())])
    environment = os.environ.copy()
    environment['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    subprocess.Popen(command, env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


def wait_for_parent():
    if len(sys.argv) != 3 or sys.argv[1] != '--wait-for-parent':
        return
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.OpenProcess(0x00100000, False, int(sys.argv[2]))
    if handle:
        try:
            if api.WaitForSingleObject(handle, 20000) != 0:
                raise SystemExit('Previous app is still running; restart cancelled.')
        finally:
            api.CloseHandle(handle)
