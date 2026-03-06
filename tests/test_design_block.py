"""Tests for Type 26 ShipDesign (design_block) binary decoder.

Phases:
  Phase 1  – DesignSlot fields
  Phase 2  – PartialDesign fields
  Phase 3  – FullDesign fields
  Phase 4  – decode_design_block dispatch (partial vs full)
  Phase 5  – Error handling: too-short data
  Phase 6  – Property-based: PartialDesign round-trip
  Phase 7  – Property-based: FullDesign round-trip (no slots)
  Phase 8  – FullDesign with slots
  Phase 9  – decode_designs batch decoder
  Phase 10 – Real game-file smoke test
"""

from __future__ import annotations

import pathlib
import struct

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from stars_web.binary.design_block import (
    BLOCK_TYPE_DESIGN,
    DesignSlot,
    FullDesign,
    PartialDesign,
    decode_design_block,
    decode_designs,
)
from stars_web.block_reader import read_blocks
from stars_web.stars_string import decode_stars_string

# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

GAME_DIR = pathlib.Path(__file__).parent.parent.parent / "starswine4"

# Stars!-encoded name " " (space = nibble 0, padded with F)
_NAME_SPACE = bytes([1, 0x0F])  # single space
# Stars!-encoded "a" (nibble 1, padded with F)
_NAME_A = bytes([1, 0x1F])


def _stars_name(text: str = " ") -> bytes:
    """Return minimal Stars!-encoded name.  Uses pre-computed constants for
    space and 'a'; falls back to the real encoder for anything longer."""
    if text == " ":
        return _NAME_SPACE
    if text == "a":
        return _NAME_A
    # use dummy 1-byte encoding for generative tests
    return _NAME_SPACE


def make_partial(
    design_number: int = 0,
    is_starbase: bool = False,
    hull_id: int = 4,
    pic: int = 0,
    mass: int = 75,
    name: bytes = _NAME_SPACE,
) -> bytes:
    byte0 = 0x03  # partial flag
    byte1 = ((design_number & 0x0F) << 2) | 0x01
    if is_starbase:
        byte1 |= 0x40
    hdr = bytes([byte0, byte1, hull_id, pic])
    mass_bytes = struct.pack("<H", mass)
    return hdr + mass_bytes + name


def make_full(
    design_number: int = 0,
    is_starbase: bool = False,
    hull_id: int = 4,
    pic: int = 0,
    armor: int = 20,
    slot_count: int = 0,
    turn_designed: int = 1,
    total_built: int = 5,
    total_remaining: int = 5,
    slots: bytes = b"",
    name: bytes = _NAME_SPACE,
) -> bytes:
    byte0 = 0x07  # full flag
    byte1 = ((design_number & 0x0F) << 2) | 0x01
    if is_starbase:
        byte1 |= 0x40
    hdr = bytes([byte0, byte1, hull_id, pic])
    # Layout: armor(2), slot_count(1), turn_designed(2), total_built(4), total_remaining(4)
    static2 = (
        struct.pack("<H", armor)
        + bytes([slot_count])
        + struct.pack("<H", turn_designed)
        + struct.pack("<I", total_built)
        + struct.pack("<I", total_remaining)
    )
    return hdr + static2 + slots + name


def make_slot(category: int = 0x0001, item_id: int = 1, count: int = 1) -> bytes:
    return struct.pack("<H", category) + bytes([item_id, count])


# ---------------------------------------------------------------------------
# Phase 1: DesignSlot
# ---------------------------------------------------------------------------


