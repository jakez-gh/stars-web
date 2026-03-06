"""Tests for Type 31 BattleRecord binary decoder.

Phases:
  Phase 1  – BattleToken fields
  Phase 2  – BattleRecord header fields
  Phase 3  – BattleRecord token parsing
  Phase 4  – BattleRecord event data
  Phase 5  – decode_battle_block size dispatch and properties
  Phase 6  – Error handling: too-short data
  Phase 7  – Property-based: header round-trip
  Phase 8  – BattleRecord.token_count property
  Phase 9  – decode_battles batch decoder
  Phase 10 – Real game-file smoke test
"""

from __future__ import annotations

import pathlib
import struct

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from stars_web.binary.battle_record import (
    BLOCK_TYPE_BATTLE,
    BattleRecord,
    BattleToken,
    decode_battle_block,
    decode_battles,
)
from stars_web.block_reader import read_blocks

# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

GAME_DIR = pathlib.Path(__file__).parent.parent.parent / "starswine4"

_TOKEN_SIZE = 24
_HEADER_SIZE = 16


def make_token(content: bytes | None = None) -> bytes:
    """Return pad-filled 24-byte token."""
    if content is None:
        return bytes(_TOKEN_SIZE)
    assert len(content) == _TOKEN_SIZE
    return content


def make_battle(
    battle_id: int = 1,
    num_tokens: int = 0,
    x: int = 100,
    y: int = 200,
    header_extra: bytes = b"\x00\x00\x00\x00",
    token_data: bytes = b"",
    events: bytes = b"",
) -> bytes:
    """Build a synthetic Type 31 block."""
    block_size = _HEADER_SIZE + len(token_data) + len(events)
    hdr = bytes([
        battle_id,       # byte 0
        0x00,            # byte 1 reserved
        0x02,            # byte 2 version
        num_tokens,      # byte 3 num_tokens
        0x00,            # byte 4 battle_size_x
        0x03,            # byte 5 battle_size_y
    ])
    hdr += struct.pack("<H", block_size)   # bytes 6-7
    hdr += struct.pack("<H", x)            # bytes 8-9
    hdr += struct.pack("<H", y)            # bytes 10-11
    hdr += header_extra                    # bytes 12-15
    return hdr + token_data + events


# ---------------------------------------------------------------------------
# Phase 1: BattleToken
# ---------------------------------------------------------------------------


class TestBattleToken:
    """Phase 1: BattleToken basic properties."""

    def test_raw_stored(self) -> None:
        raw = bytes(range(24))
        t = BattleToken(raw=raw)
        assert t.raw == raw

    def test_len_is_24(self) -> None:
        t = BattleToken(raw=bytes(24))
        assert len(t) == 24

    def test_str_contains_class_name(self) -> None:
        t = BattleToken(raw=bytes(24))
        assert "BattleToken" in str(t)

    def test_frozen(self) -> None:
        t = BattleToken(raw=bytes(24))
        with pytest.raises(Exception):
            t.raw = bytes(24)  # type: ignore[misc]

    def test_equality(self) -> None:
        a = BattleToken(raw=bytes(24))
        b = BattleToken(raw=bytes(24))
        assert a == b

    def test_inequality(self) -> None:
        a = BattleToken(raw=bytes(24))
        b = BattleToken(raw=bytes([1] + [0] * 23))
        assert a != b


# ---------------------------------------------------------------------------
# Phase 2: BattleRecord header
# ---------------------------------------------------------------------------


class TestBattleRecordHeader:
    """Phase 2: BattleRecord header fields."""

    def test_battle_id(self) -> None:
        data = make_battle(battle_id=3)
        r = decode_battle_block(data)
        assert r.battle_id == 3

    def test_num_tokens(self) -> None:
        data = make_battle(num_tokens=0)
        r = decode_battle_block(data)
        assert r.num_tokens == 0

    def test_x(self) -> None:
        data = make_battle(x=512)
        r = decode_battle_block(data)
        assert r.x == 512

    def test_y(self) -> None:
        data = make_battle(y=1024)
        r = decode_battle_block(data)
        assert r.y == 1024

    def test_block_size_matches_actual(self) -> None:
        data = make_battle()
        r = decode_battle_block(data)
        assert r.block_size == len(data)

    def test_header_extra_stored(self) -> None:
        extra = bytes([0xAA, 0xBB, 0xCC, 0xDD])
        data = make_battle(header_extra=extra)
        r = decode_battle_block(data)
        assert r.header_extra == extra

    def test_header_extra_length(self) -> None:
        data = make_battle()
        r = decode_battle_block(data)
        assert len(r.header_extra) == 4

    def test_raw_stored(self) -> None:
        data = make_battle()
        r = decode_battle_block(data)
        assert r.raw == data

    def test_frozen(self) -> None:
        r = decode_battle_block(make_battle())
        with pytest.raises(Exception):
            r.battle_id = 99  # type: ignore[misc]

    def test_str_contains_class_name(self) -> None:
        r = decode_battle_block(make_battle())
        assert "BattleRecord" in str(r)


