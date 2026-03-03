"""Window control: find, focus, pin and measure the Stars! window.

Usage::

    from stars_web.automation.window import StarsWindow

    win = StarsWindow.find()  # raises RuntimeError if not found
    win.focus()
    win.pin(x=100, y=100)
    left, top, right, bottom = win.window_rect()
    left, top, right, bottom = win.client_rect_screen()
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes

from stars_web.automation.launcher import _find_stars_hwnd

_user32 = ctypes.windll.user32

# Win32 constants
_SWP_NOSIZE = 0x0001
_SWP_NOZORDER = 0x0004
_HWND_TOP = 0
_SW_RESTORE = 9


class StarsWindow:
    """Thin wrapper around a Stars! Win32 window handle.

    Parameters
    ----------
    hwnd:
        Win32 window handle (HWND) for the Stars! window.
    """

    def __init__(self, hwnd: int) -> None:
        self.hwnd = hwnd

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def find(cls) -> "StarsWindow":
        """Find the running Stars! window.

        Raises
        ------
        RuntimeError
            If Stars! is not currently running.
        """
        hwnd = _find_stars_hwnd()
        if hwnd is None:
            raise RuntimeError("Stars! window not found — is the game running?")
        return cls(hwnd)

    # ------------------------------------------------------------------
    # Focus / position
    # ------------------------------------------------------------------

    def focus(self) -> None:
        """Bring the Stars! window to the foreground."""
        _user32.ShowWindow(self.hwnd, _SW_RESTORE)
        _user32.SetForegroundWindow(self.hwnd)

    def pin(self, x: int, y: int) -> None:
        """Move the window to (*x*, *y*) without resizing."""
        _user32.SetWindowPos(
            self.hwnd,
            _HWND_TOP,
            x,
            y,
            0,
            0,
            _SWP_NOSIZE | _SWP_NOZORDER,
        )

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def window_rect(self) -> tuple[int, int, int, int]:
        """Return (left, top, right, bottom) of the whole window in screen coords."""
        rect = ctypes.wintypes.RECT()
        _user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        return rect.left, rect.top, rect.right, rect.bottom

    def client_rect_screen(self) -> tuple[int, int, int, int]:
        """Return (left, top, right, bottom) of the client area in screen coords."""
        rect = ctypes.wintypes.RECT()
        _user32.GetClientRect(self.hwnd, ctypes.byref(rect))

        pt_tl = ctypes.wintypes.POINT(rect.left, rect.top)
        pt_br = ctypes.wintypes.POINT(rect.right, rect.bottom)
        _user32.ClientToScreen(self.hwnd, ctypes.byref(pt_tl))
        _user32.ClientToScreen(self.hwnd, ctypes.byref(pt_br))

        return pt_tl.x, pt_tl.y, pt_br.x, pt_br.y

    def client_size(self) -> tuple[int, int]:
        """Return (width, height) of the client area."""
        left, top, right, bottom = self.client_rect_screen()
        return right - left, bottom - top

    def title(self) -> str:
        """Return the current window title text."""
        buf = ctypes.create_unicode_buffer(256)
        _user32.GetWindowTextW(self.hwnd, buf, 256)
        return buf.value

    def is_visible(self) -> bool:
        """Return True if the window is currently visible."""
        return bool(_user32.IsWindowVisible(self.hwnd))