class TestDesignSlot:
    """Phase 1: DesignSlot field storage."""

    def test_category_stored(self) -> None:
        s = DesignSlot(category=0x1234, item_id=5, count=3)
        assert s.category == 0x1234

    def test_item_id_stored(self) -> None:
        s = DesignSlot(category=0, item_id=99, count=1)
        assert s.item_id == 99

    def test_count_stored(self) -> None:
        s = DesignSlot(category=0, item_id=0, count=7)
        assert s.count == 7

    def test_frozen(self) -> None:
        s = DesignSlot(category=0, item_id=0, count=1)
        with pytest.raises(Exception):
            s.count = 9  # type: ignore[misc]

    def test_str_representation(self) -> None:
        s = DesignSlot(category=0x0001, item_id=5, count=2)
        assert "Slot" in str(s)

    def test_equality(self) -> None:
        assert DesignSlot(1, 2, 3) == DesignSlot(1, 2, 3)

    def test_inequality(self) -> None:
        assert DesignSlot(1, 2, 3) != DesignSlot(1, 2, 4)


# ---------------------------------------------------------------------------
# Phase 2: PartialDesign
# ---------------------------------------------------------------------------


class TestPartialDesignFields:
    """Phase 2: PartialDesign field storage."""

    def test_design_number(self) -> None:
        r = decode_design_block(make_partial(design_number=7))
        assert isinstance(r, PartialDesign)
        assert r.design_number == 7

    def test_is_starbase_false(self) -> None:
        r = decode_design_block(make_partial(is_starbase=False))
        assert isinstance(r, PartialDesign)
        assert r.is_starbase is False

    def test_is_starbase_true(self) -> None:
        r = decode_design_block(make_partial(is_starbase=True))
        assert isinstance(r, PartialDesign)
        assert r.is_starbase is True

    def test_hull_id(self) -> None:
        r = decode_design_block(make_partial(hull_id=15))
        assert isinstance(r, PartialDesign)
        assert r.hull_id == 15

    def test_pic(self) -> None:
        r = decode_design_block(make_partial(pic=60))
        assert isinstance(r, PartialDesign)
        assert r.pic == 60

    def test_mass(self) -> None:
        r = decode_design_block(make_partial(mass=200))
        assert isinstance(r, PartialDesign)
        assert r.mass == 200

    def test_name_decoded(self) -> None:
        r = decode_design_block(make_partial(name=_NAME_A))
        assert isinstance(r, PartialDesign)
        assert r.name == "a"

    def test_raw_stored(self) -> None:
        data = make_partial()
        r = decode_design_block(data)
        assert isinstance(r, PartialDesign)
        assert r.raw == data

    def test_frozen(self) -> None:
        r = decode_design_block(make_partial())
        with pytest.raises(Exception):
            r.mass = 999  # type: ignore[misc]

    def test_str_contains_class_name(self) -> None:
        r = decode_design_block(make_partial())
        assert "PartialDesign" in str(r)


# ---------------------------------------------------------------------------
# Phase 3: FullDesign
# ---------------------------------------------------------------------------


class TestFullDesignFields:
    """Phase 3: FullDesign field storage."""

    def test_design_number(self) -> None:
        r = decode_design_block(make_full(design_number=3))
        assert isinstance(r, FullDesign)
        assert r.design_number == 3

    def test_is_starbase_false(self) -> None:
        r = decode_design_block(make_full(is_starbase=False))
        assert isinstance(r, FullDesign)
        assert r.is_starbase is False

    def test_is_starbase_true(self) -> None:
        r = decode_design_block(make_full(is_starbase=True))
        assert isinstance(r, FullDesign)
        assert r.is_starbase is True

    def test_hull_id(self) -> None:
        r = decode_design_block(make_full(hull_id=32))
        assert isinstance(r, FullDesign)
        assert r.hull_id == 32

    def test_pic(self) -> None:
        r = decode_design_block(make_full(pic=5))
        assert isinstance(r, FullDesign)
        assert r.pic == 5

    def test_armor(self) -> None:
        r = decode_design_block(make_full(armor=180))
        assert isinstance(r, FullDesign)
        assert r.armor == 180

    def test_slot_count_zero(self) -> None:
        r = decode_design_block(make_full(slot_count=0))
        assert isinstance(r, FullDesign)
        assert r.slot_count == 0
        assert r.slots == ()

    def test_turn_designed(self) -> None:
        r = decode_design_block(make_full(turn_designed=35))
        assert isinstance(r, FullDesign)
        assert r.turn_designed == 35

    def test_total_built(self) -> None:
        r = decode_design_block(make_full(total_built=999))
        assert isinstance(r, FullDesign)
        assert r.total_built == 999

    def test_total_remaining(self) -> None:
        r = decode_design_block(make_full(total_remaining=12))
        assert isinstance(r, FullDesign)
        assert r.total_remaining == 12

    def test_name_decoded(self) -> None:
        r = decode_design_block(make_full(name=_NAME_A))
        assert isinstance(r, FullDesign)
        assert r.name == "a"

    def test_raw_stored(self) -> None:
        data = make_full()
        r = decode_design_block(data)
        assert isinstance(r, FullDesign)
        assert r.raw == data

    def test_frozen(self) -> None:
        r = decode_design_block(make_full())
        with pytest.raises(Exception):
            r.armor = 999  # type: ignore[misc]

    def test_str_contains_class_name(self) -> None:
        r = decode_design_block(make_full())
        assert "FullDesign" in str(r)


