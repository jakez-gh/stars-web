"""Test Suite for Fleet Block Parsing (Tier-1 Binary Parsing)

Block Types: 16 (full/own fleet) and 17 (partial/enemy fleet)
Purpose: Parse fleet position, ship composition, owner, and waypoint count.
Location: In .m# player files alongside other game-state blocks.

Related Issues: Tier-1 binary parsing work
Pattern: Test-driven development

References:
  - docs/file-format-discovery.md (section 10)
  - starswine4/Game.m1, Game-big.m1 (real test data)
  - stars_web/game_state.py _parse_fleet_block() (existing inline parser)
  - stars-4x/starsapi-python BLOCKS dict: type 16="FleetBlock", 17="PartialFleetBlock"
"""

import struct

import pytest
from hypothesis import given, settings, strategies as st

from stars_web.binary.fleet import (
    FleetDetail,
    decode_fleet,
    decode_fleets,
    BLOCK_TYPE_FLEET_FULL,
    BLOCK_TYPE_FLEET_PARTIAL,
    FLEET_KIND_WRITE,
    FLEET_KIND_CARGO,
    FLEET_KIND_FULL,
)


# ─────────────────────────────────────────────────────────────────────────────
# Real binary fixtures (decrypted, extracted from starswine4/ game files)
# ─────────────────────────────────────────────────────────────────────────────

# ── starswine4/Game.m1 (2-player game) ──────────────────────────────────────

# Fleet #1: size=22, fleet_id=1, owner=0, flags=0x09 (1-byte ship counts)
# orbit=29, x=1361, y=1132, mask=0x0002 (design slot 1),
# ship_count[1]=1, wp_count=7
M1_FLEET_1 = bytes(
    [
        1,
        0,
        0,
        0,  # d[0-3]: fleet_id=1, owner=0, unknown
        7,
        9,  # d[4-5]: kind=7, flags=0x09 (bit3 SET→1-byte counts)
        29,
        0,  # d[6-7]: orbit_planet_id=29
        81,
        5,  # d[8-9]: x=1361
        108,
        4,  # d[10-11]: y=1132
        2,
        0,  # d[12-13]: ship_designs_mask=0x0002
        1,  # d[14]: design slot 1 count = 1
        0,
        1,
        248,
        0,
        0,
        0,  # d[15-20]: extra bytes (fuel etc., unparsed)
        7,  # d[21]: wp_count = 7
    ]
)

# Fleet #3: size=25, fleet_id=3, owner=0, flags=0x2b (1-byte counts, bit5 set)
# orbit=20, x=1273, y=1183, mask=0x0008 (design slot 3),
# ship_count[3]=1, wp_count=3
M1_FLEET_3 = bytes(
    [
        3,
        0,
        0,
        0,  # fleet_id=3, owner=0, unknown
        7,
        43,  # kind=7, flags=0x2b
        20,
        0,  # orbit_planet_id=20
        249,
        4,  # x=1273
        159,
        4,  # y=1183
        8,
        0,  # ship_designs_mask=0x0008
        1,  # design slot 3 count = 1
        17,
        2,
        89,
        6,
        159,
        1,
        0,
        0,
        0,  # extra bytes (9 bytes)
        3,  # wp_count = 3
    ]
)

# Fleet #5: size=22, fleet_id=5, owner=0, flags=0x29 (1-byte counts)
# orbit=20, x=1273, y=1183, mask=0x0020 (design slot 5), ship_count[5]=1, wp_count=1
M1_FLEET_5 = bytes(
    [
        5,
        0,
        0,
        0,  # fleet_id=5, owner=0, unknown
        7,
        41,  # kind=7, flags=0x29
        20,
        0,  # orbit_planet_id=20
        249,
        4,  # x=1273
        159,
        4,  # y=1183
        32,
        0,  # ship_designs_mask=0x0020
        1,  # design slot 5 count = 1
        0,
        1,
        210,
        0,
        0,
        0,  # extra bytes (6 bytes)
        1,  # wp_count = 1
    ]
)

# ── starswine4/Game-big.m1 (16-player game) ─────────────────────────────────

