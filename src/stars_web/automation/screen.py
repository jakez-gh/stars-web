"""Screenshot capture: grab the Stars! window to a PIL Image or PNG file.

Usage::

    from stars_web.automation.screen import Screen
    from stars_web.automation.window import StarsWindow

    win = StarsWindow.find()
    img = Screen.capture(win)          # PIL Image
    Screen.save(win, "shot.png")       # save to PNG
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import ImageGrab

from stars_web.automation.window import StarsWindow


class Screen:
    """Screenshot helpers for the Stars! window."""

    @staticmethod
    def capture(win: StarsWindow) -> "ImageGrab.Image":
        """Capture the Stars! client area as a PIL Image.

        Parameters
        ----------
        win:
            A :class:`~stars_web.automation.window.StarsWindow` instance.

        Returns
        -------
        PIL.Image.Image
            RGB screenshot of the client area.
        """
        bbox = win.client_rect_screen()  # (left, top, right, bottom)
        # all_screens=True handles multi-monitor setups correctly
        img = ImageGrab.grab(bbox=bbox, all_screens=True)
        return img

    @staticmethod
    def save(win: StarsWindow, path: str | Path | None = None) -> Path:
        """Capture and save the Stars! client area to a PNG file.

        If *path* is None a timestamped filename is generated in the
        current working directory.

        Parameters
        ----------
        win:
            A :class:`~stars_web.automation.window.StarsWindow` instance.
        path:
            Output PNG file path (created or overwritten).

        Returns
        -------
        Path
            Absolute path of the saved PNG.
        """
        if path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = Path(f"screenshot_{ts}.png")
        else:
            path = Path(path)

        img = Screen.capture(win)
        img.save(str(path), format="PNG")
        return path.resolve()

    @staticmethod
    def is_blank(win: StarsWindow) -> bool:
        """Return True if the captured screenshot is entirely black/one colour.

        Used to sanity-check that the window is actually rendered.
        """
        img = Screen.capture(win)
        # Use tobytes() so we work with Pillow 12+ without deprecation warnings
        data = img.tobytes()
        return len(set(data[i : i + 3] for i in range(0, len(data), 3))) <= 1
