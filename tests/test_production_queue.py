"""Tests for stars_web.binary.production_queue (Type 28 ProductionQueueBlock).

Real data sources:
  Game.m1     — 1 production queue block, 40 bytes (10 items)
  Game-big.m1 — 5 production queue blocks (48, 48, 48, 36, 48 bytes)

Block structure (variable, N × 4 bytes):
  Each 4-byte item: <H H> → (item_type, quantity)

Phases:
  1. Module constants
  2. Single-item queue (4 bytes)
  3. Multi-item queue (Game.m1  40-byte block, 10 items)
  4. Multi-item queue (Game-big.m1 48-byte block, 12 items)
  5. ProductionItem frozen / immutable
  6. ProductionQueue len / iter
  7. Error handling (empty, non-multiple-of-4)
  8. Real-data integration: Game.m1
  9. Real-data integration: Game-big.m1
  10. Property-based fuzzing
"""

import struct
from pathlib import Path

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from stars_web.binary.production_queue import (
    BLOCK_TYPE_PRODUCTION_QUEUE,
    PRODUCTION_ITEM_SIZE,
    ProductionItem,
    decode_production_queue,
    decode_production_queues,
)


# ---------------------------------------------------------------------------
# Real-data fixture bytes
# ---------------------------------------------------------------------------

# Game.m1 single Type 28 block: 40 bytes, 10 items
REAL_M1_RAW = bytes(
    [
        1,
        36,
        194,
        0,
        252,
        23,
        2,
        0,
        252,
        7,
        2,
        0,
        252,
        3,
        2,
        0,
        252,
        15,
        2,
        0,
        252,
        3,
        2,
        0,
        252,
        15,
        2,
        0,
        252,
        7,
        2,
        0,
        252,
        15,
        2,
        0,
        252,
        11,
        2,
        0,
    ]
)
REAL_M1_ITEMS = [
    (9217, 194),
    (6140, 2),
    (2044, 2),
    (1020, 2),
    (4092, 2),
    (1020, 2),
    (4092, 2),
    (2044, 2),
    (4092, 2),
    (3068, 2),
]

# Game-big.m1 first Type 28 block: 48 bytes, 12 items
REAL_BIG_M1_RAW_0 = bytes(
    [
        1,
        48,
        130,
        4,
        252,
        19,
        2,
        0,
        251,
        7,
        2,
        0,
        251,
        23,
        2,
        0,
        252,
        3,
        2,
        0,
        252,
        19,
        2,
        0,
        252,
        3,
        2,
        0,
        252,
        15,
        2,
        0,
        252,
        7,
        2,
        0,
        252,
        23,
        2,
        0,
        252,
        15,
        2,
        0,
        252,
        11,
        2,
        0,
    ]
)
REAL_BIG_M1_ITEMS_0 = [
    (12289, 1154),
    (5116, 2),
    (2043, 2),
    (6139, 2),
    (1020, 2),
    (5116, 2),
    (1020, 2),
    (4092, 2),
    (2044, 2),
    (6140, 2),
    (4092, 2),
    (3068, 2),
]

# Minimal 4-byte single-item queue (from Game-big.m11 4-byte blocks)
SINGLE_ITEM_RAW = bytes([1, 48, 2, 4])  # item_type=12289, quantity=1026
SINGLE_ITEM_RAW_2 = bytes([1, 48, 82, 1])  # item_type=12289, quantity=338


# ---------------------------------------------------------------------------
# Phase 1: Module constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_block_type_id(self):
        assert BLOCK_TYPE_PRODUCTION_QUEUE == 28

    def test_item_size(self):
        assert PRODUCTION_ITEM_SIZE == 4


# ---------------------------------------------------------------------------
# Phase 2: Single-item queue
# ---------------------------------------------------------------------------


class TestSingleItem:
    def test_one_item(self):
        pq = decode_production_queue(SINGLE_ITEM_RAW)
        assert len(pq.items) == 1

    def test_item_type(self):
        pq = decode_production_queue(SINGLE_ITEM_RAW)
        assert pq.items[0].item_type == 12289

    def test_item_quantity(self):
        pq = decode_production_queue(SINGLE_ITEM_RAW)
        assert pq.items[0].quantity == 1026

    def test_raw_preserved(self):
        pq = decode_production_queue(SINGLE_ITEM_RAW)
        assert pq.raw == SINGLE_ITEM_RAW

    def test_second_single_item(self):
        pq = decode_production_queue(SINGLE_ITEM_RAW_2)
        assert pq.items[0].item_type == 12289
        assert pq.items[0].quantity == 338