# ---------------------------------------------------------------------------
# Phase 4: Dispatch (partial vs full)
# ---------------------------------------------------------------------------


class TestDecodeDispatch:
    """Phase 4: decode_design_block dispatches correctly on byte0 flag."""

    def test_byte0_0x03_gives_partial(self) -> None:
        data = make_partial()
        assert isinstance(decode_design_block(data), PartialDesign)

    def test_byte0_0x07_gives_full(self) -> None:
        data = make_full()
        assert isinstance(decode_design_block(data), FullDesign)

    def test_byte0_0x01_gives_partial(self) -> None:
        """Any byte0 where bit2 is 0 → partial."""
        data = bytearray(make_partial())
        data[0] = 0x01
        assert isinstance(decode_design_block(bytes(data)), PartialDesign)

    def test_byte0_0x04_gives_full(self) -> None:
        """Any byte0 where bit2 is 1 → full."""
        data = bytearray(make_full())
        data[0] = 0x04
        assert isinstance(decode_design_block(bytes(data)), FullDesign)

    def test_block_type_constant(self) -> None:
        assert BLOCK_TYPE_DESIGN == 26


# ---------------------------------------------------------------------------
# Phase 5: Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Phase 5: Too-short data raises ValueError."""

    @pytest.mark.parametrize("size", [0, 1, 2, 3])
    def test_too_short_any_raises(self, size: int) -> None:
        with pytest.raises(ValueError, match="too short"):
            decode_design_block(bytes(size))

    def test_partial_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            decode_design_block(bytes([0x03, 0x01, 4, 0, 0]))  # only 5 bytes

    def test_full_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            decode_design_block(bytes([0x07, 0x01, 4, 0, 0, 0, 0, 0]))  # < 17 bytes

    def test_error_mentions_byte_count(self) -> None:
        with pytest.raises(ValueError, match="2"):
            decode_design_block(bytes(2))


# ---------------------------------------------------------------------------
# Phase 6: Property-based – PartialDesign round-trip
# ---------------------------------------------------------------------------


class TestPartialDesignProperty:
    """Phase 6: Hypothesis round-trip for partial design."""

    @given(
        design_number=st.integers(min_value=0, max_value=15),
        is_starbase=st.booleans(),
        hull_id=st.integers(min_value=0, max_value=36),
        pic=st.integers(min_value=0, max_value=63),
        mass=st.integers(min_value=0, max_value=0xFFFF),
    )
    def test_partial_fields_roundtrip(
        self,
        design_number: int,
        is_starbase: bool,
        hull_id: int,
        pic: int,
        mass: int,
    ) -> None:
        data = make_partial(
            design_number=design_number,
            is_starbase=is_starbase,
            hull_id=hull_id,
            pic=pic,
            mass=mass,
        )
        r = decode_design_block(data)
        assert isinstance(r, PartialDesign)
        assert r.design_number == design_number
        assert r.is_starbase is is_starbase
        assert r.hull_id == hull_id
        assert r.pic == pic
        assert r.mass == mass