# Fleet #0: size=22, fleet_id=0, owner=0, flags=0x49 (1-byte ship counts)
# orbit=307, x=1644, y=2877, mask=0x0001 (design slot 0), ship_count[0]=1, wp_count=1
BIG_FLEET_0 = bytes(
    [
        0,
        0,
        0,
        0,  # fleet_id=0, owner=0, unknown
        7,
        73,  # kind=7, flags=0x49
        51,
        1,  # orbit_planet_id=307
        108,
        6,  # x=1644
        61,
        11,  # y=2877
        1,
        0,  # ship_designs_mask=0x0001
        1,  # design slot 0 count = 1
        0,
        1,
        50,
        0,
        0,
        0,  # extra bytes (6 bytes)
        1,  # wp_count = 1
    ]
)

# Fleet #1: size=23, fleet_id=1, owner=0, flags=0x69 (1-byte ship counts)
# orbit=307, x=1644, y=2877, mask=0x0200 (design slot 9), ship_count[9]=1, wp_count=1
BIG_FLEET_1 = bytes(
    [
        1,
        0,
        0,
        0,  # fleet_id=1, owner=0, unknown
        7,
        105,  # kind=7, flags=0x69
        51,
        1,  # orbit_planet_id=307
        108,
        6,  # x=1644
        61,
        11,  # y=2877
        0,
        2,  # ship_designs_mask=0x0200
        1,  # design slot 9 count = 1
        0,
        2,
        204,
        1,
        0,
        0,
        0,  # extra bytes (7 bytes)
        1,  # wp_count = 1
    ]
)

# Fleet #2: size=23, fleet_id=2, owner=0, flags=0x69
# orbit=307, x=1644, y=2877, mask=0x0040 (design slot 6), ship_count[6]=1, wp_count=1
BIG_FLEET_2 = bytes(
    [
        2,
        0,
        0,
        0,
        7,
        105,
        51,
        1,
        108,
        6,
        61,
        11,
        64,
        0,  # ship_designs_mask=0x0040
        1,
        0,
        2,
        188,
        2,
        0,
        0,
        0,
        1,
    ]
)

# Fleet #9: size=22, fleet_id=9, owner=0, flags=0x69
# orbit=307, x=1644, y=2877, mask=0x0004 (design slot 2), ship_count[2]=1, wp_count=1
BIG_FLEET_9 = bytes(
    [
        9,
        0,
        0,
        0,
        7,
        105,
        51,
        1,
        108,
        6,
        61,
        11,
        4,
        0,  # ship_designs_mask=0x0004
        1,
        0,
        1,
        200,
        0,
        0,
        0,
        1,
    ]
)


def _make_minimal_fleet(
    fleet_id=0,
    owner=0,
    kind=7,
    flags=0x09,
    orbit=0,
    x=0,
    y=0,
    mask=0,
    ship_counts: list[int] | None = None,
    extra: bytes = b"",
    wp_count: int = 0,
) -> bytes:
    """Build a synthetic Type-16 block payload for testing."""
    hdr = bytes(
        [
            fleet_id & 0xFF,
            ((fleet_id >> 8) & 0x01) | ((owner & 0x7F) << 1),
            0,
            0,  # unknown
            kind,
            flags,
        ]
    )
    hdr += struct.pack("<H", orbit)
    hdr += struct.pack("<H", x)
    hdr += struct.pack("<H", y)
    hdr += struct.pack("<H", mask)

    one_byte = bool(flags & 0x08)
    counts_bytes = b""
    if ship_counts:
        for c in ship_counts:
            if one_byte:
                counts_bytes += bytes([c & 0xFF])
            else:
                counts_bytes += struct.pack("<H", c)
    return hdr + counts_bytes + extra + bytes([wp_count])


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Constants and dataclass structure
# ─────────────────────────────────────────────────────────────────────────────


class TestConstants:
    """Verify module-level constants."""

    def test_block_type_fleet_full_value(self):
        assert BLOCK_TYPE_FLEET_FULL == 16

    def test_block_type_fleet_partial_value(self):
        assert BLOCK_TYPE_FLEET_PARTIAL == 17

    def test_fleet_kind_write(self):
        assert FLEET_KIND_WRITE == 0

    def test_fleet_kind_cargo(self):
        assert FLEET_KIND_CARGO == 4

    def test_fleet_kind_full(self):
        assert FLEET_KIND_FULL == 7

    def test_distinct_block_types(self):
        assert BLOCK_TYPE_FLEET_FULL != BLOCK_TYPE_FLEET_PARTIAL


