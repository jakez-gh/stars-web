"""Launcher: start and stop Stars! via OTVDM.

Usage::

    from stars_web.automation.launcher import Launcher

    launcher = Launcher(game_dir)
    hwnd = launcher.start(timeout=30)   # returns Win32 HWND
    launcher.stop()
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import subprocess
import time
from pathlib import Path

# Stars! window class registered by the 16-bit app running inside OTVDM.
# EnumWindows is used as a fallback when the class name is unknown.
_STARS_WINDOW_TITLES = ("Stars!", "STARS.EXE")
_POLL_INTERVAL = 0.25  # seconds


def _find_stars_hwnd() -> int | None:
    """Return HWND of a running Stars! window, or None if not found."""
    user32 = ctypes.windll.user32
    found: list[int] = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.wintypes.BOOL,
        ctypes.wintypes.HWND,
        ctypes.wintypes.LPARAM,
    )

    buf = ctypes.create_unicode_buffer(256)

    def _cb(hwnd: int, _lparam: int) -> bool:
        user32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value.strip()
        if any(t.lower() in title.lower() for t in _STARS_WINDOW_TITLES):
            found.append(hwnd)
            return False  # stop enumeration
        return True

    user32.EnumWindows(EnumWindowsProc(_cb), 0)
    return found[0] if found else None


class Launcher:
    """Start and stop Stars! (16-bit) via the OTVDM wrapper.

    Parameters
    ----------
    game_dir:
        Path to the starswine directory that contains ``otvdm/otvdm.exe``
        and ``stars/stars.exe``.
    """

    def __init__(self, game_dir: str | Path) -> None:
        self.game_dir = Path(game_dir)
        self._proc: subprocess.Popen | None = None

    @property
    def otvdm_exe(self) -> Path:
        return self.game_dir / "otvdm" / "otvdm.exe"

    @property
    def stars_exe(self) -> Path:
        return self.game_dir / "stars" / "stars.exe"

    def start(self, timeout: float = 30.0) -> int:
        """Launch Stars! and wait for its window to appear.

        Returns
        -------
        int
            Win32 HWND of the Stars! window.

        Raises
        ------
        FileNotFoundError
            If otvdm.exe or stars.exe is missing.
        TimeoutError
            If the window does not appear within *timeout* seconds.
        """
        if not self.otvdm_exe.exists():
            raise FileNotFoundError(f"otvdm.exe not found: {self.otvdm_exe}")
        if not self.stars_exe.exists():
            raise FileNotFoundError(f"stars.exe not found: {self.stars_exe}")

        self._proc = subprocess.Popen(
            [str(self.otvdm_exe), str(self.stars_exe)],
            cwd=str(self.game_dir),
        )

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            hwnd = _find_stars_hwnd()
            if hwnd:
                return hwnd
            time.sleep(_POLL_INTERVAL)

        self._proc.terminate()
        raise TimeoutError(f"Stars! window did not appear within {timeout}s")

    def stop(self) -> None:
        """Gracefully close Stars! then terminate the process if needed."""
        hwnd = _find_stars_hwnd()
        if hwnd:
            WM_CLOSE = 0x0010
            ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            # Give it up to 5 s to close
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if _find_stars_hwnd() is None:
                    break
                time.sleep(_POLL_INTERVAL)

        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    def is_running(self) -> bool:
        """Return True if the Stars! window is currently visible."""
        return _find_stars_hwnd() is not None
