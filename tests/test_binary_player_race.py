"""Tests for Type 6 PlayerRaceData binary block parser (binary module).

Phases:
  Phase 1  – PlayerCompact construction & fields
  Phase 2  – PlayerRaceData construction & fields
  Phase 3  – PlayerRaceData immunity properties
  Phase 4  – decode_player_race_block size dispatch
  Phase 5  – Error handling: too-short data
  Phase 6  – Property-based: PlayerCompact round-trip
  Phase 7  – Property-based: PlayerRaceData round-trip
  Phase 8  – Immunity flag properties
  Phase 9  – decode_player_races batch decoder
  Phase 10 – Real game-file smoke test
"""

from __future__ import annotations

import pathlib
import struct

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from stars_web.binary.player_race import (
    HAB_IMMUNE,
    PlayerCompact,
    PlayerRaceData,
    decode_player_race_block,
    decode_player_races,
)
from stars_web.block_reader import read_blocks

# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

GAME_DIR = pathlib.Path(__file__).parent.parent.parent / "starswine4"

# Compact size ≥ 5, < 50
COMPACT_HEX = "0a0000000000638f02bd2203bd229f"  # size 15 real sample

# Full size ≥ 50 – from Game-big.m3 (player 2, PRT=3, game_id=0x094dabee)
FULL_HEX = (
    "02033e002450ff0f76010600eeab4d09"
    "ffffffffffffffffff"
    "07020506060404"
    "0000000000000000000000000000000046020000000000000f6428030000"
    "080d09100a04080001020102010000006102008000000000000000000000"
    "000000000000000000000000000000000000000000000000100202000202"
    "020202020202020202020204bdde576f04bdde5769"
)
FULL_SIZE = 139

KNOWN_GAME_ID = 0x094DABEE


def make_compact(
    record_type: int = 0x0A,
    field_01: int = 0,
    field_03: int = 0,
    extra: bytes = b"\x00" * 10,
) -> bytes:
    hdr = struct.pack("<BHH", record_type, field_01, field_03)
    return hdr + extra


def make_full(
    player_index: int = 2,
    prt_id: int = 3,
    field_02: int = 62,
    field_04: int = 20516,
    field_06: int = 4095,
    field_08: int = 374,
    field_10: int = 6,
    game_id: int = KNOWN_GAME_ID,
    hab_data: bytes = bytes([HAB_IMMUNE] * 9),
    extra: bytes = b"\x00" * 113,
) -> bytes:
    static = struct.pack(
        "<BBHHHHHI",
        player_index,
        prt_id,
        field_02,
        field_04,
        field_06,
        field_08,
        field_10,
        game_id,
    )
    assert len(static) == 16
    assert len(hab_data) == 9
    return static + hab_data + extra


# ---------------------------------------------------------------------------
# Phase 1: PlayerCompact
# ---------------------------------------------------------------------------


class TestPlayerCompact:
    """Phase 1: PlayerCompact (small variant) fields."""

    def test_record_type_stored(self) -> None:
        pc = PlayerCompact(record_type=0x0A, field_01=0, field_03=0, extra=b"")
        assert pc.record_type == 0x0A

    def test_field_01_stored(self) -> None:
        pc = PlayerCompact(record_type=0, field_01=999, field_03=0, extra=b"")
        assert pc.field_01 == 999

    def test_field_03_stored(self) -> None:
        pc = PlayerCompact(record_type=0, field_01=0, field_03=1234, extra=b"")
        assert pc.field_03 == 1234

    def test_extra_stored(self) -> None:
        extra = b"\xDE\xAD\xBE\xEF"
        pc = PlayerCompact(record_type=0, field_01=0, field_03=0, extra=extra)
        assert pc.extra == extra

    def test_frozen(self) -> None:
        pc = PlayerCompact(record_type=0, field_01=0, field_03=0, extra=b"")
        with pytest.raises(Exception):
            pc.record_type = 99  # type: ignore[misc]

    def test_str_representation(self) -> None:
        pc = PlayerCompact(record_type=0x0A, field_01=0, field_03=0, extra=b"")
        s = str(pc)
        assert "PlayerCompact" in s

    def test_equality(self) -> None:
        a = PlayerCompact(record_type=1, field_01=0, field_03=0, extra=b"")
        b = PlayerCompact(record_type=1, field_01=0, field_03=0, extra=b"")
        assert a == b

    def test_inequality(self) -> None:
        a = PlayerCompact(record_type=1, field_01=0, field_03=0, extra=b"")
        b = PlayerCompact(record_type=2, field_01=0, field_03=0, extra=b"")
        assert a != b


