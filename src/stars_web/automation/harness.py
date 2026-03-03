"""Autonomous turn harness: read game state, decide, issue orders, generate turn.

This module implements the MA3 milestone: a full autonomous turn cycle that
operates without human intervention.  The :class:`DecisionEngine` applies
simple heuristic rules; the :class:`AutonomousHarness` coordinates the loop.

Architecture
------------
::

    AutonomousHarness
        ├── GameState loader   (stars_web.game_state)
        ├── DecisionEngine     (rule-based orders)
        ├── order_serializer   (write .x1 binary)
        └── Launcher / Screen  (optional GUI verification)

Usage::

    from pathlib import Path
    from stars_web.automation.harness import AutonomousHarness

    harness = AutonomousHarness(
        game_dir=Path("starswine4"),
        game_prefix="Game",
        player_number=1,
    )
    harness.play_turn()       # one turn
    harness.play_turns(n=5)   # n turns
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from stars_web.order_serializer import (
    QUEUE_ITEM_TYPE_STANDARD,
    WaypointOrder,
    build_order_file,
)

if TYPE_CHECKING:
    from stars_web.game_state import Fleet, GameState, Planet

# Production queue item IDs (from QUEUE_ITEM_IDS)
_ITEM_FACTORY = 7
_ITEM_MINE = 8
_ITEM_AUTO_FACTORIES = 1
_ITEM_AUTO_MINES = 0

# Warp factor used for unassigned fleet waypoints
_DEFAULT_WARP = 6


# ---------------------------------------------------------------------------
# AI decision layer
# ---------------------------------------------------------------------------


@dataclass
class ProductionDecision:
    """Decision: change a planet's production queue."""

    planet_id: int
    items: list[dict] = field(default_factory=list)
    """List of ``{name, quantity}`` dicts for the new queue."""


@dataclass
class WaypointDecision:
    """Decision: add a waypoint to a fleet."""

    fleet_id: int
    target_x: int
    target_y: int
    warp: int
    obj_id: int
    obj_type: int  # OBJ_TYPE_PLANET or OBJ_TYPE_DEEP_SPACE


@dataclass
class TurnDecisions:
    """All decisions made for a single turn."""

    production: list[ProductionDecision] = field(default_factory=list)
    waypoints: list[WaypointDecision] = field(default_factory=list)


class DecisionEngine:
    """Simple rule-based AI decision engine.

    Rules
    -----
    Production:
      - Planets with fewer factories than mines get ``Auto Factories`` queued.
      - Planets with fewer mines than factories get ``Auto Mines`` queued.
      - If factories == mines, queue both in equal proportion.

    Waypoints:
      - Fleets with no waypoints are sent to the nearest owned planet.
    """

    def __init__(self, player_index: int = 0) -> None:
        self.player_index = player_index

    def decide(self, game_state: GameState) -> TurnDecisions:
        """Analyse *game_state* and return a :class:`TurnDecisions` object."""
        decisions = TurnDecisions()

        owned_planets = [p for p in game_state.planets if p.owner == self.player_index]
        owned_fleets = [f for f in game_state.fleets if f.owner == self.player_index]

        for planet in owned_planets:
            prod = self._decide_production(planet)
            if prod:
                decisions.production.append(prod)

        for fleet in owned_fleets:
            wp = self._decide_waypoint(fleet, owned_planets)
            if wp:
                decisions.waypoints.append(wp)

        return decisions

    # ------------------------------------------------------------------
    # Production heuristic
    # ------------------------------------------------------------------

    def _decide_production(self, planet: Planet) -> ProductionDecision | None:
        """Return a production queue change if the planet needs one."""
        factories = planet.factories
        mines = planet.mines

        if factories == 0 and mines == 0:
            # New colony: build factories first
            items = [
                {"name": "Auto Factories", "quantity": 10},
                {"name": "Auto Mines", "quantity": 10},
            ]
        elif factories < mines:
            items = [
                {"name": "Auto Factories", "quantity": 10},
                {"name": "Auto Mines", "quantity": 5},
            ]
        elif mines < factories:
            items = [
                {"name": "Auto Mines", "quantity": 10},
                {"name": "Auto Factories", "quantity": 5},
            ]
        else:
            # Balanced — no change needed
            return None

        return ProductionDecision(planet_id=planet.planet_id, items=items)

    # ------------------------------------------------------------------
    # Waypoint heuristic
    # ------------------------------------------------------------------

    def _decide_waypoint(
        self, fleet: Fleet, owned_planets: list[Planet]
    ) -> WaypointDecision | None:
        """Return a waypoint decision for a fleet that has no waypoints."""
        if fleet.waypoints:
            return None  # already has orders
        if not owned_planets:
            return None

        # Find nearest owned planet
        nearest = min(
            owned_planets,
            key=lambda p: math.hypot(p.x - fleet.x, p.y - fleet.y),
        )
        # Don't issue a null-move (fleet already on planet)
        if nearest.x == fleet.x and nearest.y == fleet.y:
            return None

        from stars_web.order_serializer import OBJ_TYPE_PLANET

        return WaypointDecision(
            fleet_id=fleet.fleet_id,
            target_x=nearest.x,
            target_y=nearest.y,
            warp=_DEFAULT_WARP,
            obj_id=nearest.planet_id,
            obj_type=OBJ_TYPE_PLANET,
        )


