"""Tests for stars_web.binary.fleet_order (Type 20 FleetOrderBlock).

Real data sources:
  Game.m1     — 8 fleets, all targeted (order_type=17), targeting planets 29,24,16,14,10,11,15,20
  Game-big.m1 — 5 fleets, all targeted (order_type=17), targeting planet 307 (multiple times)
  Game-big.m2 — mix of targeted and open-space (order_type=17 and 20)

Block structure (8 bytes fixed):
  <H H H B B> → dest_x, dest_y, target_id, flags, order_type

Phases:
  1. Module constants
  2. Single targeted decode (Game.m1)
  3. Single open-space decode (Game-big.m2)
  4. Properties: is_targeted / is_open_space
  5. Multiple flags values
  6. Error handling (wrong size)
  7. Real-data integration: Game.m1 (all 8 fleets)
  8. Real-data integration: Game-big.m1 (first 5 fleets, all targeted)
  9. Property-based fuzzing
"""

import struct
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from stars_web.binary.fleet_order import (
    BLOCK_TYPE_FLEET_ORDER,
    FLEET_ORDER_SIZE,
    ORDER_TYPE_OPEN_SPACE,
    ORDER_TYPE_TARGETED,
    decode_fleet_order,
    decode_fleet_orders,
)


# ---------------------------------------------------------------------------
# Real-data fixtures
# ---------------------------------------------------------------------------

# Game.m1 first Type 20 block: x=1361, y=1132, target=29, flags=0x40, type=17
REAL_M1_BLOCK_0 = bytes([81, 5, 108, 4, 29, 0, 64, 17])
# Game.m1 last Type 20 block:  x=1273, y=1183, target=20, flags=0x50, type=17
REAL_M1_BLOCK_7 = bytes([249, 4, 159, 4, 20, 0, 80, 17])

# Game-big.m1 first Type 20 block: x=1644, y=2877, target=307, flags=0x00, type=17
REAL_BIG_M1_BLOCK_0 = bytes([108, 6, 61, 11, 51, 1, 0, 17])
# Game-big.m1 second block same coords, flags=0x40
REAL_BIG_M1_BLOCK_1 = bytes([108, 6, 61, 11, 51, 1, 64, 17])

# Game-big.m2 second Type 20 block: x=1789, y=2316, target=0, flags=0x50, type=20 (open space)
REAL_BIG_M2_OPEN_0 = bytes([253, 6, 12, 9, 0, 0, 80, 20])
# Game-big.m2 third Type 20 block: x=1796, y=2329, target=0, flags=0x50, type=20 (open space)
REAL_BIG_M2_OPEN_1 = bytes([4, 7, 25, 9, 0, 0, 80, 20])


# ---------------------------------------------------------------------------
# Phase 1: Module constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_block_type_id(self):
        assert BLOCK_TYPE_FLEET_ORDER == 20

    def test_fleet_order_size(self):
        assert FLEET_ORDER_SIZE == 8

    def test_order_type_targeted(self):
        assert ORDER_TYPE_TARGETED == 0x11

    def test_order_type_open_space(self):
        assert ORDER_TYPE_OPEN_SPACE == 0x14

    def test_order_types_differ(self):
        assert ORDER_TYPE_TARGETED != ORDER_TYPE_OPEN_SPACE


# ---------------------------------------------------------------------------
# Phase 2: Single targeted decode
# ---------------------------------------------------------------------------


class TestDecodeTargeted:
    def test_dest_x(self):
        fo = decode_fleet_order(REAL_M1_BLOCK_0)
        assert fo.dest_x == 1361

    def test_dest_y(self):
        fo = decode_fleet_order(REAL_M1_BLOCK_0)
        assert fo.dest_y == 1132

    def test_target_id(self):
        fo = decode_fleet_order(REAL_M1_BLOCK_0)
        assert fo.target_id == 29

    def test_flags(self):
        fo = decode_fleet_order(REAL_M1_BLOCK_0)
        assert fo.flags == 0x40

    def test_order_type(self):
        fo = decode_fleet_order(REAL_M1_BLOCK_0)
        assert fo.order_type == ORDER_TYPE_TARGETED

    def test_raw_preserved(self):
        fo = decode_fleet_order(REAL_M1_BLOCK_0)
        assert fo.raw == REAL_M1_BLOCK_0

    def test_second_block(self):
        fo = decode_fleet_order(REAL_M1_BLOCK_7)
        assert fo.dest_x == 1273
        assert fo.dest_y == 1183
        assert fo.target_id == 20
        assert fo.flags == 0x50

    def test_big_game_target_307(self):
        fo = decode_fleet_order(REAL_BIG_M1_BLOCK_0)
        assert fo.dest_x == 1644
        assert fo.dest_y == 2877
        assert fo.target_id == 307
        assert fo.flags == 0x00

    def test_big_game_flags_0x40(self):
        fo = decode_fleet_order(REAL_BIG_M1_BLOCK_1)
        assert fo.flags == 0x40
        assert fo.target_id == 307