# ---------------------------------------------------------------------------
# Phase 3: 10-item queue (Game.m1 real data)
# ---------------------------------------------------------------------------


class TestTenItemQueue:
    @pytest.fixture
    def pq(self):
        return decode_production_queue(REAL_M1_RAW)

    def test_item_count(self, pq):
        assert len(pq.items) == 10

    def test_first_item_type(self, pq):
        assert pq.items[0].item_type == 9217

    def test_first_item_quantity(self, pq):
        assert pq.items[0].quantity == 194

    def test_repeated_items_quantity_2(self, pq):
        # Items 1-9 all have quantity=2
        for i in range(1, 10):
            assert pq.items[i].quantity == 2

    def test_all_items(self, pq):
        for i, (expected_type, expected_qty) in enumerate(REAL_M1_ITEMS):
            assert pq.items[i].item_type == expected_type
            assert pq.items[i].quantity == expected_qty

    def test_raw_preserved(self, pq):
        assert pq.raw == REAL_M1_RAW


# ---------------------------------------------------------------------------
# Phase 4: 12-item queue (Game-big.m1 real data)
# ---------------------------------------------------------------------------


class TestTwelveItemQueue:
    @pytest.fixture
    def pq(self):
        return decode_production_queue(REAL_BIG_M1_RAW_0)

    def test_item_count(self, pq):
        assert len(pq.items) == 12

    def test_first_item_type(self, pq):
        assert pq.items[0].item_type == 12289

    def test_first_item_quantity(self, pq):
        assert pq.items[0].quantity == 1154

    def test_all_remaining_quantity_2(self, pq):
        for i in range(1, 12):
            assert pq.items[i].quantity == 2

    def test_all_items(self, pq):
        for i, (expected_type, expected_qty) in enumerate(REAL_BIG_M1_ITEMS_0):
            assert pq.items[i].item_type == expected_type
            assert pq.items[i].quantity == expected_qty


# ---------------------------------------------------------------------------
# Phase 5: ProductionItem frozen / immutable
# ---------------------------------------------------------------------------


class TestProductionItemFrozen:
    def test_item_type_accessible(self):
        item = ProductionItem(item_type=42, quantity=100)
        assert item.item_type == 42

    def test_quantity_accessible(self):
        item = ProductionItem(item_type=42, quantity=100)
        assert item.quantity == 100

    def test_frozen_cannot_set_item_type(self):
        item = ProductionItem(item_type=42, quantity=100)
        with pytest.raises((AttributeError, TypeError)):
            item.item_type = 99  # type: ignore[misc]

    def test_frozen_cannot_set_quantity(self):
        item = ProductionItem(item_type=42, quantity=100)
        with pytest.raises((AttributeError, TypeError)):
            item.quantity = 99  # type: ignore[misc]

    def test_items_equal_when_same(self):
        a = ProductionItem(item_type=12289, quantity=1154)
        b = ProductionItem(item_type=12289, quantity=1154)
        assert a == b

    def test_items_not_equal_when_different(self):
        a = ProductionItem(item_type=1, quantity=2)
        b = ProductionItem(item_type=3, quantity=4)
        assert a != b


# ---------------------------------------------------------------------------
# Phase 6: ProductionQueue len / iter
# ---------------------------------------------------------------------------


class TestProductionQueueProtocol:
    def test_len_single(self):
        pq = decode_production_queue(SINGLE_ITEM_RAW)
        assert len(pq) == 1

    def test_len_ten(self):
        pq = decode_production_queue(REAL_M1_RAW)
        assert len(pq) == 10

    def test_iter_yields_items(self):
        pq = decode_production_queue(REAL_M1_RAW)
        items = list(pq)
        assert len(items) == 10
        assert all(isinstance(x, ProductionItem) for x in items)

    def test_iter_first_item(self):
        pq = decode_production_queue(REAL_M1_RAW)
        first = next(iter(pq))
        assert first.item_type == 9217
        assert first.quantity == 194

    def test_items_indexable(self):
        pq = decode_production_queue(REAL_M1_RAW)
        assert pq.items[5].item_type == 1020

    def test_items_is_list(self):
        pq = decode_production_queue(SINGLE_ITEM_RAW)
        assert isinstance(pq.items, list)