# ---------------------------------------------------------------------------
# Phase 3: Token parsing
# ---------------------------------------------------------------------------


class TestTokenParsing:
    """Phase 3: Token records decoded from data."""

    def test_zero_tokens(self) -> None:
        data = make_battle(num_tokens=0)
        r = decode_battle_block(data)
        assert r.tokens == ()

    def test_single_token(self) -> None:
        tok = make_token(bytes(range(24)))
        data = make_battle(num_tokens=1, token_data=tok)
        r = decode_battle_block(data)
        assert len(r.tokens) == 1
        assert isinstance(r.tokens[0], BattleToken)

    def test_token_raw_preserved(self) -> None:
        tok_bytes = bytes(range(24))
        tok = make_token(tok_bytes)
        data = make_battle(num_tokens=1, token_data=tok)
        r = decode_battle_block(data)
        assert r.tokens[0].raw == tok_bytes

    def test_two_tokens(self) -> None:
        tok1 = bytes([0xAA] * 24)
        tok2 = bytes([0xBB] * 24)
        data = make_battle(num_tokens=2, token_data=tok1 + tok2)
        r = decode_battle_block(data)
        assert len(r.tokens) == 2
        assert r.tokens[0].raw == tok1
        assert r.tokens[1].raw == tok2

    def test_tokens_is_tuple(self) -> None:
        data = make_battle(num_tokens=0)
        r = decode_battle_block(data)
        assert isinstance(r.tokens, tuple)

    def test_token_count_property_matches(self) -> None:
        tok = make_token()
        data = make_battle(num_tokens=1, token_data=tok)
        r = decode_battle_block(data)
        assert r.token_count == 1


# ---------------------------------------------------------------------------
# Phase 4: Event data
# ---------------------------------------------------------------------------


class TestEventData:
    """Phase 4: Battle event raw bytes."""

    def test_no_events(self) -> None:
        data = make_battle()
        r = decode_battle_block(data)
        assert r.events_raw == b""

    def test_events_stored(self) -> None:
        events = bytes([0x01, 0x02, 0x03, 0x04])
        data = make_battle(events=events)
        r = decode_battle_block(data)
        assert r.events_raw == events

    def test_events_after_tokens(self) -> None:
        tok = make_token()
        events = bytes([0xFF, 0xFE, 0xFD])
        data = make_battle(num_tokens=1, token_data=tok, events=events)
        r = decode_battle_block(data)
        assert r.events_raw == events

    def test_events_raw_is_bytes(self) -> None:
        data = make_battle()
        r = decode_battle_block(data)
        assert isinstance(r.events_raw, bytes)


# ---------------------------------------------------------------------------
# Phase 5: Properties
# ---------------------------------------------------------------------------


class TestProperties:
    """Phase 5: BattleRecord computed properties."""

    def test_token_count_zero(self) -> None:
        r = decode_battle_block(make_battle(num_tokens=0))
        assert r.token_count == 0

    def test_token_count_matches_num_tokens(self) -> None:
        tokens = make_token() * 4  # 4 × 24 bytes
        data = make_battle(num_tokens=4, token_data=tokens)
        r = decode_battle_block(data)
        assert r.token_count == 4

    def test_block_type_constant(self) -> None:
        assert BLOCK_TYPE_BATTLE == 31


# ---------------------------------------------------------------------------
# Phase 6: Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Phase 6: Too-short data raises ValueError."""

    @pytest.mark.parametrize("size", [0, 1, 5, 10, 15])
    def test_too_short_raises(self, size: int) -> None:
        with pytest.raises(ValueError, match="too short"):
            decode_battle_block(bytes(size))

    def test_error_mentions_byte_count(self) -> None:
        with pytest.raises(ValueError, match="5"):
            decode_battle_block(bytes(5))


# ---------------------------------------------------------------------------
# Phase 7: Property-based – header round-trip
# ---------------------------------------------------------------------------


class TestPropertyBased:
    """Phase 7: Hypothesis round-trip for header fields."""

    @given(
        battle_id=st.integers(min_value=0, max_value=255),
        num_tokens=st.integers(min_value=0, max_value=20),
        x=st.integers(min_value=0, max_value=0xFFFF),
        y=st.integers(min_value=0, max_value=0xFFFF),
        extra=st.binary(min_size=4, max_size=4),
        events=st.binary(min_size=0, max_size=50),
    )
    @settings(max_examples=200)
    def test_header_roundtrip(
        self,
        battle_id: int,
        num_tokens: int,
        x: int,
        y: int,
        extra: bytes,
        events: bytes,
    ) -> None:
        token_data = bytes(num_tokens * _TOKEN_SIZE)
        data = make_battle(
            battle_id=battle_id,
            num_tokens=num_tokens,
            x=x,
            y=y,
            header_extra=extra,
            token_data=token_data,
            events=events,
        )
        r = decode_battle_block(data)
        assert r.battle_id == battle_id
        assert r.num_tokens == num_tokens
        assert r.x == x
        assert r.y == y
        assert r.header_extra == extra
        assert r.events_raw == events
        assert r.token_count == num_tokens
        assert r.block_size == len(data)


