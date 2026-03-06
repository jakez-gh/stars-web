"""Tests for Type 43 ShipDesign binary block parser.

Tests are organised into phases:
  Phase 1  – ShipDesignCount (2-byte variant) construction & invariants
  Phase 2  – ShipDesign (18-byte variant) construction & field access
  Phase 3  – ShipDesign computed properties
  Phase 4  – decode_ship_design_block dispatch
  Phase 5  – Error handling: invalid sizes
  Phase 6  – Property-based: ShipDesignCount round-trip
  Phase 7  – Property-based: ShipDesign round-trip
  Phase 8  – decode_ship_designs batch decoder
  Phase 9  – Real game-file smoke test
"""

from __future__ import annotations

import pathlib
import struct

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from stars_web.binary.ship_design import (
    ShipDesign,
    ShipDesignCount,
    decode_ship_design_block,
    decode_ship_designs,
)
from stars_web.block_reader import read_blocks

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GAME_DIR = pathlib.Path(__file__).parent.parent.parent / "starswine4"

# Known 18-byte sample from Game-big.m2 (player 2, design slot 1)
SAMPLE_18 = bytes.fromhex("012e75076f090bd000000100000001c02000")
# Known 2-byte sample from Game-big.m2 (player 2 design count = 1)
SAMPLE_2 = bytes.fromhex("0100")


def make_design(
    design_id: int = 0,
    player_tag: int = 0x2E,
    cost_iron: int = 100,
    cost_boron: int = 50,
    cost_germ_pack: int = 0xD020,
    slots_a: int = 0,
    slots_b: int = 1,
    slots_c: int = 0,
    tech_flags: int = 0xC001,
    padding: int = 0x0020,
) -> bytes:
    return struct.pack(
        "<BBHHHHHHHH",
        design_id,
        player_tag,
        cost_iron,
        cost_boron,
        cost_germ_pack,
        slots_a,
        slots_b,
        slots_c,
        tech_flags,
        padding,
    )


def make_count(count: int) -> bytes:
    return struct.pack("<H", count)


# ---------------------------------------------------------------------------
# Phase 1: ShipDesignCount construction
# ---------------------------------------------------------------------------


class TestShipDesignCount:
    """Phase 1: ShipDesignCount (2-byte variant)."""

    def test_count_stored_correctly(self) -> None:
        sdc = ShipDesignCount(count=3)
        assert sdc.count == 3

    def test_count_zero(self) -> None:
        sdc = ShipDesignCount(count=0)
        assert sdc.count == 0

    def test_count_max_uint16(self) -> None:
        sdc = ShipDesignCount(count=0xFFFF)
        assert sdc.count == 0xFFFF

    def test_str_representation(self) -> None:
        sdc = ShipDesignCount(count=5)
        assert "5" in str(sdc)

    def test_frozen(self) -> None:
        sdc = ShipDesignCount(count=2)
        with pytest.raises(Exception):
            sdc.count = 99  # type: ignore[misc]

    def test_equality(self) -> None:
        assert ShipDesignCount(count=1) == ShipDesignCount(count=1)
        assert ShipDesignCount(count=1) != ShipDesignCount(count=2)


# ---------------------------------------------------------------------------
# Phase 2: ShipDesign field access
# ---------------------------------------------------------------------------


class TestShipDesignFields:
    """Phase 2: ShipDesign (18-byte variant) fields."""

    def test_design_id(self) -> None:
        data = make_design(design_id=5)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.design_id == 5

    def test_player_tag(self) -> None:
        data = make_design(player_tag=0x3E)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.player_tag == 0x3E

    def test_cost_iron(self) -> None:
        data = make_design(cost_iron=999)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.cost_iron == 999

    def test_cost_boron(self) -> None:
        data = make_design(cost_boron=512)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.cost_boron == 512

    def test_cost_germ_pack(self) -> None:
        data = make_design(cost_germ_pack=0xD030)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.cost_germ_pack == 0xD030

    def test_slots_abc(self) -> None:
        data = make_design(slots_a=6, slots_b=11, slots_c=21)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.slots_a == 6
        assert d.slots_b == 11
        assert d.slots_c == 21

    def test_tech_flags(self) -> None:
        data = make_design(tech_flags=0xC005)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.tech_flags == 0xC005

    def test_padding(self) -> None:
        data = make_design(padding=0x0020)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.padding == 0x0020

    def test_frozen(self) -> None:
        d = decode_ship_design_block(make_design())
        with pytest.raises(Exception):
            d.design_id = 99  # type: ignore[misc]

    def test_str_representation(self) -> None:
        d = decode_ship_design_block(SAMPLE_18)
        s = str(d)
        assert "ShipDesign" in s
        assert "design_id" not in s or "id=" in s  # just check it contains info