# ---------------------------------------------------------------------------
# Phase 2: PlayerRaceData fields
# ---------------------------------------------------------------------------


class TestPlayerRaceDataFields:
    """Phase 2: PlayerRaceData (full variant) field storage."""

    def test_player_index(self) -> None:
        data = make_full(player_index=5)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.player_index == 5

    def test_prt_id(self) -> None:
        data = make_full(prt_id=7)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.prt_id == 7

    def test_field_02(self) -> None:
        data = make_full(field_02=999)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.field_02 == 999

    def test_field_08(self) -> None:
        data = make_full(field_08=12345)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.field_08 == 12345

    def test_field_10(self) -> None:
        data = make_full(field_10=20)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.field_10 == 20

    def test_game_id(self) -> None:
        data = make_full(game_id=KNOWN_GAME_ID)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.game_id == KNOWN_GAME_ID

    def test_hab_data_length(self) -> None:
        data = make_full()
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert len(r.hab_data) == 9

    def test_hab_data_content(self) -> None:
        hab = bytes(range(9))
        data = make_full(hab_data=hab)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.hab_data == hab

    def test_extra_stored(self) -> None:
        extra = b"\xAB" * 50
        data = make_full(extra=extra)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.extra == extra

    def test_frozen(self) -> None:
        r = decode_player_race_block(make_full())
        with pytest.raises(Exception):
            r.player_index = 99  # type: ignore[misc]

    def test_str_representation(self) -> None:
        r = decode_player_race_block(make_full())
        s = str(r)
        assert "PlayerRaceData" in s


# ---------------------------------------------------------------------------
# Phase 3: Immunity properties
# ---------------------------------------------------------------------------


class TestImmunityProperties:
    """Phase 3: grav_immune / temp_immune / rad_immune computed flags."""

    def test_all_immune(self) -> None:
        hab = bytes([HAB_IMMUNE] * 9)
        data = make_full(hab_data=hab)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.grav_immune is True
        assert r.temp_immune is True
        assert r.rad_immune is True

    def test_none_immune(self) -> None:
        hab = bytes([50, 50, 85, 15, 15, 45, 15, 50, 85])
        data = make_full(hab_data=hab)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.grav_immune is False
        assert r.temp_immune is False
        assert r.rad_immune is False

    def test_grav_only_immune(self) -> None:
        hab = bytes([HAB_IMMUNE, HAB_IMMUNE, HAB_IMMUNE, 10, 50, 90, 10, 50, 90])
        data = make_full(hab_data=hab)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.grav_immune is True
        assert r.temp_immune is False
        assert r.rad_immune is False

    def test_is_multiplayer_nonzero_game_id(self) -> None:
        data = make_full(game_id=KNOWN_GAME_ID)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.is_multiplayer is True

    def test_is_multiplayer_zero_game_id(self) -> None:
        data = make_full(game_id=0)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.is_multiplayer is False


# ---------------------------------------------------------------------------
# Phase 4: Dispatch on size
# ---------------------------------------------------------------------------


class TestDecodeDispatch:
    """Phase 4: decode_player_race_block dispatches correctly."""

    def test_compact_below_threshold(self) -> None:
        data = make_compact()
        result = decode_player_race_block(data)
        assert isinstance(result, PlayerCompact)

    def test_full_at_threshold(self) -> None:
        # 25-byte extra → total = 16 + 9 + 25 = 50
        data = make_full(extra=b"\x00" * 25)
        result = decode_player_race_block(data)
        assert isinstance(result, PlayerRaceData)

    def test_full_above_threshold(self) -> None:
        data = make_full()
        result = decode_player_race_block(data)
        assert isinstance(result, PlayerRaceData)

    def test_known_compact_sample(self) -> None:
        data = bytes.fromhex(COMPACT_HEX)
        result = decode_player_race_block(data)
        assert isinstance(result, PlayerCompact)
        assert result.record_type == 0x0A

    def test_known_full_sample(self) -> None:
        data = bytes.fromhex(FULL_HEX)
        result = decode_player_race_block(data)
        assert isinstance(result, PlayerRaceData)
        assert result.player_index == 2
        assert result.prt_id == 3
        assert result.game_id == KNOWN_GAME_ID

    def test_full_sample_all_immune(self) -> None:
        data = bytes.fromhex(FULL_HEX)
        result = decode_player_race_block(data)
        assert isinstance(result, PlayerRaceData)
        assert result.grav_immune is True
        assert result.temp_immune is True
        assert result.rad_immune is True


