"""Input simulation: mouse clicks and keystrokes for the Stars! window.

Uses ``SendInput`` via ctypes so that inputs are delivered at the OS level
rather than via window messages (more reliable for 16-bit apps under OTVDM).

Usage::

    from stars_web.automation.input import Input
    from stars_web.automation.window import StarsWindow

    win = StarsWindow.find()
    win.focus()

    Input.click(100, 200)           # left-click at screen coords
    Input.key(Input.VK_F1)          # press F1
    Input.key_combo(Input.VK_MENU, Input.VK_F4)  # Alt+F4
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import time

_user32 = ctypes.windll.user32

# ---------------------------------------------------------------------------
# SendInput structures
# ---------------------------------------------------------------------------

_INPUT_MOUSE = 0
_INPUT_KEYBOARD = 1

_MOUSEEVENTF_MOVE = 0x0001
_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004
_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP = 0x0010
_MOUSEEVENTF_ABSOLUTE = 0x8000

_KEYEVENTF_KEYUP = 0x0002


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("_input", _INPUT_UNION),
    ]


def _send(*inputs: _INPUT) -> None:
    n = len(inputs)
    arr = (_INPUT * n)(*inputs)
    _user32.SendInput(n, arr, ctypes.sizeof(_INPUT))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class Input:
    """Static helpers for mouse and keyboard input via SendInput."""

    # ------------------------------------------------------------------
    # Virtual-key constants used by Stars!
    # ------------------------------------------------------------------
    VK_RETURN = 0x0D
    VK_ESCAPE = 0x1B
    VK_MENU = 0x12  # Alt
    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    VK_F1 = 0x70
    VK_F2 = 0x71
    VK_F3 = 0x72
    VK_F4 = 0x73
    VK_F5 = 0x74
    VK_F6 = 0x75
    VK_F7 = 0x76
    VK_F8 = 0x77
    VK_F9 = 0x78
    VK_F10 = 0x79

    # Delay (seconds) between key-down and key-up events
    DEFAULT_KEY_DELAY: float = 0.05

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------

    @staticmethod
    def move(x: int, y: int) -> None:
        """Move the mouse cursor to absolute screen coordinates (*x*, *y*)."""
        # Normalise to 0–65535 range required by MOUSEEVENTF_ABSOLUTE
        screen_w = _user32.GetSystemMetrics(0)
        screen_h = _user32.GetSystemMetrics(1)
        nx = int(x * 65535 / screen_w)
        ny = int(y * 65535 / screen_h)

        inp = _INPUT(
            type=_INPUT_MOUSE,
            _input=_INPUT_UNION(
                mi=_MOUSEINPUT(
                    dx=nx,
                    dy=ny,
                    mouseData=0,
                    dwFlags=_MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE,
                    time=0,
                )
            ),
        )
        _send(inp)

    @staticmethod
    def click(x: int, y: int, delay: float = DEFAULT_KEY_DELAY) -> None:
        """Left-click at absolute screen coordinates (*x*, *y*)."""
        Input.move(x, y)
        time.sleep(delay)

        screen_w = _user32.GetSystemMetrics(0)
        screen_h = _user32.GetSystemMetrics(1)
        nx = int(x * 65535 / screen_w)
        ny = int(y * 65535 / screen_h)

        down = _INPUT(
            type=_INPUT_MOUSE,
            _input=_INPUT_UNION(
                mi=_MOUSEINPUT(
                    dx=nx,
                    dy=ny,
                    mouseData=0,
                    dwFlags=_MOUSEEVENTF_LEFTDOWN | _MOUSEEVENTF_ABSOLUTE,
                    time=0,
                )
            ),
        )
        up = _INPUT(
            type=_INPUT_MOUSE,
            _input=_INPUT_UNION(
                mi=_MOUSEINPUT(
                    dx=nx,
                    dy=ny,
                    mouseData=0,
                    dwFlags=_MOUSEEVENTF_LEFTUP | _MOUSEEVENTF_ABSOLUTE,
                    time=0,
                )
            ),
        )
        _send(down)
        time.sleep(delay)
        _send(up)

    @staticmethod
    def right_click(x: int, y: int, delay: float = DEFAULT_KEY_DELAY) -> None:
        """Right-click at absolute screen coordinates (*x*, *y*)."""
        Input.move(x, y)
        time.sleep(delay)

        screen_w = _user32.GetSystemMetrics(0)
        screen_h = _user32.GetSystemMetrics(1)
        nx = int(x * 65535 / screen_w)
        ny = int(y * 65535 / screen_h)

        down = _INPUT(
            type=_INPUT_MOUSE,
            _input=_INPUT_UNION(
                mi=_MOUSEINPUT(
                    dx=nx,
                    dy=ny,
                    mouseData=0,
                    dwFlags=_MOUSEEVENTF_RIGHTDOWN | _MOUSEEVENTF_ABSOLUTE,
                    time=0,
                )
            ),
        )
        up = _INPUT(
            type=_INPUT_MOUSE,
            _input=_INPUT_UNION(
                mi=_MOUSEINPUT(
                    dx=nx,
                    dy=ny,
                    mouseData=0,
                    dwFlags=_MOUSEEVENTF_RIGHTUP | _MOUSEEVENTF_ABSOLUTE,
                    time=0,
                )
            ),
        )
        _send(down)
        time.sleep(delay)
        _send(up)

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    @staticmethod
    def key(vk: int, delay: float = DEFAULT_KEY_DELAY) -> None:
        """Press and release a single virtual-key code.

        Parameters
        ----------
        vk:
            Win32 virtual-key code.  Common codes are available as
            class constants, e.g. ``Input.VK_F1``.
        delay:
            Seconds to hold the key down before releasing.
        """
        down = _INPUT(
            type=_INPUT_KEYBOARD,
            _input=_INPUT_UNION(ki=_KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0)),
        )
        up = _INPUT(
            type=_INPUT_KEYBOARD,
            _input=_INPUT_UNION(ki=_KEYBDINPUT(wVk=vk, wScan=0, dwFlags=_KEYEVENTF_KEYUP, time=0)),
        )
        _send(down)
        time.sleep(delay)
        _send(up)

    @staticmethod
    def key_combo(*vks: int, delay: float = DEFAULT_KEY_DELAY) -> None:
        """Press a key combination (e.g. Alt+F4).

        All keys are pressed in order, then released in reverse order.

        Parameters
        ----------
        *vks:
            Virtual-key codes to press simultaneously, e.g.
            ``Input.VK_MENU, Input.VK_F4`` for Alt+F4.
        delay:
            Seconds between press and release.
        """
        for vk in vks:
            down = _INPUT(
                type=_INPUT_KEYBOARD,
                _input=_INPUT_UNION(ki=_KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0)),
            )
            _send(down)
        time.sleep(delay)
        for vk in reversed(vks):
            up = _INPUT(
                type=_INPUT_KEYBOARD,
                _input=_INPUT_UNION(
                    ki=_KEYBDINPUT(wVk=vk, wScan=0, dwFlags=_KEYEVENTF_KEYUP, time=0)
                ),
            )
            _send(up)