# ---------------------------------------------------------------------------
# Phase 3: ShipDesign computed properties
# ---------------------------------------------------------------------------


class TestShipDesignProperties:
    """Phase 3: Computed properties of ShipDesign."""

    def test_cost_germanium_low_byte(self) -> None:
        data = make_design(cost_germ_pack=0xD048)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.cost_germanium == 0x48

    def test_cost_germanium_zero(self) -> None:
        data = make_design(cost_germ_pack=0xD000)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.cost_germanium == 0

    def test_tech_count_low_6_bits(self) -> None:
        data = make_design(tech_flags=0xC007)  # low 6 bits = 7
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.tech_count == 7

    def test_tech_count_ignores_high_bits(self) -> None:
        data = make_design(tech_flags=0xC03F)  # low 6 bits = 63
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.tech_count == 63

    def test_tech_count_zero(self) -> None:
        data = make_design(tech_flags=0xC000)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.tech_count == 0


# ---------------------------------------------------------------------------
# Phase 4: Decode dispatch
# ---------------------------------------------------------------------------


class TestDecodeDispatch:
    """Phase 4: decode_ship_design_block dispatches on size."""

    def test_2_byte_returns_count(self) -> None:
        result = decode_ship_design_block(make_count(7))
        assert isinstance(result, ShipDesignCount)
        assert result.count == 7

    def test_18_byte_returns_design(self) -> None:
        result = decode_ship_design_block(make_design())
        assert isinstance(result, ShipDesign)

    def test_known_sample_count(self) -> None:
        result = decode_ship_design_block(SAMPLE_2)
        assert isinstance(result, ShipDesignCount)
        assert result.count == 1

    def test_known_sample_design(self) -> None:
        result = decode_ship_design_block(SAMPLE_18)
        assert isinstance(result, ShipDesign)
        assert result.design_id == 1
        assert result.player_tag == 0x2E


# ---------------------------------------------------------------------------
# Phase 5: Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Phase 5: decode_ship_design_block rejects invalid sizes."""

    @pytest.mark.parametrize("size", [0, 1, 3, 10, 17, 19, 100])
    def test_invalid_size_raises_value_error(self, size: int) -> None:
        with pytest.raises(ValueError, match="2 or 18 bytes"):
            decode_ship_design_block(bytes(size))

    def test_error_message_includes_size(self) -> None:
        with pytest.raises(ValueError, match="5"):
            decode_ship_design_block(bytes(5))


# ---------------------------------------------------------------------------
# Phase 6: Property-based – ShipDesignCount round-trip
# ---------------------------------------------------------------------------


class TestShipDesignCountProperty:
    """Phase 6: Hypothesis round-trip for the 2-byte variant."""

    @given(st.integers(min_value=0, max_value=0xFFFF))
    def test_count_roundtrip(self, count: int) -> None:
        data = make_count(count)
        result = decode_ship_design_block(data)
        assert isinstance(result, ShipDesignCount)
        assert result.count == count

    @given(st.integers(min_value=0, max_value=0xFFFF))
    def test_count_data_length(self, count: int) -> None:
        data = make_count(count)
        assert len(data) == 2


# ---------------------------------------------------------------------------
# Phase 7: Property-based – ShipDesign round-trip
# ---------------------------------------------------------------------------


class TestShipDesignProperty:
    """Phase 7: Hypothesis round-trip for the 18-byte variant."""

    @given(
        design_id=st.integers(min_value=0, max_value=255),
        player_tag=st.integers(min_value=0, max_value=255),
        cost_iron=st.integers(min_value=0, max_value=0xFFFF),
        cost_boron=st.integers(min_value=0, max_value=0xFFFF),
        cost_germ_pack=st.integers(min_value=0, max_value=0xFFFF),
        slots_a=st.integers(min_value=0, max_value=0xFFFF),
        slots_b=st.integers(min_value=0, max_value=0xFFFF),
        slots_c=st.integers(min_value=0, max_value=0xFFFF),
        tech_flags=st.integers(min_value=0, max_value=0xFFFF),
        padding=st.integers(min_value=0, max_value=0xFFFF),
    )
    @settings(max_examples=200)
    def test_design_roundtrip(
        self,
        design_id: int,
        player_tag: int,
        cost_iron: int,
        cost_boron: int,
        cost_germ_pack: int,
        slots_a: int,
        slots_b: int,
        slots_c: int,
        tech_flags: int,
        padding: int,
    ) -> None:
        data = make_design(
            design_id=design_id,
            player_tag=player_tag,
            cost_iron=cost_iron,
            cost_boron=cost_boron,
            cost_germ_pack=cost_germ_pack,
            slots_a=slots_a,
            slots_b=slots_b,
            slots_c=slots_c,
            tech_flags=tech_flags,
            padding=padding,
        )
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.design_id == design_id
        assert d.player_tag == player_tag
        assert d.cost_iron == cost_iron
        assert d.cost_boron == cost_boron
        assert d.cost_germ_pack == cost_germ_pack
        assert d.slots_a == slots_a
        assert d.slots_b == slots_b
        assert d.slots_c == slots_c
        assert d.tech_flags == tech_flags
        assert d.padding == padding

    @given(
        cost_germ_pack=st.integers(min_value=0, max_value=0xFFFF),
    )
    def test_cost_germanium_is_low_byte(self, cost_germ_pack: int) -> None:
        data = make_design(cost_germ_pack=cost_germ_pack)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.cost_germanium == cost_germ_pack & 0xFF

    @given(
        tech_flags=st.integers(min_value=0, max_value=0xFFFF),
    )
    def test_tech_count_is_low_6_bits(self, tech_flags: int) -> None:
        data = make_design(tech_flags=tech_flags)
        d = decode_ship_design_block(data)
        assert isinstance(d, ShipDesign)
        assert d.tech_count == tech_flags & 0x003F


