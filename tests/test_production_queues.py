"""Tests for Stars! production queue parsing (block type 28)."""

import struct
import pytest

from stars_web.game_state import (
    parse_production_queue_block,
    QUEUE_ITEM_NAMES,
)
from stars_web.block_reader import Block


# ── Queue item names ────────────────────────────────────────────────


class TestQueueItemNames:
    """Standard queue item names should match known IDs."""

    def test_factory_is_7(self):
        assert QUEUE_ITEM_NAMES[7] == "Factory"

    def test_mine_is_8(self):
        assert QUEUE_ITEM_NAMES[8] == "Mine"

    def test_auto_mines_is_0(self):
        assert QUEUE_ITEM_NAMES[0] == "Auto Mines"

    def test_auto_factories_is_1(self):
        assert QUEUE_ITEM_NAMES[1] == "Auto Factories"

    def test_planetary_scanner_is_27(self):
        assert QUEUE_ITEM_NAMES[27] == "Planetary Scanner"


# ── Parse queue blocks ──────────────────────────────────────────────


class TestParseProductionQueueBlock:
    """Parse production queue blocks (type 28)."""

    def _make_queue_block(self, items):
        """Build a synthetic queue block from (itemId, count, pct, itype) tuples."""
        data = bytearray()
        for item_id, count, pct, itype in items:
            chunk1 = (item_id << 10) | (count & 0x3FF)
            chunk2 = (pct << 4) | (itype & 0xF)
            data.extend(struct.pack("<H", chunk1))
            data.extend(struct.pack("<H", chunk2))
        return Block(type_id=28, size=len(data), data=bytes(data))

    def test_single_factory_item(self):
        block = self._make_queue_block([(7, 1, 89, 2)])
        items = parse_production_queue_block(block)
        assert len(items) == 1
        assert items[0].item_id == 7
        assert items[0].count == 1
        assert items[0].complete_percent == 89
        assert items[0].item_type == 2
        assert items[0].item_name == "Factory"

    def test_auto_build_items(self):
        block = self._make_queue_block(
            [
                (5, 1020, 0, 2),  # Auto Max Terraform
                (1, 1020, 0, 2),  # Auto Factories
                (0, 1020, 0, 2),  # Auto Mines
            ]
        )
        items = parse_production_queue_block(block)
        assert len(items) == 3
        assert items[0].item_name == "Auto Max Terraform"
        assert items[1].item_name == "Auto Factories"
        assert items[2].item_name == "Auto Mines"
        assert all(i.count == 1020 for i in items)

    def test_ship_design_item(self):
        """itemType=4 means a custom ship/starbase design."""
        block = self._make_queue_block([(3, 5, 0, 4)])
        items = parse_production_queue_block(block)
        assert len(items) == 1
        assert items[0].item_type == 4
        assert items[0].item_id == 3
        assert items[0].item_name == "Ship Design #3"

    def test_empty_queue(self):
        block = Block(type_id=28, size=0, data=b"")
        items = parse_production_queue_block(block)
        assert items == []

    def test_wrong_block_type_returns_none(self):
        block = Block(type_id=13, size=4, data=b"\x00" * 4)
        assert parse_production_queue_block(block) is None

    def test_completion_percentage(self):
        block = self._make_queue_block([(8, 1, 50, 2)])
        items = parse_production_queue_block(block)
        assert items[0].complete_percent == 50

    def test_max_count_10_bits(self):
        """count uses 10 bits → max 1023."""
        block = self._make_queue_block([(7, 1023, 0, 2)])
        items = parse_production_queue_block(block)
        assert items[0].count == 1023


# ── Integration: parse queues from real game file ───────────────────


class TestParseQueuesFromFile:
    """Parse production queue blocks from real Stars! game files."""

    @pytest.fixture
    def m1_queues(self):
        import os
        from stars_web.block_reader import read_blocks

        path = os.path.join("docs", "images", "original_fat_client_screenshots", "Game.m1")
        if not os.path.exists(path):
            pytest.skip("Game.m1 not found")
        data = open(path, "rb").read()
        blocks = read_blocks(data)

        # Pair queue blocks with their preceding planet
        queues = {}
        last_planet = None
        for b in blocks:
            if b.type_id in (13, 14):
                last_planet = b.data[0] | ((b.data[1] & 0x07) << 8)
            elif b.type_id == 28 and last_planet is not None:
                queues[last_planet] = parse_production_queue_block(b)
        return queues

    def test_at_least_one_queue(self, m1_queues):
        assert len(m1_queues) > 0

    def test_planet_18_has_queue(self, m1_queues):
        assert 18 in m1_queues

    def test_planet_18_has_six_items(self, m1_queues):
        assert len(m1_queues[18]) == 6

    def test_planet_18_first_item_is_factory(self, m1_queues):
        first = m1_queues[18][0]
        assert first.item_id == 7
        assert first.item_name == "Factory"
        assert first.count == 1
        assert first.complete_percent == 89

    def test_all_items_have_names(self, m1_queues):
        for planet_id, items in m1_queues.items():
            for item in items:
                assert (
                    len(item.item_name) > 0
                ), f"Planet {planet_id} queue item {item.item_id} has no name"
