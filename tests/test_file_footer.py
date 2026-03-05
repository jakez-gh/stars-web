"""Test Suite for FileFooter Block Parsing (Tier-1 Binary Parsing)

Block Type: 0 (FileFooterBlock)
Purpose: Parse the game year from the 2-byte file footer block.
Location: Last block in every .m# file.

References:
  - starswine4/Game.m1: footer=[18, 0] → year_offset=18 → game_year=2418
  - starswine4/Game-big.m1: footer=[33, 0] → year_offset=33 → game_year=2433
  - stars-4x/starsapi-python BLOCKS dict: type 0 = "FileFooterBlock"
"""

import struct

import pytest
from hypothesis import given, settings, strategies as st

from stars_web.binary.file_footer import (
    FileFooter,
    BLOCK_TYPE_FILE_FOOTER,
    FILE_FOOTER_SIZE,
    STARS_BASE_YEAR,
    decode_file_footer,
)


# ─────────────────────────────────────────────────────────────────────────────
# Real binary fixtures
# ─────────────────────────────────────────────────────────────────────────────

# Game.m1 (2-player game): year_offset=18 → game_year=2418
M1_FOOTER = bytes([18, 0])

# Game-big.m1 (16-player game): year_offset=33 → game_year=2433
BIG_FOOTER = bytes([33, 0])


def _make_footer(year_offset: int) -> bytes:
    return struct.pack("<H", year_offset)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Constants
# ─────────────────────────────────────────────────────────────────────────────


class TestConstants:
    def test_block_type_value(self):
        assert BLOCK_TYPE_FILE_FOOTER == 0

    def test_block_size_two(self):
        assert FILE_FOOTER_SIZE == 2

    def test_base_year_is_2400(self):
        assert STARS_BASE_YEAR == 2400


class TestFileFooterDataclass:
    def test_can_construct(self):
        ff = FileFooter(year_offset=18, game_year=2418)
        assert ff.year_offset == 18

    def test_game_year_relation(self):
        ff = FileFooter(year_offset=50, game_year=2450)
        assert ff.game_year == STARS_BASE_YEAR + ff.year_offset


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Decoding
# ─────────────────────────────────────────────────────────────────────────────


class TestDecoding:
    def test_year_offset_decoded(self):
        ff = decode_file_footer(_make_footer(18))
        assert ff.year_offset == 18

    def test_game_year_computed(self):
        ff = decode_file_footer(_make_footer(18))
        assert ff.game_year == 2418

    def test_year_offset_zero(self):
        ff = decode_file_footer(_make_footer(0))
        assert ff.year_offset == 0
        assert ff.game_year == 2400

    def test_year_offset_one(self):
        ff = decode_file_footer(_make_footer(1))
        assert ff.game_year == 2401

    def test_year_offset_100(self):
        ff = decode_file_footer(_make_footer(100))
        assert ff.game_year == 2500

    def test_year_offset_max_uint16(self):
        ff = decode_file_footer(_make_footer(65535))
        assert ff.year_offset == 65535
        assert ff.game_year == STARS_BASE_YEAR + 65535


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: Error handling
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    def test_raises_on_empty(self):
        with pytest.raises(ValueError, match="2 bytes"):
            decode_file_footer(b"")

    def test_raises_on_one_byte(self):
        with pytest.raises(ValueError):
            decode_file_footer(b"\x12")

    def test_raises_on_three_bytes(self):
        with pytest.raises(ValueError, match="2 bytes"):
            decode_file_footer(bytes(3))

    def test_accepts_exactly_two_bytes(self):
        ff = decode_file_footer(bytes(2))
        assert ff is not None


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Real data validation
# ─────────────────────────────────────────────────────────────────────────────


class TestRealData:
    def test_m1_year_offset(self):
        ff = decode_file_footer(M1_FOOTER)
        assert ff.year_offset == 18

    def test_m1_game_year(self):
        ff = decode_file_footer(M1_FOOTER)
        assert ff.game_year == 2418

    def test_big_year_offset(self):
        ff = decode_file_footer(BIG_FOOTER)
        assert ff.year_offset == 33

    def test_big_game_year(self):
        ff = decode_file_footer(BIG_FOOTER)
        assert ff.game_year == 2433

    def test_big_game_later_than_m1(self):
        ff_m1 = decode_file_footer(M1_FOOTER)
        ff_big = decode_file_footer(BIG_FOOTER)
        assert ff_big.game_year > ff_m1.game_year


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5: Property-based invariants
# ─────────────────────────────────────────────────────────────────────────────


class TestPropertyBased:
    @given(year_offset=st.integers(min_value=0, max_value=65535))
    @settings(max_examples=100, deadline=None)
    def test_round_trip(self, year_offset):
        ff = decode_file_footer(_make_footer(year_offset))
        assert ff.year_offset == year_offset
        assert ff.game_year == STARS_BASE_YEAR + year_offset

    @given(year_offset=st.integers(min_value=0, max_value=65535))
    @settings(max_examples=50, deadline=None)
    def test_game_year_always_at_least_base(self, year_offset):
        ff = decode_file_footer(_make_footer(year_offset))
        assert ff.game_year >= STARS_BASE_YEAR