# ---------------------------------------------------------------------------
# Order builder
# ---------------------------------------------------------------------------


def build_orders(
    decisions: TurnDecisions,
    m1_header: bytes,
) -> bytes:
    """Convert *decisions* into a binary ``.x1`` file."""
    from stars_web.order_serializer import (
        ProductionItem,
        ProductionQueueOrder,
    )

    # Convert ProductionDecisions to ProductionQueueOrder objects
    production_orders: list[ProductionQueueOrder] = []
    for pd in decisions.production:
        items = [
            ProductionItem(
                item_id=_name_to_id(item["name"]),
                quantity=item["quantity"],
                item_type=QUEUE_ITEM_TYPE_STANDARD,
                complete_percent=0,
            )
            for item in pd.items
        ]
        order = ProductionQueueOrder(planet_id=pd.planet_id, items=items)
        production_orders.append(order)

    # Convert WaypointDecisions to WaypointOrder objects
    waypoint_orders: list[WaypointOrder] = []
    for wd in decisions.waypoints:
        order = WaypointOrder(
            fleet_id=wd.fleet_id,
            x=wd.target_x,
            y=wd.target_y,
            warp=wd.warp,
            task=0,
            obj_id=wd.obj_id,
        )
        waypoint_orders.append(order)

    # Use build_order_file to handle encryption and file building
    return build_order_file(
        source_header_bytes=m1_header,
        waypoint_orders=waypoint_orders,
        production_orders=production_orders,
    )


def _name_to_id(name: str) -> int:
    from stars_web.order_serializer import QUEUE_ITEM_IDS

    return QUEUE_ITEM_IDS[name]


# ---------------------------------------------------------------------------
# Autonomous harness
# ---------------------------------------------------------------------------


class AutonomousHarness:
    """Coordinate the full autonomous turn cycle.

    Parameters
    ----------
    game_dir:
        Path to the directory containing the Stars! game files.
    game_prefix:
        Game file name prefix (e.g. ``"Game"`` → ``Game.m1``, ``Game.x1``).
    player_number:
        The player number whose files to read/write (e.g. ``1``).
    player_index:
        Zero-based player index used in game state (usually ``player_number - 1``).
    """

    def __init__(
        self,
        game_dir: str | Path,
        game_prefix: str,
        player_number: int = 1,
        player_index: int = 0,
    ) -> None:
        self.game_dir = Path(game_dir)
        self.game_prefix = game_prefix
        self.player_number = player_number
        self.player_index = player_index
        self.engine = DecisionEngine(player_index=player_index)

    @property
    def m_file(self) -> Path:
        return self.game_dir / f"{self.game_prefix}.m{self.player_number}"

    @property
    def x1_file(self) -> Path:
        return self.game_dir / f"{self.game_prefix}.x{self.player_number}"

    def load_game_state(self) -> GameState:
        """Parse the current ``.m`` file and return a :class:`GameState`."""
        from stars_web.game_state import load_game

        return load_game(str(self.game_dir), player=self.player_number)

    def play_turn(self) -> TurnDecisions:
        """Execute a single autonomous turn.

        1. Load game state from ``.m`` file.
        2. Run decision engine.
        3. Build and write ``.x1`` order file.

        Returns
        -------
        TurnDecisions
            The decisions that were issued this turn.
        """
        game_state = self.load_game_state()
        decisions = self.engine.decide(game_state)

        # Read the existing .x1 (or .m1) file to extract the file header
        x1_path = self.x1_file
        if x1_path.exists():
            with open(x1_path, "rb") as f:
                existing_bytes = f.read()
        else:
            # Fall back to reading the m-file
            with open(self.m_file, "rb") as f:
                existing_bytes = f.read()

        # Extract the FILE_HEADER block (first 16 bytes after the 2-byte block header)
        from stars_web.block_reader import read_blocks

        blocks = read_blocks(existing_bytes)
        if not blocks or blocks[0].file_header is None:
            raise ValueError("Could not extract file header from game file")

        # Get the raw 16-byte header data from the first block
        header_bytes = blocks[0].data

        # build_orders needs just the raw 16-byte FILE_HEADER payload
        x1_bytes = build_orders(decisions, header_bytes)
        with open(x1_path, "wb") as f:
            f.write(x1_bytes)

        return decisions

    def play_turns(self, n: int) -> list[TurnDecisions]:
        """Call :meth:`play_turn` *n* times and return all decisions.

        Parameters
        ----------
        n:
            Number of turns to play autonomously.
        """
        all_decisions: list[TurnDecisions] = []
        for _ in range(n):
            decisions = self.play_turn()
            all_decisions.append(decisions)
        return all_decisions