# ---------------------------------------------------------------------------
# Phase 5: Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Phase 5: Too-short data raises ValueError."""

    @pytest.mark.parametrize("size", [0, 1, 2, 3, 4])
    def test_too_short_raises(self, size: int) -> None:
        with pytest.raises(ValueError, match="too short"):
            decode_player_race_block(bytes(size))

    def test_error_contains_byte_count(self) -> None:
        with pytest.raises(ValueError, match="3"):
            decode_player_race_block(bytes(3))


# ---------------------------------------------------------------------------
# Phase 6: Property-based – PlayerCompact round-trip
# ---------------------------------------------------------------------------


class TestPlayerCompactProperty:
    """Phase 6: Hypothesis round-trip for the compact variant."""

    @given(
        record_type=st.integers(min_value=0, max_value=255),
        field_01=st.integers(min_value=0, max_value=0xFFFF),
        field_03=st.integers(min_value=0, max_value=0xFFFF),
        extra_len=st.integers(min_value=0, max_value=40),
    )
    def test_compact_roundtrip(
        self,
        record_type: int,
        field_01: int,
        field_03: int,
        extra_len: int,
    ) -> None:
        extra = bytes(extra_len)
        data = make_compact(record_type, field_01, field_03, extra)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerCompact)
        assert r.record_type == record_type
        assert r.field_01 == field_01
        assert r.field_03 == field_03
        assert r.extra == extra


# ---------------------------------------------------------------------------
# Phase 7: Property-based – PlayerRaceData round-trip
# ---------------------------------------------------------------------------


class TestPlayerRaceDataProperty:
    """Phase 7: Hypothesis round-trip for the full variant."""

    @given(
        player_index=st.integers(min_value=0, max_value=255),
        prt_id=st.integers(min_value=0, max_value=15),
        field_02=st.integers(min_value=0, max_value=0xFFFF),
        field_04=st.integers(min_value=0, max_value=0xFFFF),
        field_06=st.integers(min_value=0, max_value=0xFFFF),
        field_08=st.integers(min_value=0, max_value=0xFFFF),
        field_10=st.integers(min_value=0, max_value=0xFFFF),
        game_id=st.integers(min_value=0, max_value=0xFFFFFFFF),
        hab_data=st.binary(min_size=9, max_size=9),
        extra=st.binary(min_size=25, max_size=120),
    )
    @settings(max_examples=200)
    def test_full_roundtrip(
        self,
        player_index: int,
        prt_id: int,
        field_02: int,
        field_04: int,
        field_06: int,
        field_08: int,
        field_10: int,
        game_id: int,
        hab_data: bytes,
        extra: bytes,
    ) -> None:
        data = make_full(
            player_index=player_index,
            prt_id=prt_id,
            field_02=field_02,
            field_04=field_04,
            field_06=field_06,
            field_08=field_08,
            field_10=field_10,
            game_id=game_id,
            hab_data=hab_data,
            extra=extra,
        )
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.player_index == player_index
        assert r.prt_id == prt_id
        assert r.field_02 == field_02
        assert r.game_id == game_id
        assert r.hab_data == hab_data
        assert r.extra == extra


# ---------------------------------------------------------------------------
# Phase 8: Immunity flag properties
# ---------------------------------------------------------------------------


class TestImmunityPropertyBased:
    """Phase 8: Hypothesis for immune flags."""

    @given(
        hab_data=st.binary(min_size=9, max_size=9),
    )
    def test_grav_immune_iff_first_byte_ff(self, hab_data: bytes) -> None:
        data = make_full(hab_data=hab_data)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.grav_immune == (hab_data[0] == HAB_IMMUNE)

    @given(
        hab_data=st.binary(min_size=9, max_size=9),
    )
    def test_temp_immune_iff_byte3_ff(self, hab_data: bytes) -> None:
        data = make_full(hab_data=hab_data)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.temp_immune == (hab_data[3] == HAB_IMMUNE)

    @given(
        hab_data=st.binary(min_size=9, max_size=9),
    )
    def test_rad_immune_iff_byte6_ff(self, hab_data: bytes) -> None:
        data = make_full(hab_data=hab_data)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.rad_immune == (hab_data[6] == HAB_IMMUNE)

    @given(game_id=st.integers(min_value=0, max_value=0xFFFFFFFF))
    def test_is_multiplayer_iff_game_id_nonzero(self, game_id: int) -> None:
        data = make_full(game_id=game_id)
        r = decode_player_race_block(data)
        assert isinstance(r, PlayerRaceData)
        assert r.is_multiplayer == (game_id != 0)