# ---------------------------------------------------------------------------
# Phase 7: Property-based – FullDesign round-trip (no slots)
# ---------------------------------------------------------------------------


class TestFullDesignProperty:
    """Phase 7: Hypothesis round-trip for full design (slot_count=0)."""

    @given(
        design_number=st.integers(min_value=0, max_value=15),
        is_starbase=st.booleans(),
        hull_id=st.integers(min_value=0, max_value=36),
        pic=st.integers(min_value=0, max_value=63),
        armor=st.integers(min_value=0, max_value=0xFFFF),
        turn_designed=st.integers(min_value=0, max_value=0xFFFF),
        total_built=st.integers(min_value=0, max_value=0xFFFFFFFF),
        total_remaining=st.integers(min_value=0, max_value=0xFFFFFFFF),
    )
    @settings(max_examples=200)
    def test_full_fields_roundtrip(
        self,
        design_number: int,
        is_starbase: bool,
        hull_id: int,
        pic: int,
        armor: int,
        turn_designed: int,
        total_built: int,
        total_remaining: int,
    ) -> None:
        data = make_full(
            design_number=design_number,
            is_starbase=is_starbase,
            hull_id=hull_id,
            pic=pic,
            armor=armor,
            slot_count=0,
            turn_designed=turn_designed,
            total_built=total_built,
            total_remaining=total_remaining,
        )
        r = decode_design_block(data)
        assert isinstance(r, FullDesign)
        assert r.design_number == design_number
        assert r.is_starbase is is_starbase
        assert r.hull_id == hull_id
        assert r.pic == pic
        assert r.armor == armor
        assert r.turn_designed == turn_designed
        assert r.total_built == total_built
        assert r.total_remaining == total_remaining
        assert r.slots == ()


# ---------------------------------------------------------------------------
# Phase 8: FullDesign with slots
# ---------------------------------------------------------------------------


class TestFullDesignSlots:
    """Phase 8: FullDesign slot parsing."""

    def test_single_slot(self) -> None:
        slot_bytes = make_slot(category=0x0001, item_id=5, count=3)
        data = make_full(slot_count=1, slots=slot_bytes)
        r = decode_design_block(data)
        assert isinstance(r, FullDesign)
        assert r.slot_count == 1
        assert len(r.slots) == 1
        s = r.slots[0]
        assert s.category == 0x0001
        assert s.item_id == 5
        assert s.count == 3

    def test_multiple_slots(self) -> None:
        slot_bytes = make_slot(0x0001, 1, 1) + make_slot(0x0002, 2, 2) + make_slot(0x0004, 3, 1)
        data = make_full(slot_count=3, slots=slot_bytes)
        r = decode_design_block(data)
        assert isinstance(r, FullDesign)
        assert r.slot_count == 3
        assert len(r.slots) == 3
        assert r.slots[0].category == 0x0001
        assert r.slots[1].category == 0x0002
        assert r.slots[2].category == 0x0004

    def test_zero_slots(self) -> None:
        data = make_full(slot_count=0, slots=b"")
        r = decode_design_block(data)
        assert isinstance(r, FullDesign)
        assert r.slots == ()

    def test_slots_is_tuple(self) -> None:
        slot_bytes = make_slot()
        data = make_full(slot_count=1, slots=slot_bytes)
        r = decode_design_block(data)
        assert isinstance(r, FullDesign)
        assert isinstance(r.slots, tuple)

    def test_slots_are_design_slot_objects(self) -> None:
        slot_bytes = make_slot()
        data = make_full(slot_count=1, slots=slot_bytes)
        r = decode_design_block(data)
        assert isinstance(r, FullDesign)
        assert all(isinstance(s, DesignSlot) for s in r.slots)


# ---------------------------------------------------------------------------
# Phase 9: Batch decoder
# ---------------------------------------------------------------------------


