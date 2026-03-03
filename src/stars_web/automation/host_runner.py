"""Host-turn generator: trigger "File > Save & Generate Turn" via the Stars! GUI.

This module automates the host-side turn generation by navigating the
Stars! File menu.  It then waits for a new ``.m`` output file to confirm
that the turn was generated successfully.

.. note::
   This approach uses the GUI for completeness; the Flask web-UI already
   generates turns via the command line (``POST /game/submit-turn``).  Use
   :class:`GUIHostRunner` when you need to drive a **running** Stars!
   instance from within the automation harness.

Depends on:
    launcher.py / window.py / input.py / navigator.py

Usage::

    from stars_web.automation.host_runner import GUIHostRunner
    from stars_web.automation.window import StarsWindow
    from pathlib import Path

    win = StarsWindow.find()
    runner = GUIHostRunner(win, game_dir=Path("starswine4"), game_prefix="Game")
    new_path = runner.generate_turn(timeout=120)
    print("Turn generated:", new_path)
"""

from __future__ import annotations

import time
from pathlib import Path

from stars_web.automation.input import Input
from stars_web.automation.window import StarsWindow

# Virtual-key for opening a menu via Alt+letter
_VK_ALT = Input.VK_MENU

# Stars! File menu: Alt+F opens it, then navigate with arrow keys.
# The "Generate Turn" item is approximately the 6th item in the File menu.
# Adjust _GENERATE_TURN_STEPS if your Stars! version differs.
_GENERATE_TURN_STEPS = 6

_POLL_INTERVAL = 1.0  # seconds between file-existence checks


class GUIHostRunner:
    """Generate a Stars! turn via the File > Generate Turn menu.

    Parameters
    ----------
    win:
        The running Stars! window.
    game_dir:
        Path to the game directory (contains ``.m`` files).
    game_prefix:
        Game file prefix, e.g. ``"Game"`` for ``Game.m1``.
    player_number:
        The host player number whose ``.m`` file is watched for updates.
        Defaults to ``1``.
    settle_delay:
        Seconds to pause after each UI interaction.
    """

    def __init__(
        self,
        win: StarsWindow,
        game_dir: str | Path,
        game_prefix: str,
        player_number: int = 1,
        settle_delay: float = 0.3,
    ) -> None:
        self.win = win
        self.game_dir = Path(game_dir)
        self.game_prefix = game_prefix
        self.player_number = player_number
        self.settle_delay = settle_delay

    # ------------------------------------------------------------------
    # File paths
    # ------------------------------------------------------------------

    @property
    def m_file(self) -> Path:
        """Path of the ``.m`` file to watch for regeneration."""
        return self.game_dir / f"{self.game_prefix}.m{self.player_number}"

    # ------------------------------------------------------------------
    # Menu navigation
    # ------------------------------------------------------------------

    def open_file_menu(self) -> None:
        """Press Alt+F to open the File menu."""
        self.win.focus()
        Input.key_combo(_VK_ALT, 0x46)  # Alt+F  (0x46 = 'F')
        time.sleep(self.settle_delay)

    def navigate_to_generate_turn(self) -> None:
        """Press the Down arrow *n* times, then Enter, to select Generate Turn."""
        VK_DOWN = 0x28
        for _ in range(_GENERATE_TURN_STEPS):
            Input.key(VK_DOWN)
            time.sleep(0.05)
        time.sleep(self.settle_delay)
        Input.key(Input.VK_RETURN)
        time.sleep(self.settle_delay)

    # ------------------------------------------------------------------
    # Full workflow
    # ------------------------------------------------------------------

    def generate_turn(self, timeout: float = 120.0) -> Path:
        """Trigger turn generation and wait for the new ``.m`` file.

        The method records the modification time of the existing ``.m``
        file *before* triggering generation, then polls until the mtime
        changes (indicating the host wrote a new file).

        Parameters
        ----------
        timeout:
            Maximum seconds to wait for the new ``.m`` file.

        Returns
        -------
        Path
            Path to the updated ``.m`` file.

        Raises
        ------
        FileNotFoundError
            If the ``.m`` file does not exist before starting.
        TimeoutError
            If the new ``.m`` file does not appear within *timeout* seconds.
        """
        m = self.m_file
        if not m.exists():
            raise FileNotFoundError(f".m file not found: {m}")

        old_mtime = m.stat().st_mtime

        self.open_file_menu()
        self.navigate_to_generate_turn()

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if m.stat().st_mtime != old_mtime:
                return m
            time.sleep(_POLL_INTERVAL)

        raise TimeoutError(f"New .m file did not appear within {timeout}s (watching {m})")

    def save_game(self) -> None:
        """Press Ctrl+S to save the current game state."""
        self.win.focus()
        Input.key_combo(Input.VK_CONTROL, 0x53)  # Ctrl+S
        time.sleep(self.settle_delay)