class TestFleetDetailDataclass:
    """Verify FleetDetail dataclass fields and defaults."""

    def test_can_construct_with_required_fields(self):
        fd = FleetDetail(
            fleet_id=0,
            owner=0,
            kind=7,
            flags=0,
            orbit_planet_id=0,
            x=0,
            y=0,
            ship_designs_mask=0,
        )
        assert fd.fleet_id == 0

    def test_ship_counts_defaults_empty(self):
        fd = FleetDetail(
            fleet_id=1,
            owner=0,
            kind=7,
            flags=0,
            orbit_planet_id=0,
            x=10,
            y=20,
            ship_designs_mask=0,
        )
        assert fd.ship_counts == {}

    def test_total_ship_count_defaults_zero(self):
        fd = FleetDetail(
            fleet_id=1,
            owner=0,
            kind=7,
            flags=0,
            orbit_planet_id=0,
            x=0,
            y=0,
            ship_designs_mask=0,
        )
        assert fd.total_ship_count == 0

    def test_wp_count_defaults_zero(self):
        fd = FleetDetail(
            fleet_id=0,
            owner=0,
            kind=0,
            flags=0,
            orbit_planet_id=0,
            x=0,
            y=0,
            ship_designs_mask=0,
        )
        assert fd.wp_count == 0

    def test_is_full_defaults_true(self):
        fd = FleetDetail(
            fleet_id=0,
            owner=0,
            kind=7,
            flags=0,
            orbit_planet_id=0,
            x=0,
            y=0,
            ship_designs_mask=0,
        )
        assert fd.is_full is True

    def test_extra_bytes_defaults_empty(self):
        fd = FleetDetail(
            fleet_id=0,
            owner=0,
            kind=7,
            flags=0,
            orbit_planet_id=0,
            x=0,
            y=0,
            ship_designs_mask=0,
        )
        assert fd.extra_bytes == b""

    def test_can_set_partial_fleet(self):
        fd = FleetDetail(
            fleet_id=5,
            owner=3,
            kind=7,
            flags=0,
            orbit_planet_id=0,
            x=0,
            y=0,
            ship_designs_mask=0x0001,
            is_full=False,
        )
        assert fd.is_full is False


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Header parsing
# ─────────────────────────────────────────────────────────────────────────────


class TestHeaderParsing:
    """Verify fixed 14-byte header is decoded correctly."""

    def test_fleet_id_low_byte(self):
        data = _make_minimal_fleet(fleet_id=5, ship_counts=[1], extra=b"\x00\x01\x00\x00\x00")
        f = decode_fleet(data)
        assert f.fleet_id == 5

    def test_fleet_id_high_bit(self):
        # fleet_id=256 → byte0=0, byte1 bit0=1
        data = _make_minimal_fleet(fleet_id=256, ship_counts=[], extra=b"")
        f = decode_fleet(data)
        assert f.fleet_id == 256

    def test_owner_extracted_from_byte1(self):
        # owner=3 → byte1 bits[7:1] = 0b0000011 → byte1 = 0x06 (no fleet_id high bit)
        data = _make_minimal_fleet(owner=3, ship_counts=[], extra=b"")
        f = decode_fleet(data)
        assert f.owner == 3

    def test_kind_byte(self):
        data = _make_minimal_fleet(kind=4, ship_counts=[], extra=b"")
        # kind != 7 means no wp_count at end
        f = decode_fleet(data)
        assert f.kind == 4

    def test_flags_byte(self):
        data = _make_minimal_fleet(flags=0x2B, ship_counts=[], extra=b"")
        f = decode_fleet(data)
        assert f.flags == 0x2B

    def test_orbit_planet_id(self):
        data = _make_minimal_fleet(orbit=307, ship_counts=[], extra=b"")
        f = decode_fleet(data)
        assert f.orbit_planet_id == 307

    def test_x_position(self):
        data = _make_minimal_fleet(x=1361, ship_counts=[], extra=b"")
        f = decode_fleet(data)
        assert f.x == 1361

    def test_y_position(self):
        data = _make_minimal_fleet(y=2877, ship_counts=[], extra=b"")
        f = decode_fleet(data)
        assert f.y == 2877

    def test_ship_designs_mask(self):
        data = _make_minimal_fleet(mask=0x0200, ship_counts=[1])
        f = decode_fleet(data)
        assert f.ship_designs_mask == 0x0200

    def test_is_full_true_for_type16(self):
        data = _make_minimal_fleet(ship_counts=[], extra=b"")
        f = decode_fleet(data, BLOCK_TYPE_FLEET_FULL)
        assert f.is_full is True

    def test_is_full_false_for_type17(self):
        data = _make_minimal_fleet(ship_counts=[], extra=b"")
        f = decode_fleet(data, BLOCK_TYPE_FLEET_PARTIAL)
        assert f.is_full is False


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: Ship count decoding (1-byte vs 2-byte paths)
# ─────────────────────────────────────────────────────────────────────────────