# ---------------------------------------------------------------------------
# Phase 3: Open-space decode
# ---------------------------------------------------------------------------


class TestDecodeOpenSpace:
    def test_target_id_zero(self):
        fo = decode_fleet_order(REAL_BIG_M2_OPEN_0)
        assert fo.target_id == 0

    def test_dest_coords(self):
        fo = decode_fleet_order(REAL_BIG_M2_OPEN_0)
        assert fo.dest_x == 1789
        assert fo.dest_y == 2316

    def test_order_type(self):
        fo = decode_fleet_order(REAL_BIG_M2_OPEN_0)
        assert fo.order_type == ORDER_TYPE_OPEN_SPACE

    def test_flags(self):
        fo = decode_fleet_order(REAL_BIG_M2_OPEN_0)
        assert fo.flags == 0x50

    def test_raw_preserved(self):
        fo = decode_fleet_order(REAL_BIG_M2_OPEN_0)
        assert fo.raw == REAL_BIG_M2_OPEN_0

    def test_second_open_space_block(self):
        fo = decode_fleet_order(REAL_BIG_M2_OPEN_1)
        assert fo.dest_x == 1796
        assert fo.dest_y == 2329
        assert fo.target_id == 0


# ---------------------------------------------------------------------------
# Phase 4: Properties
# ---------------------------------------------------------------------------


class TestProperties:
    def test_is_targeted_true_when_order_type_0x11(self):
        fo = decode_fleet_order(REAL_M1_BLOCK_0)
        assert fo.is_targeted is True

    def test_is_targeted_false_when_order_type_0x14(self):
        fo = decode_fleet_order(REAL_BIG_M2_OPEN_0)
        assert fo.is_targeted is False

    def test_is_open_space_true_when_order_type_0x14(self):
        fo = decode_fleet_order(REAL_BIG_M2_OPEN_0)
        assert fo.is_open_space is True

    def test_is_open_space_false_when_order_type_0x11(self):
        fo = decode_fleet_order(REAL_M1_BLOCK_0)
        assert fo.is_open_space is False

    def test_targeted_and_open_are_exclusive(self):
        for raw in [REAL_M1_BLOCK_0, REAL_BIG_M2_OPEN_0]:
            fo = decode_fleet_order(raw)
            assert fo.is_targeted != fo.is_open_space


# ---------------------------------------------------------------------------
# Phase 5: Various flags values
# ---------------------------------------------------------------------------


def _make_order(x=100, y=200, target=0, flags=0, order_type=ORDER_TYPE_OPEN_SPACE):
    return struct.pack("<HHHBB", x, y, target, flags, order_type)


class TestFlagsVariants:
    @pytest.mark.parametrize(
        "flags",
        [0x00, 0x40, 0x50, 0x60, 0x70, 0x80, 0x90],
    )
    def test_flags_round_trip(self, flags):
        raw = _make_order(flags=flags)
        fo = decode_fleet_order(raw)
        assert fo.flags == flags

    def test_zero_flags(self):
        raw = _make_order(flags=0x00, target=42, order_type=ORDER_TYPE_TARGETED)
        fo = decode_fleet_order(raw)
        assert fo.flags == 0x00

    def test_any_flags_preserved_in_raw(self):
        for flags in [0x30, 0x40, 0xA0]:
            raw = _make_order(flags=flags)
            fo = decode_fleet_order(raw)
            assert fo.raw[6] == flags


# ---------------------------------------------------------------------------
# Phase 6: Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    def test_empty_raises(self):
        with pytest.raises(ValueError, match="8 bytes"):
            decode_fleet_order(b"")

    def test_too_short_raises(self):
        with pytest.raises(ValueError, match="8 bytes"):
            decode_fleet_order(b"\x00" * 7)

    def test_too_long_raises(self):
        with pytest.raises(ValueError, match="8 bytes"):
            decode_fleet_order(b"\x00" * 9)

    def test_exact_size_does_not_raise(self):
        decode_fleet_order(b"\x00" * 8)  # should not raise


