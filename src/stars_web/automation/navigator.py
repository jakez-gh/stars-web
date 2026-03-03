"""Screen navigation: move between Stars! main screens using hotkeys.

Stars! keyboard shortcuts
--------------------------
F1  -- Planet summary list
F2  -- Fleet list
F3  -- Scanner (the main galaxy map)
F4  -- Research / Technology dialog
F10 -- Race summary

Usage::

    from stars_web.automation.navigator import Navigator, StarScreen
    from stars_web.automation.window import StarsWindow

    win = StarsWindow.find()
    nav = Navigator(win)
    nav.go(StarScreen.PLANETS)   # press F1, wait, optionally verify
    nav.go(StarScreen.SCANNER)   # press F3, wait, optionally verify
"""

from __future__ import annotations

import enum
import time
from typing import Callable

from stars_web.automation.input import Input
from stars_web.automation.window import StarsWindow


class StarScreen(enum.Enum):
    """Named Stars! screens accessible via function keys."""

    PLANETS = "planets"
    FLEETS = "fleets"
    SCANNER = "scanner"
    RESEARCH = "research"
    RACE = "race"


# Hotkey for each screen
_SCREEN_HOTKEYS: dict[StarScreen, int] = {
    StarScreen.PLANETS: Input.VK_F1,
    StarScreen.FLEETS: Input.VK_F2,
    StarScreen.SCANNER: Input.VK_F3,
    StarScreen.RESEARCH: Input.VK_F4,
    StarScreen.RACE: Input.VK_F10,
}

# Default delay (seconds) after pressing the hotkey to let the screen render
_DEFAULT_SETTLE_DELAY = 0.5


class Navigator:
    """Navigate between Stars! main screens.

    Parameters
    ----------
    win:
        The :class:`~stars_web.automation.window.StarsWindow` to operate on.
    settle_delay:
        Seconds to wait after pressing the hotkey for the screen to render.
    verify_fn:
        Optional callable ``(win, screen) -> bool`` that inspects a
        screenshot to confirm the correct screen is displayed.  If
        provided and it returns *False*, a :exc:`RuntimeError` is raised.
    """

    def __init__(
        self,
        win: StarsWindow,
        settle_delay: float = _DEFAULT_SETTLE_DELAY,
        verify_fn: Callable[[StarsWindow, StarScreen], bool] | None = None,
    ) -> None:
        self.win = win
        self.settle_delay = settle_delay
        self.verify_fn = verify_fn

    def go(self, screen: StarScreen) -> None:
        """Navigate to the given Stars! screen.

        Parameters
        ----------
        screen:
            The screen to navigate to.

        Raises
        ------
        ValueError
            If *screen* is not a recognised :class:`StarScreen`.
        RuntimeError
            If *verify_fn* is set and screen verification fails.
        """
        vk = _SCREEN_HOTKEYS.get(screen)
        if vk is None:
            raise ValueError(f"No hotkey registered for screen {screen!r}")

        self.win.focus()
        Input.key(vk)
        time.sleep(self.settle_delay)

        if self.verify_fn is not None:
            if not self.verify_fn(self.win, screen):
                raise RuntimeError(
                    f"Screen verification failed after navigating to {screen.value!r}"
                )

    def dismiss_dialog(self) -> None:
        """Press Escape to dismiss the topmost modal dialog."""
        self.win.focus()
        Input.key(Input.VK_ESCAPE)
        time.sleep(self.settle_delay)

    def confirm_dialog(self) -> None:
        """Press Enter to confirm the topmost modal dialog."""
        self.win.focus()
        Input.key(Input.VK_RETURN)
        time.sleep(self.settle_delay)