class TestShipCountDecoding:
    """Verify variable-length ship count section is decoded correctly."""

    def test_one_byte_counts_when_bit3_set(self):
        # flags=0x09 → bit3 SET → 1-byte ship counts
        data = _make_minimal_fleet(flags=0x09, mask=0x0001, ship_counts=[5])
        f = decode_fleet(data)
        assert f.ship_counts == {0: 5}

    def test_two_byte_counts_when_bit3_clear(self):
        # flags=0x00 → bit3 CLEAR → 2-byte ship counts
        data = _make_minimal_fleet(flags=0x00, mask=0x0001, ship_counts=[300], extra=b"")
        f = decode_fleet(data)
        assert f.ship_counts == {0: 300}

    def test_two_byte_count_value_above_255(self):
        data = _make_minimal_fleet(flags=0x00, mask=0x0004, ship_counts=[1000], extra=b"")
        f = decode_fleet(data)
        assert f.ship_counts[2] == 1000

    def test_multiple_design_slots(self):
        # mask=0x0005 → bits 0 and 2 → two ships
        data = _make_minimal_fleet(flags=0x09, mask=0x0005, ship_counts=[3, 7])
        f = decode_fleet(data)
        assert f.ship_counts == {0: 3, 2: 7}

    def test_total_ship_count_single_slot(self):
        data = _make_minimal_fleet(flags=0x09, mask=0x0001, ship_counts=[12])
        f = decode_fleet(data)
        assert f.total_ship_count == 12

    def test_total_ship_count_two_slots(self):
        data = _make_minimal_fleet(flags=0x09, mask=0x0003, ship_counts=[4, 6])
        f = decode_fleet(data)
        assert f.total_ship_count == 10

    def test_mask_zero_no_ship_counts(self):
        """No ship counts when mask is 0."""
        data = _make_minimal_fleet(flags=0x09, mask=0x0000, ship_counts=[])
        f = decode_fleet(data)
        assert f.ship_counts == {}
        assert f.total_ship_count == 0

    def test_all_sixteen_slots_1byte(self):
        """Mask with all 16 bits set, 1-byte counts."""
        counts = list(range(1, 17))  # 1..16
        data = _make_minimal_fleet(flags=0x09, mask=0xFFFF, ship_counts=counts)
        f = decode_fleet(data)
        assert len(f.ship_counts) == 16
        assert f.total_ship_count == sum(counts)

    def test_design_slot_index_from_mask(self):
        """Bit position maps correctly to design slot number."""
        # mask=0x0200 → bit 9
        data = _make_minimal_fleet(flags=0x09, mask=0x0200, ship_counts=[2])
        f = decode_fleet(data)
        assert 9 in f.ship_counts
        assert f.ship_counts[9] == 2


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Waypoint count + extra bytes
# ─────────────────────────────────────────────────────────────────────────────