# ---------------------------------------------------------------------------
# Phase 7: Real-data integration: Game.m1
# ---------------------------------------------------------------------------

GAME_DIR = Path(__file__).parent.parent.parent / "starswine4"


@pytest.mark.skipif(not GAME_DIR.exists(), reason="starswine4 game data not found")
class TestRealGameM1:
    @pytest.fixture(scope="class")
    def orders(self):
        data = (GAME_DIR / "Game.m1").read_bytes()
        return decode_fleet_orders(data)

    def test_fleet_order_count(self, orders):
        # Game.m1 = 2-player game, player 0 has 8 fleets = 8 orders
        assert len(orders) == 8

    def test_all_are_targeted(self, orders):
        assert all(o.is_targeted for o in orders)

    def test_no_open_space_orders(self, orders):
        assert not any(o.is_open_space for o in orders)

    def test_all_have_nonzero_target(self, orders):
        assert all(o.target_id > 0 for o in orders)

    def test_first_order_coords(self, orders):
        # [81,5,108,4,29,0,64,17] → x=1361, y=1132, target=29
        assert orders[0].dest_x == 1361
        assert orders[0].dest_y == 1132
        assert orders[0].target_id == 29

    def test_last_order_coords(self, orders):
        # [249,4,159,4,20,0,80,17] → x=1273, y=1183, target=20
        assert orders[7].dest_x == 1273
        assert orders[7].dest_y == 1183
        assert orders[7].target_id == 20

    def test_all_order_types_are_0x11(self, orders):
        assert all(o.order_type == ORDER_TYPE_TARGETED for o in orders)

    def test_raw_length(self, orders):
        for o in orders:
            assert len(o.raw) == FLEET_ORDER_SIZE


# ---------------------------------------------------------------------------
# Phase 8: Real-data integration: Game-big.m1
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not GAME_DIR.exists(), reason="starswine4 game data not found")
class TestRealGameBigM1:
    @pytest.fixture(scope="class")
    def orders(self):
        data = (GAME_DIR / "Game-big.m1").read_bytes()
        return decode_fleet_orders(data)

    def test_fleet_order_count(self, orders):
        # Game-big.m1 has 5 fleets for player 0
        assert len(orders) == 5

    def test_all_targeted(self, orders):
        assert all(o.is_targeted for o in orders)

    def test_target_id_is_307(self, orders):
        # All fleets target planet 307
        assert all(o.target_id == 307 for o in orders)

    def test_coordinates(self, orders):
        assert all(o.dest_x == 1644 for o in orders)
        assert all(o.dest_y == 2877 for o in orders)

    def test_flags_vary(self, orders):
        flag_values = {o.flags for o in orders}
        assert len(flag_values) > 1  # multiple distinct flag values


# ---------------------------------------------------------------------------
# Phase 9: Property-based fuzzing
# ---------------------------------------------------------------------------


class TestPropertyBased:
    @given(
        x=st.integers(0, 65535),
        y=st.integers(0, 65535),
        target=st.integers(0, 65535),
        flags=st.integers(0, 255),
        order_type=st.integers(0, 255),
    )
    @settings(max_examples=200)
    def test_roundtrip(self, x, y, target, flags, order_type):
        raw = struct.pack("<HHHBB", x, y, target, flags, order_type)
        fo = decode_fleet_order(raw)
        assert fo.dest_x == x
        assert fo.dest_y == y
        assert fo.target_id == target
        assert fo.flags == flags
        assert fo.order_type == order_type
        assert fo.raw == raw

    @given(n=st.integers(0, 7).filter(lambda n: n != 8))
    def test_wrong_size_always_raises(self, n):
        with pytest.raises(ValueError):
            decode_fleet_order(b"\x00" * n)

    @given(
        x=st.integers(0, 65535),
        y=st.integers(0, 65535),
    )
    def test_coords_preserved(self, x, y):
        raw = struct.pack("<HHHBB", x, y, 0, 0, ORDER_TYPE_OPEN_SPACE)
        fo = decode_fleet_order(raw)
        assert fo.dest_x == x
        assert fo.dest_y == y