# ---------------------------------------------------------------------------
# Phase 8: token_count property
# ---------------------------------------------------------------------------


class TestTokenCountProperty:
    """Phase 8: token_count always equals len(tokens) tuple."""

    @given(n=st.integers(min_value=0, max_value=15))
    def test_token_count_equals_tuple_len(self, n: int) -> None:
        data = make_battle(num_tokens=n, token_data=bytes(n * _TOKEN_SIZE))
        r = decode_battle_block(data)
        assert r.token_count == len(r.tokens)


# ---------------------------------------------------------------------------
# Phase 9: Batch decoder
# ---------------------------------------------------------------------------


class TestDecodeBattles:
    """Phase 9: decode_battles batch decoder."""

    def test_empty_returns_empty(self) -> None:
        assert decode_battles([]) == []

    def test_skips_non_type_31(self) -> None:
        class FakeBlock:
            type_id = 6
            data = make_battle()

        assert decode_battles([FakeBlock()]) == []

    def test_processes_type_31_blocks(self) -> None:
        class FakeBlock:
            type_id = 31

        b1 = FakeBlock()
        b1.data = make_battle(battle_id=1)
        b2 = FakeBlock()
        b2.data = make_battle(battle_id=2)

        results = decode_battles([b1, b2])
        assert len(results) == 2
        assert results[0].battle_id == 1
        assert results[1].battle_id == 2

    def test_mixed_blocks_skipped(self) -> None:
        class B31:
            type_id = 31
            data = make_battle()

        class B6:
            type_id = 6
            data = make_battle()

        assert len(decode_battles([B31(), B6(), B31()])) == 2

    def test_returns_list(self) -> None:
        assert isinstance(decode_battles([]), list)


# ---------------------------------------------------------------------------
# Phase 10: Real game-file smoke test
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not GAME_DIR.exists(),
    reason="starswine4 game data not available",
)
class TestRealGameFiles:
    """Phase 10: Smoke tests against real starswine4 game data."""

    def test_all_type31_blocks_parse(self) -> None:
        errors: list[str] = []
        total = 0
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            for blk in read_blocks(p.read_bytes()):
                if blk.type_id == 31:
                    total += 1
                    try:
                        decode_battle_block(blk.data)
                    except Exception as exc:
                        errors.append(f"{p.name}: {exc}")
        assert not errors, "\n".join(errors)
        assert total > 0, "No Type 31 blocks found"

    def test_block_count_is_four(self) -> None:
        total = sum(
            1
            for p in GAME_DIR.rglob("*.m?")
            if p.suffix != ".md"
            for blk in read_blocks(p.read_bytes())
            if blk.type_id == 31
        )
        assert total == 4

    def test_battle_ids_sequential(self) -> None:
        ids = []
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            for blk in read_blocks(p.read_bytes()):
                if blk.type_id == 31:
                    r = decode_battle_block(blk.data)
                    ids.append(r.battle_id)
        assert sorted(ids) == list(range(1, len(ids) + 1))

    def test_block_size_matches_actual_data(self) -> None:
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            for blk in read_blocks(p.read_bytes()):
                if blk.type_id == 31:
                    r = decode_battle_block(blk.data)
                    assert r.block_size == len(blk.data), (
                        f"{p.name}: block_size={r.block_size} != actual={len(blk.data)}"
                    )

    def test_token_count_matches_header(self) -> None:
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            for blk in read_blocks(p.read_bytes()):
                if blk.type_id == 31:
                    r = decode_battle_block(blk.data)
                    assert r.token_count == r.num_tokens

    def test_x_y_coordinates_in_range(self) -> None:
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            for blk in read_blocks(p.read_bytes()):
                if blk.type_id == 31:
                    r = decode_battle_block(blk.data)
                    assert 0 <= r.x <= 0xFFFF
                    assert 0 <= r.y <= 0xFFFF

    def test_all_battle_ids_positive(self) -> None:
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            for blk in read_blocks(p.read_bytes()):
                if blk.type_id == 31:
                    r = decode_battle_block(blk.data)
                    assert r.battle_id >= 1

    def test_batch_decoder_all_files(self) -> None:
        for p in sorted(GAME_DIR.rglob("*.m?")):
            if p.suffix == ".md":
                continue
            results = decode_battles(read_blocks(p.read_bytes()))
            assert isinstance(results, list)
