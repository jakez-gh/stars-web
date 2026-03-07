"""Pytest configuration and shared fixtures for stars_web tests.

This module provides:
- Test factories for common objects (WaypointOrder, ProductionItem, etc.)
- Fixtures for game state, files, and temporary directories
- Strategies for property-based testing with Hypothesis
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import strategies as st
from stars_web.order_serializer import (
    ProductionItem,
    ProductionQueueOrder,
    WaypointOrder,
    QUEUE_ITEM_TYPE_STANDARD,
)


# ─────────────────────────────────────────────────────────────────────────────
# Strategies for property-based testing (Hypothesis)
# ─────────────────────────────────────────────────────────────────────────────


@st.composite
def waypoint_orders(draw):
    """Generate valid WaypointOrder objects for property-based tests."""
    return WaypointOrder(
        fleet_id=draw(st.integers(min_value=1, max_value=999)),
        x=draw(st.integers(min_value=0, max_value=32767)),
        y=draw(st.integers(min_value=0, max_value=32767)),
        warp=draw(st.integers(min_value=1, max_value=9)),
        task=draw(st.integers(min_value=0, max_value=255)),
        obj_id=draw(st.integers(min_value=0, max_value=999)),
        obj_type=draw(st.just(0)),  # OBJ_TYPE_PLANET
        waypoint_index=draw(st.just(0xFF)),  # append
    )


@st.composite
def production_items(draw):
    """Generate valid ProductionItem objects for property-based tests."""
    return ProductionItem(
        item_id=draw(st.integers(min_value=0, max_value=30)),
        quantity=draw(st.integers(min_value=1, max_value=1000)),
        item_type=QUEUE_ITEM_TYPE_STANDARD,
        complete_percent=draw(st.integers(min_value=0, max_value=100)),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Object factories for test setup (DRY principle)
# ─────────────────────────────────────────────────────────────────────────────


class WaypointOrderFactory:
    """Factory for creating WaypointOrder test objects."""

    @staticmethod
    def create(
        fleet_id: int = 1,
        x: int = 100,
        y: int = 200,
        warp: int = 6,
        task: int = 0,
        obj_id: int = 1,
        obj_type: int = 0,
        waypoint_index: int = 0xFF,
    ):
        """Build a WaypointOrder with custom or default values."""
        return WaypointOrder(
            fleet_id=fleet_id,
            x=x,
            y=y,
            warp=warp,
            task=task,
            obj_id=obj_id,
            obj_type=obj_type,
            waypoint_index=waypoint_index,
        )

    @staticmethod
    def batch(count: int = 5) -> list:
        """Create multiple WaypointOrders with auto-incrementing fleet_id."""
        return [
            WaypointOrderFactory.create(fleet_id=i, x=100 + i * 10, y=200 + i * 10)
            for i in range(1, count + 1)
        ]


class ProductionItemFactory:
    """Factory for creating ProductionItem test objects."""

    @staticmethod
    def create(
        item_id: int = 7,
        quantity: int = 50,
        item_type: int = 0,
        complete_percent: int = 0,
    ):
        """Build a ProductionItem with custom or default values."""
        return ProductionItem(
            item_id=item_id,
            quantity=quantity,
            item_type=item_type or QUEUE_ITEM_TYPE_STANDARD,
            complete_percent=complete_percent,
        )

    @staticmethod
    def factory():
        """Build a Factory with auto-incrementing item_id."""
        return [
            ProductionItemFactory.create(item_id=7, quantity=50),  # Factories
            ProductionItemFactory.create(item_id=8, quantity=50),  # Mines
        ]


class ProductionQueueOrderFactory:
    """Factory for creating ProductionQueueOrder test objects."""

    @staticmethod
    def create(planet_id: int = 1, items: list | None = None):
        """Build a ProductionQueueOrder with custom or default items."""
        if items is None:
            items = ProductionItemFactory.factory()

        return ProductionQueueOrder(planet_id=planet_id, items=items)


# ─────────────────────────────────────────────────────────────────────────────
# Pytest fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def game_dir() -> Path:
    """Return path to the test game directory (Game-big files)."""
    return Path(__file__).parent.parent.parent / "starswine4"


@pytest.fixture
def waypoint_factory():
    """Fixture providing WaypointOrderFactory."""
    return WaypointOrderFactory


@pytest.fixture
def production_item_factory():
    """Fixture providing ProductionItemFactory."""
    return ProductionItemFactory


@pytest.fixture
def production_queue_factory():
    """Fixture providing ProductionQueueOrderFactory."""
    return ProductionQueueOrderFactory


# ─────────────────────────────────────────────────────────────────────────────
# Sidecar isolation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_sidecar(request, monkeypatch):
    """Stub sidecar read/write for all tests except those marked 'uses_sidecar'.

    Tests running in parallel with pytest-xdist share ``TEST_DATA_DIR``.
    Without this fixture, mutation tests (POST waypoints / production / research)
    write ``.orders_pending.json`` into that directory.  When a concurrent worker
    then calls ``create_app(TEST_DATA_DIR)``, ``_load_pending_orders`` reads the
    sidecar and populates the pending dicts, causing spurious "has_pending_orders
    is True" assertions in tests that expect a clean state.

    Tests that explicitly verify sidecar on-disk behaviour must opt in with
    ``@pytest.mark.uses_sidecar``.
    """
    if request.node.get_closest_marker("uses_sidecar"):
        return  # Real sidecar I/O for sidecar-specific tests

    import stars_web.app as app_mod

    monkeypatch.setattr(app_mod, "_save_pending_orders", lambda _app: None)
    monkeypatch.setattr(app_mod, "_load_pending_orders", lambda _app: None)