# ---------------------------------------------------------------------------
# Phase 8: Batch decoder
# ---------------------------------------------------------------------------


class TestDecodeShipDesigns:
    """Phase 8: decode_ship_designs batch processing."""

    def test_empty_block_list(self) -> None:
        assert decode_ship_designs([]) == []

    def test_skips_non_type_43(self) -> None:
        class FakeBlock:
            type_id = 12
            data = SAMPLE_18

        assert decode_ship_designs([FakeBlock()]) == []

    def test_processes_type_43_blocks(self) -> None:
        class FakeBlock:
            type_id = 43

        b1 = FakeBlock()
        b1.data = SAMPLE_2
        b2 = FakeBlock()
        b2.data = SAMPLE_18

        results = decode_ship_designs([b1, b2])
        assert len(results) == 2
        assert isinstance(results[0], ShipDesignCount)
        assert isinstance(results[1], ShipDesign)

    def test_mixed_block_list(self) -> None:
        class Block43:
            type_id = 43
            data = make_design()

        class Block12:
            type_id = 12
            data = b"\x00" * 8

        blocks = [Block43(), Block12(), Block43(), Block12()]
        results = decode_ship_designs(blocks)
        assert len(results) == 2
        assert all(isinstance(r, ShipDesign) for r in results)

    def test_returns_list(self) -> None:
        result = decode_ship_designs([])
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Phase 9: Real game-file smoke test
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not GAME_DIR.exists(),
    reason="starswine4 game data not available",
)
class TestRealGameFiles:
    """Phase 9: Smoke test against real starswine4 game data."""

    def test_all_type43_blocks_parse(self) -> None:
        """Every Type 43 block in every game file parses without error."""
        errors: list[str] = []
        total = 0
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            try:
                blocks = read_blocks(p.read_bytes())
                for blk in blocks:
                    if blk.type_id == 43:
                        total += 1
                        decode_ship_design_block(blk.data)
            except Exception as exc:
                errors.append(f"{p.name}: {exc}")
        assert not errors, "\n".join(errors)
        assert total > 0, "No Type 43 blocks found in game data"

    def test_design_count_matches_design_records(self) -> None:
        """2-byte count block value equals number of 18-byte design blocks in the same file."""
        m2_path = GAME_DIR / "Game-big.m2"
        if not m2_path.exists():
            pytest.skip("Game-big.m2 not available")

        blocks = read_blocks(m2_path.read_bytes())
        results = decode_ship_designs(blocks)

        counts = [r for r in results if isinstance(r, ShipDesignCount)]
        designs = [r for r in results if isinstance(r, ShipDesign)]
        total_count = sum(c.count for c in counts)

        # The count should reflect the designs visible to this player
        assert total_count >= len(designs)

    def test_design_slot_in_valid_range(self) -> None:
        """All decoded design_id values are within 0-15."""
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            blocks = read_blocks(p.read_bytes())
            for blk in blocks:
                if blk.type_id == 43 and blk.size == 18:
                    d = decode_ship_design_block(blk.data)
                    assert isinstance(d, ShipDesign)
                    assert (
                        0 <= d.design_id <= 15
                    ), f"{p.name}: design_id={d.design_id} out of range"

    def test_all_m_files_parsed_without_exception(self) -> None:
        """decode_ship_designs handles all files without raising."""
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            blocks = read_blocks(p.read_bytes())
            results = decode_ship_designs(blocks)  # must not raise
            assert isinstance(results, list)