class TestWaypointCountAndExtra:
    """Verify wp_count and extra_bytes handling."""

    def test_wp_count_is_last_byte_when_kind7(self):
        data = _make_minimal_fleet(kind=7, flags=0x09, mask=0x0001, ship_counts=[1], wp_count=3)
        f = decode_fleet(data)
        assert f.wp_count == 3

    def test_wp_count_one(self):
        data = _make_minimal_fleet(kind=7, flags=0x09, mask=0x0001, ship_counts=[1], wp_count=1)
        f = decode_fleet(data)
        assert f.wp_count == 1

    def test_wp_count_seven(self):
        data = _make_minimal_fleet(
            kind=7,
            flags=0x09,
            mask=0x0001,
            ship_counts=[1],
            extra=b"\x00\x01\x00\x00\x00",
            wp_count=7,
        )
        f = decode_fleet(data)
        assert f.wp_count == 7

    def test_wp_count_zero_when_kind_not_7(self):
        data = _make_minimal_fleet(kind=4, flags=0x09, mask=0x0001, ship_counts=[1])
        # kind != 7 → no wp_count byte convention; raw bytes go to extra_bytes
        f = decode_fleet(data)
        assert f.wp_count == 0

    def test_extra_bytes_stored_raw(self):
        extra = bytes([0, 1, 50, 0, 0, 0])
        data = _make_minimal_fleet(
            kind=7, flags=0x09, mask=0x0001, ship_counts=[1], extra=extra, wp_count=1
        )
        f = decode_fleet(data)
        assert f.extra_bytes == extra

    def test_extra_bytes_empty_when_no_extra(self):
        data = _make_minimal_fleet(
            kind=7, flags=0x09, mask=0x0001, ship_counts=[1], extra=b"", wp_count=1
        )
        f = decode_fleet(data)
        assert f.extra_bytes == b""

    def test_extra_bytes_type_is_bytes(self):
        data = _make_minimal_fleet(
            kind=7, flags=0x09, mask=0x0001, ship_counts=[1], extra=b"\x0a\x0b", wp_count=2
        )
        f = decode_fleet(data)
        assert isinstance(f.extra_bytes, bytes)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5: Error handling
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Verify decode_fleet raises appropriate errors on invalid input."""

    def test_raises_on_data_too_short(self):
        with pytest.raises(ValueError, match="too short"):
            decode_fleet(bytes(10))

    def test_raises_on_empty_data(self):
        with pytest.raises(ValueError):
            decode_fleet(b"")

    def test_raises_on_wrong_block_type(self):
        with pytest.raises(ValueError, match="16 or 17"):
            decode_fleet(bytes(20), block_type=13)

    def test_raises_on_block_type_zero(self):
        with pytest.raises(ValueError):
            decode_fleet(bytes(20), block_type=0)

    def test_minimum_14_bytes_accepted(self):
        """Exactly 14 bytes (no ship counts, no extra) → no error."""
        data = bytes(14)
        f = decode_fleet(data)
        assert f is not None

    def test_decode_fleets_wrong_type_raises(self):
        with pytest.raises(ValueError):
            decode_fleets([(99, bytes(20))])


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6: Real game data validation (Game.m1 and Game-big.m1)
# ─────────────────────────────────────────────────────────────────────────────


class TestRealDataM1:
    """Validate against Game.m1 (2-player game) fleet blocks."""

    def test_m1_fleet1_fleet_id(self):
        f = decode_fleet(M1_FLEET_1)
        assert f.fleet_id == 1

    def test_m1_fleet1_owner(self):
        f = decode_fleet(M1_FLEET_1)
        assert f.owner == 0

    def test_m1_fleet1_kind_full(self):
        f = decode_fleet(M1_FLEET_1)
        assert f.kind == FLEET_KIND_FULL

    def test_m1_fleet1_position(self):
        f = decode_fleet(M1_FLEET_1)
        assert f.x == 1361
        assert f.y == 1132

    def test_m1_fleet1_orbit(self):
        f = decode_fleet(M1_FLEET_1)
        assert f.orbit_planet_id == 29

    def test_m1_fleet1_ship_counts(self):
        f = decode_fleet(M1_FLEET_1)
        assert f.ship_counts == {1: 1}
        assert f.total_ship_count == 1

    def test_m1_fleet1_wp_count(self):
        f = decode_fleet(M1_FLEET_1)
        assert f.wp_count == 7

    def test_m1_fleet3_fleet_id(self):
        f = decode_fleet(M1_FLEET_3)
        assert f.fleet_id == 3

    def test_m1_fleet3_ship_counts(self):
        f = decode_fleet(M1_FLEET_3)
        assert f.ship_counts == {3: 1}

    def test_m1_fleet3_wp_count(self):
        f = decode_fleet(M1_FLEET_3)
        assert f.wp_count == 3

    def test_m1_fleet3_orbit(self):
        f = decode_fleet(M1_FLEET_3)
        assert f.orbit_planet_id == 20

    def test_m1_fleet5_fleet_id(self):
        f = decode_fleet(M1_FLEET_5)
        assert f.fleet_id == 5

    def test_m1_fleet5_design_slot(self):
        f = decode_fleet(M1_FLEET_5)
        assert 5 in f.ship_counts

    def test_m1_fleet5_wp_count(self):
        f = decode_fleet(M1_FLEET_5)
        assert f.wp_count == 1

    def test_m1_fleet5_position(self):
        f = decode_fleet(M1_FLEET_5)
        assert f.x == 1273
        assert f.y == 1183


class TestRealDataBigM1:
    """Validate against Game-big.m1 (16-player game) fleet blocks."""

    def test_big_fleet0_fleet_id(self):
        f = decode_fleet(BIG_FLEET_0)
        assert f.fleet_id == 0

    def test_big_fleet0_owner(self):
        f = decode_fleet(BIG_FLEET_0)
        assert f.owner == 0

    def test_big_fleet0_position(self):
        f = decode_fleet(BIG_FLEET_0)
        assert f.x == 1644
        assert f.y == 2877

    def test_big_fleet0_orbit(self):
        f = decode_fleet(BIG_FLEET_0)
        assert f.orbit_planet_id == 307

    def test_big_fleet0_mask(self):
        f = decode_fleet(BIG_FLEET_0)
        assert f.ship_designs_mask == 0x0001

    def test_big_fleet0_ship_count_slot0(self):
        f = decode_fleet(BIG_FLEET_0)
        assert f.ship_counts == {0: 1}

    def test_big_fleet0_wp_count(self):
        f = decode_fleet(BIG_FLEET_0)
        assert f.wp_count == 1

    def test_big_fleet1_fleet_id(self):
        f = decode_fleet(BIG_FLEET_1)
        assert f.fleet_id == 1

    def test_big_fleet1_design_slot9(self):
        f = decode_fleet(BIG_FLEET_1)
        assert 9 in f.ship_counts
        assert f.ship_counts[9] == 1

    def test_big_fleet1_wp_count(self):
        f = decode_fleet(BIG_FLEET_1)
        assert f.wp_count == 1

    def test_big_fleet2_fleet_id(self):
        f = decode_fleet(BIG_FLEET_2)
        assert f.fleet_id == 2

    def test_big_fleet2_design_slot6(self):
        f = decode_fleet(BIG_FLEET_2)
        assert 6 in f.ship_counts

    def test_big_fleet9_fleet_id(self):
        f = decode_fleet(BIG_FLEET_9)
        assert f.fleet_id == 9

    def test_big_fleet9_design_slot2(self):
        f = decode_fleet(BIG_FLEET_9)
        assert 2 in f.ship_counts

    def test_big_fleet9_wp_count(self):
        f = decode_fleet(BIG_FLEET_9)
        assert f.wp_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7: Batch decoder + load_game integration
# ─────────────────────────────────────────────────────────────────────────────


class TestBatchDecoder:
    """Validate decode_fleets() (multi-block pipeline)."""

    def test_empty_list_returns_empty(self):
        result = decode_fleets([])
        assert result == []

    def test_single_item_returns_one_detail(self):
        result = decode_fleets([(BLOCK_TYPE_FLEET_FULL, M1_FLEET_1)])
        assert len(result) == 1

    def test_multiple_items_preserves_order(self):
        result = decode_fleets(
            [
                (BLOCK_TYPE_FLEET_FULL, M1_FLEET_1),
                (BLOCK_TYPE_FLEET_FULL, M1_FLEET_3),
                (BLOCK_TYPE_FLEET_FULL, M1_FLEET_5),
            ]
        )
        assert len(result) == 3
        assert result[0].fleet_id == 1
        assert result[1].fleet_id == 3
        assert result[2].fleet_id == 5

    def test_mixed_full_and_partial_types(self):
        result = decode_fleets(
            [
                (BLOCK_TYPE_FLEET_FULL, M1_FLEET_1),
                (BLOCK_TYPE_FLEET_PARTIAL, M1_FLEET_5),
            ]
        )
        assert result[0].is_full is True
        assert result[1].is_full is False

    def test_batch_totals_correct(self):
        result = decode_fleets(
            [
                (BLOCK_TYPE_FLEET_FULL, BIG_FLEET_0),
                (BLOCK_TYPE_FLEET_FULL, BIG_FLEET_1),
                (BLOCK_TYPE_FLEET_FULL, BIG_FLEET_2),
            ]
        )
        total = sum(f.total_ship_count for f in result)
        assert total == 3  # 1 ship per fleet


class TestLoadGameIntegration:
    """Verify fleet data appears correctly in game state via load_game()."""

    def test_load_game_has_fleets(self, game_dir):
        from stars_web.game_state import load_game

        gs = load_game(game_dir, player=1)
        assert len(gs.fleets) > 0

    def test_load_game_fleet_has_position(self, game_dir):
        from stars_web.game_state import load_game

        gs = load_game(game_dir, player=1)
        for fleet in gs.fleets:
            assert fleet.x >= 0
            assert fleet.y >= 0

    def test_load_game_fleet_has_positive_ship_count(self, game_dir):
        from stars_web.game_state import load_game

        gs = load_game(game_dir, player=1)
        for fleet in gs.fleets:
            assert fleet.ship_count > 0

    def test_load_game_fleet_owner_non_negative(self, game_dir):
        from stars_web.game_state import load_game

        gs = load_game(game_dir, player=1)
        for fleet in gs.fleets:
            assert fleet.owner >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Phase 8: Property-based invariants
# ─────────────────────────────────────────────────────────────────────────────


class TestPropertyBasedInvariants:
    """Hypothesis-based tests for broad input coverage."""

    @given(
        fleet_id=st.integers(min_value=0, max_value=511),
        owner=st.integers(min_value=0, max_value=15),
        x=st.integers(min_value=0, max_value=32767),
        y=st.integers(min_value=0, max_value=32767),
    )
    @settings(max_examples=80, deadline=None)
    def test_round_trip_header_fields(self, fleet_id, owner, x, y):
        data = _make_minimal_fleet(fleet_id=fleet_id, owner=owner, x=x, y=y, ship_counts=[])
        f = decode_fleet(data)
        assert f.fleet_id == fleet_id
        assert f.owner == owner
        assert f.x == x
        assert f.y == y

    @given(count=st.integers(min_value=0, max_value=65535))
    @settings(max_examples=80, deadline=None)
    def test_two_byte_ship_count_roundtrip(self, count):
        # flags=0x00 (bit3 CLEAR) → 2-byte counts
        data = _make_minimal_fleet(flags=0x00, mask=0x0001, ship_counts=[count], extra=b"")
        f = decode_fleet(data)
        assert f.ship_counts.get(0, 0) == count

    @given(count=st.integers(min_value=0, max_value=255))
    @settings(max_examples=80, deadline=None)
    def test_one_byte_ship_count_roundtrip(self, count):
        # flags=0x09 (bit3 SET) → 1-byte counts
        data = _make_minimal_fleet(flags=0x09, mask=0x0001, ship_counts=[count])
        f = decode_fleet(data)
        assert f.ship_counts.get(0, 0) == count

    @given(wp=st.integers(min_value=0, max_value=9))
    @settings(max_examples=40, deadline=None)
    def test_wp_count_roundtrip(self, wp):
        data = _make_minimal_fleet(kind=7, flags=0x09, mask=0x0001, ship_counts=[1], wp_count=wp)
        f = decode_fleet(data)
        assert f.wp_count == wp