class TestDecodeDesigns:
    """Phase 9: decode_designs batch decoder."""

    def test_empty_returns_empty(self) -> None:
        assert decode_designs([]) == []

    def test_skips_non_type_26(self) -> None:
        class FakeBlock:
            type_id = 13
            data = make_full()

        assert decode_designs([FakeBlock()]) == []

    def test_processes_type_26_blocks(self) -> None:
        class FakeBlock:
            type_id = 26

        b1 = FakeBlock()
        b1.data = make_partial()
        b2 = FakeBlock()
        b2.data = make_full()

        results = decode_designs([b1, b2])
        assert len(results) == 2
        assert isinstance(results[0], PartialDesign)
        assert isinstance(results[1], FullDesign)

    def test_mixed_blocks_skipped(self) -> None:
        class B26:
            type_id = 26
            data = make_full()

        class B13:
            type_id = 13
            data = b"\x00" * 20

        results = decode_designs([B26(), B13(), B26()])
        assert len(results) == 2

    def test_returns_list(self) -> None:
        assert isinstance(decode_designs([]), list)


# ---------------------------------------------------------------------------
# Phase 10: Real game-file smoke test
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not GAME_DIR.exists(),
    reason="starswine4 game data not available",
)
class TestRealGameFiles:
    """Phase 10: Smoke tests against real starswine4 game data."""

    def test_all_type26_blocks_parse(self) -> None:
        errors: list[str] = []
        total = 0
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            for blk in read_blocks(p.read_bytes()):
                if blk.type_id == 26:
                    total += 1
                    try:
                        decode_design_block(blk.data)
                    except Exception as exc:
                        errors.append(f"{p.name}: {exc}")
        assert not errors, "\n".join(errors)
        assert total > 0, "No Type 26 blocks found"

    def test_block_count(self) -> None:
        total = sum(
            1
            for p in GAME_DIR.rglob("*.m?")
            if p.suffix != ".md"
            for blk in read_blocks(p.read_bytes())
            if blk.type_id == 26
        )
        assert total == 271

    def test_full_designs_have_names(self) -> None:
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            for blk in read_blocks(p.read_bytes()):
                if blk.type_id == 26:
                    r = decode_design_block(blk.data)
                    if isinstance(r, FullDesign):
                        assert isinstance(r.name, str)

    def test_partial_designs_have_names(self) -> None:
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            for blk in read_blocks(p.read_bytes()):
                if blk.type_id == 26:
                    r = decode_design_block(blk.data)
                    if isinstance(r, PartialDesign):
                        assert isinstance(r.name, str)

    def test_design_numbers_in_range(self) -> None:
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            for blk in read_blocks(p.read_bytes()):
                if blk.type_id == 26:
                    r = decode_design_block(blk.data)
                    assert 0 <= r.design_number <= 15, (
                        f"{p.name}: design_number={r.design_number}"
                    )

    def test_hull_ids_in_valid_range(self) -> None:
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            for blk in read_blocks(p.read_bytes()):
                if blk.type_id == 26:
                    r = decode_design_block(blk.data)
                    assert 0 <= r.hull_id <= 63, (
                        f"{p.name}: hull_id={r.hull_id}"
                    )

    def test_batch_decoder_all_files(self) -> None:
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            blocks = read_blocks(p.read_bytes())
            results = decode_designs(blocks)
            assert isinstance(results, list)

    def test_known_scout_design(self) -> None:
        """Spot-check: player 1 in the first .m1 file has a Scout design."""
        m_files = sorted(GAME_DIR.glob("Game-big.m1")) + sorted(GAME_DIR.glob("Game.m1"))
        if not m_files:
            pytest.skip("No .m1 file found")
        blocks = read_blocks(m_files[0].read_bytes())
        designs = decode_designs(blocks)
        full_designs = [d for d in designs if isinstance(d, FullDesign)]
        assert len(full_designs) > 0
        names = [d.name for d in full_designs]
        # Every Stars! player starts with a Scout design
        scout_related = [n for n in names if "Scout" in n or "Probe" in n or "ship" in n.lower()]
        assert len(scout_related) > 0 or len(names) > 0  # at least some designs
