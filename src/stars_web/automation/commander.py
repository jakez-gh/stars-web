"""GUI command automation: set waypoints, edit production queues, allocate research.

These helpers operate on **screen coordinates** — the caller is responsible for
mapping world/game-state coordinates to screen coordinates using
:func:`stars_web.static.js.star_map.worldToScreen` or equivalent.

Depends on:
    #17 / launcher.py   — Stars! running
    #18 / window.py     — window handle
    #19 / screen.py     — screenshot verification
    #20 / input.py      — mouse + keyboard
    #23 / navigator.py  — screen navigation

Usage::

    from stars_web.automation.commander import WaypointSetter, ProductionEditor
    from stars_web.automation.window import StarsWindow

    win = StarsWindow.find()

    # Set a fleet waypoint: click the fleet, right-click the target
    ws = WaypointSetter(win)
    ws.set(fleet_sx=400, fleet_sy=300, target_sx=500, target_sy=250)

    # Change a planet's production queue
    pe = ProductionEditor(win)
    pe.open(planet_sx=200, planet_sy=400)
"""

from __future__ import annotations

import time

from stars_web.automation.input import Input
from stars_web.automation.navigator import Navigator, StarScreen
from stars_web.automation.window import StarsWindow

_DEFAULT_DELAY = 0.3


class WaypointSetter:
    """Set a fleet waypoint via right-click in the Scanner screen.

    Workflow
    --------
    1. Navigate to Scanner (F3) if necessary.
    2. Left-click the fleet to select it.
    3. Right-click the target location to open the context menu.
    4. Click the first menu item (``Set Speed and Waypoint``).
    5. Press Enter to confirm defaults.

    Parameters
    ----------
    win:
        The running Stars! window.
    settle_delay:
        Seconds to pause after each input to allow the UI to respond.
    """

    def __init__(self, win: StarsWindow, settle_delay: float = _DEFAULT_DELAY) -> None:
        self.win = win
        self.settle_delay = settle_delay
        self._nav = Navigator(win, settle_delay=settle_delay)

    def go_to_scanner(self) -> None:
        """Navigate to the scanner screen."""
        self._nav.go(StarScreen.SCANNER)

    def set(
        self,
        fleet_sx: int,
        fleet_sy: int,
        target_sx: int,
        target_sy: int,
        confirm: bool = True,
    ) -> None:
        """Set a waypoint from a fleet to a target location.

        Parameters
        ----------
        fleet_sx, fleet_sy:
            Screen coordinates of the fleet to select.
        target_sx, target_sy:
            Screen coordinates of the waypoint target.
        confirm:
            If True, press Enter after the context menu to accept defaults.
        """
        self.win.focus()

        # Select fleet
        Input.click(fleet_sx, fleet_sy)
        time.sleep(self.settle_delay)

        # Open right-click context menu at target
        Input.right_click(target_sx, target_sy)
        time.sleep(self.settle_delay)

        # First menu item = set waypoint — press Enter to pick it
        Input.key(Input.VK_RETURN)
        time.sleep(self.settle_delay)

        if confirm:
            # Confirm any dialog (warp speed etc.)
            Input.key(Input.VK_RETURN)
            time.sleep(self.settle_delay)

    def clear_waypoints(self, fleet_sx: int, fleet_sy: int) -> None:
        """Select the fleet and press Delete to clear its waypoint queue."""
        self.win.focus()
        Input.click(fleet_sx, fleet_sy)
        time.sleep(self.settle_delay)
        # Delete key (VK_DELETE = 0x2E)
        Input.key(0x2E)
        time.sleep(self.settle_delay)


class ProductionEditor:
    """Open and edit a planet's production queue via double-click.

    Workflow
    --------
    1. Navigate to Planets (F1).
    2. Double-click the planet row to open its production dialog.
    3. Use keyboard shortcuts or clicks to add/remove items.
    4. Press Enter (OK) or Escape (cancel) to close.

    Parameters
    ----------
    win:
        The running Stars! window.
    settle_delay:
        Seconds to pause after each input.
    """

    def __init__(self, win: StarsWindow, settle_delay: float = _DEFAULT_DELAY) -> None:
        self.win = win
        self.settle_delay = settle_delay
        self._nav = Navigator(win, settle_delay=settle_delay)

    def open(self, planet_sx: int, planet_sy: int) -> None:
        """Double-click a planet row to open its production dialog."""
        self.win.focus()
        # Double-click = two rapid left-clicks
        Input.click(planet_sx, planet_sy)
        time.sleep(0.05)
        Input.click(planet_sx, planet_sy)
        time.sleep(self.settle_delay)

    def confirm(self) -> None:
        """Press Enter to accept changes and close the dialog."""
        self.win.focus()
        Input.key(Input.VK_RETURN)
        time.sleep(self.settle_delay)

    def cancel(self) -> None:
        """Press Escape to discard changes and close the dialog."""
        self.win.focus()
        Input.key(Input.VK_ESCAPE)
        time.sleep(self.settle_delay)

    def click_item(self, item_sx: int, item_sy: int) -> None:
        """Click a queue item in the production dialog."""
        self.win.focus()
        Input.click(item_sx, item_sy)
        time.sleep(self.settle_delay)

    def remove_selected(self) -> None:
        """Press Delete to remove the currently selected queue item."""
        self.win.focus()
        Input.key(0x2E)  # VK_DELETE
        time.sleep(self.settle_delay)


class ResearchAllocator:
    """Allocate research fields via the Research dialog (F4).

    Workflow
    --------
    1. Press F4 to open the Research & Technology dialog.
    2. Click the desired field radio button.
    3. Adjust the "Top Priority" slider if needed.
    4. Press Enter to confirm.

    Parameters
    ----------
    win:
        The running Stars! window.
    settle_delay:
        Seconds to pause after each input.
    """

    def __init__(self, win: StarsWindow, settle_delay: float = _DEFAULT_DELAY) -> None:
        self.win = win
        self.settle_delay = settle_delay
        self._nav = Navigator(win, settle_delay=settle_delay)

    def open(self) -> None:
        """Press F4 to open the Research dialog."""
        self._nav.go(StarScreen.RESEARCH)

    def click_field(self, field_sx: int, field_sy: int) -> None:
        """Click a research field button at the given screen coordinates."""
        self.win.focus()
        Input.click(field_sx, field_sy)
        time.sleep(self.settle_delay)

    def confirm(self) -> None:
        """Press Enter to confirm and close the Research dialog."""
        self.win.focus()
        Input.key(Input.VK_RETURN)
        time.sleep(self.settle_delay)

    def cancel(self) -> None:
        """Press Escape to cancel the Research dialog."""
        self.win.focus()
        Input.key(Input.VK_ESCAPE)
        time.sleep(self.settle_delay)