# ---------------------------------------------------------------------------
# Phase 7: Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    def test_empty_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            decode_production_queue(b"")

    def test_one_byte_raises(self):
        with pytest.raises(ValueError):
            decode_production_queue(b"\x01")

    def test_two_bytes_raises(self):
        with pytest.raises(ValueError, match="multiple"):
            decode_production_queue(b"\x01\x02")

    def test_three_bytes_raises(self):
        with pytest.raises(ValueError, match="multiple"):
            decode_production_queue(b"\x01\x02\x03")

    def test_five_bytes_raises(self):
        with pytest.raises(ValueError, match="multiple"):
            decode_production_queue(b"\x00" * 5)

    def test_exact_four_bytes_ok(self):
        pq = decode_production_queue(b"\x01\x02\x03\x04")
        assert len(pq) == 1

    def test_eight_bytes_ok(self):
        pq = decode_production_queue(b"\x00" * 8)
        assert len(pq) == 2


# ---------------------------------------------------------------------------
# Phase 8: Real-data integration: Game.m1
# ---------------------------------------------------------------------------

GAME_DIR = Path(__file__).parent.parent.parent / "starswine4"


@pytest.mark.skipif(not GAME_DIR.exists(), reason="starswine4 game data not found")
class TestRealGameM1:
    @pytest.fixture(scope="class")
    def queues(self):
        data = (GAME_DIR / "Game.m1").read_bytes()
        return decode_production_queues(data)

    def test_queue_count(self, queues):
        # Game.m1 has exactly 1 production queue block
        assert len(queues) == 1

    def test_first_queue_item_count(self, queues):
        assert len(queues[0]) == 10

    def test_first_queue_raw_length(self, queues):
        assert len(queues[0].raw) == 40

    def test_first_item_high_quantity(self, queues):
        # First item has quantity >> 2 (it's the main build goal)
        assert queues[0].items[0].quantity > 2

    def test_rest_items_quantity_2(self, queues):
        for item in list(queues[0])[1:]:
            assert item.quantity == 2


# ---------------------------------------------------------------------------
# Phase 9: Real-data integration: Game-big.m1
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not GAME_DIR.exists(), reason="starswine4 game data not found")
class TestRealGameBigM1:
    @pytest.fixture(scope="class")
    def queues(self):
        data = (GAME_DIR / "Game-big.m1").read_bytes()
        return decode_production_queues(data)

    def test_queue_count(self, queues):
        # Game-big.m1 player 0 has 5 production queue blocks
        assert len(queues) == 5

    def test_first_queue_item_count(self, queues):
        assert len(queues[0]) == 12

    def test_first_item_of_first_queue(self, queues):
        assert queues[0].items[0].item_type == 12289
        assert queues[0].items[0].quantity == 1154

    def test_all_queues_start_with_high_quantity_or_have_all_2(self, queues):
        # Each queue's first item drives the main production goal
        # Some queues (36-byte) start directly with quantity=2 items
        for q in queues:
            # All items with quantity>2 must come before items with quantity=2
            # (the queue is ordered: big first, then maintenance items)
            high_qty_items = [i for i in q if i.quantity > 2]
            # Either all are qty=2, or the first item is high-qty
            assert len(high_qty_items) == 0 or q.items[0].quantity > 2

    def test_raw_is_bytes(self, queues):
        for q in queues:
            assert isinstance(q.raw, bytes)

    def test_raw_length_multiple_of_4(self, queues):
        for q in queues:
            assert len(q.raw) % 4 == 0


# ---------------------------------------------------------------------------
# Phase 10: Property-based fuzzing
# ---------------------------------------------------------------------------


class TestPropertyBased:
    @given(
        types=st.lists(st.integers(0, 65535), min_size=1, max_size=20),
        quantities=st.lists(st.integers(0, 65535), min_size=1, max_size=20),
    )
    @settings(max_examples=200)
    def test_roundtrip(self, types, quantities):
        # Truncate to shorter list
        n = min(len(types), len(quantities))
        assume(n >= 1)
        raw = b"".join(struct.pack("<HH", t, q) for t, q in zip(types[:n], quantities[:n]))
        pq = decode_production_queue(raw)
        assert len(pq) == n
        for i, (t, q) in enumerate(zip(types[:n], quantities[:n])):
            assert pq.items[i].item_type == t
            assert pq.items[i].quantity == q

    @given(
        n=st.integers(1, 50).filter(lambda x: x % 4 != 0),
    )
    def test_non_multiple_raises(self, n):
        with pytest.raises(ValueError):
            decode_production_queue(b"\x00" * n)

    @given(n=st.integers(1, 15))
    def test_n_items_roundtrip_size(self, n):
        raw = b"\x01\x00\x01\x00" * n  # item_type=1, quantity=1
        pq = decode_production_queue(raw)
        assert len(pq) == n
        for item in pq:
            assert item.item_type == 1
            assert item.quantity == 1