# ---------------------------------------------------------------------------
# Phase 9: Batch decoder
# ---------------------------------------------------------------------------


class TestDecodePlayerRaces:
    """Phase 9: decode_player_races batch decoder."""

    def test_empty_returns_empty(self) -> None:
        assert decode_player_races([]) == []

    def test_skips_non_type_6(self) -> None:
        class FakeBlock:
            type_id = 12
            data = make_full()

        assert decode_player_races([FakeBlock()]) == []

    def test_processes_type_6_blocks(self) -> None:
        class FakeBlock:
            type_id = 6

        b1 = FakeBlock()
        b1.data = make_compact()
        b2 = FakeBlock()
        b2.data = make_full()

        results = decode_player_races([b1, b2])
        assert len(results) == 2
        assert isinstance(results[0], PlayerCompact)
        assert isinstance(results[1], PlayerRaceData)

    def test_mixed_blocks(self) -> None:
        class Block6:
            type_id = 6
            data = make_full()

        class Block99:
            type_id = 99
            data = b"\x00" * 20

        blocks = [Block6(), Block99(), Block6()]
        results = decode_player_races(blocks)
        assert len(results) == 2

    def test_returns_list(self) -> None:
        assert isinstance(decode_player_races([]), list)


# ---------------------------------------------------------------------------
# Phase 10: Real game-file smoke test
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not GAME_DIR.exists(),
    reason="starswine4 game data not available",
)
class TestRealGameFiles:
    """Phase 10: Smoke test against real game data."""

    def test_all_type6_blocks_parse(self) -> None:
        """Every Type 6 block in every game file parses without error."""
        errors: list[str] = []
        total = 0
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            blocks = read_blocks(p.read_bytes())
            for blk in blocks:
                if blk.type_id == 6:
                    total += 1
                    try:
                        decode_player_race_block(blk.data)
                    except Exception as exc:
                        errors.append(f"{p.name}: {exc}")
        assert not errors, "\n".join(errors)
        assert total > 0, "No Type 6 blocks found in game data"

    def test_full_blocks_have_known_game_id(self) -> None:
        """Full-variant blocks in multi-player game files carry the expected game ID."""
        found_multiplayer = False
        for p in sorted(GAME_DIR.rglob("Game-big.m?")):
            blocks = read_blocks(p.read_bytes())
            for blk in blocks:
                if blk.type_id == 6:
                    r = decode_player_race_block(blk.data)
                    if isinstance(r, PlayerRaceData) and r.is_multiplayer:
                        assert r.game_id == KNOWN_GAME_ID
                        found_multiplayer = True
        assert found_multiplayer, "No multiplayer PlayerRaceData found"

    def test_full_blocks_player_index_in_range(self) -> None:
        """player_index for full blocks is within 0-15."""
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            blocks = read_blocks(p.read_bytes())
            for blk in blocks:
                if blk.type_id == 6:
                    r = decode_player_race_block(blk.data)
                    if isinstance(r, PlayerRaceData):
                        assert 0 <= r.player_index <= 15, (
                            f"{p.name}: player_index={r.player_index}"
                        )

    def test_hab_data_length_always_nine(self) -> None:
        """Full-variant hab_data is always exactly 9 bytes."""
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            blocks = read_blocks(p.read_bytes())
            for blk in blocks:
                if blk.type_id == 6:
                    r = decode_player_race_block(blk.data)
                    if isinstance(r, PlayerRaceData):
                        assert len(r.hab_data) == 9

    def test_batch_decoder_all_files(self) -> None:
        """decode_player_races handles all files without raising."""
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            blocks = read_blocks(p.read_bytes())
            results = decode_player_races(blocks)
            assert isinstance(results, list)
