"""Test Suite for PlayerScores Block Parsing (Tier-1 Binary Parsing)

Block Type: 45 (PlayerScoresBlock)
Purpose: Parse per-player score snapshots from .m# game state files.
Location: Each .m# file has one block per player in the game.

Block format: Fixed 24 bytes encoding player_id, planets count, score totals,
and several other game metrics.

Related Issues: Tier-1 binary parsing work
Pattern: Test-driven development

References:
  - starswine4/Game.m1, Game.m2, Game-big.m1, Game-big.m2 (real test data)
  - stars-4x/starsapi-python BLOCKS dict: type 45 = "PlayerScoresBlock"
"""

import struct

import pytest
from hypothesis import given, settings, strategies as st

from stars_web.binary.player_scores import (
    PlayerScore,
    BLOCK_TYPE_PLAYER_SCORES,
    PLAYER_SCORES_BLOCK_SIZE,
    PLAYER_RAW_OFFSET,
    decode_player_score,
    decode_player_scores,
)


# ─────────────────────────────────────────────────────────────────────────────
# Real binary fixtures (decrypted, extracted from starswine4/ game files)
# ─────────────────────────────────────────────────────────────────────────────

# ── starswine4/Game.m1 (2-player game) ──────────────────────────────────────
#   player_id=0, num_planets=2, resources_a=29, total_score=172,
#   starbases=2, ships_unarmed=1, ships_escort=3, ships_capital=0,
#   tech_score=0, rank=18
M1_PLAYER0 = bytes(
    [
        32,
        0,  # d[0:2]: player_raw = 32 → player_id = 0
        2,
        0,  # d[2:4]: num_planets = 2
        29,
        0,
        0,
        0,  # d[4:8]: resources_a = 29 (uint32)
        172,
        0,
        0,
        0,  # d[8:12]: total_score = 172 (uint32)
        2,
        0,  # d[12:14]: starbases = 2
        1,
        0,  # d[14:16]: ships_unarmed = 1
        3,
        0,  # d[16:18]: ships_escort = 3
        0,
        0,  # d[18:20]: ships_capital = 0
        0,
        0,  # d[20:22]: tech_score = 0
        18,
        0,  # d[22:24]: rank = 18
    ]
)

# ── starswine4/Game.m2 (2-player game) ──────────────────────────────────────
#   player_id=1, num_planets=1, resources_a=40, total_score=438,
#   starbases=2, ships_unarmed=1, ships_escort=1, ships_capital=0,
#   tech_score=0, rank=19
M2_PLAYER1 = bytes(
    [
        33,
        0,  # player_raw = 33 → player_id = 1
        1,
        0,  # num_planets = 1
        40,
        0,
        0,
        0,  # resources_a = 40
        182,
        1,
        0,
        0,  # total_score = 438
        2,
        0,  # starbases = 2
        1,
        0,  # ships_unarmed = 1
        1,
        0,  # ships_escort = 1
        0,
        0,  # ships_capital = 0
        0,
        0,  # tech_score = 0
        19,
        0,  # rank = 19
    ]
)

# ── starswine4/Game-big.m1 (16-player game, first two entries) ───────────────
# Block 0: player_id=0, 16 planets, score=1674
BIG_PLAYER0 = bytes(
    [
        32,
        0,  # player_raw = 32 → player_id = 0
        16,
        0,  # num_planets = 16
        100,
        0,
        0,
        0,  # resources_a = 100
        138,
        6,
        0,
        0,  # total_score = 1674
        5,
        0,  # starbases = 5
        1,
        0,  # ships_unarmed = 1
        4,
        0,  # ships_escort = 4
        2,
        0,  # ships_capital = 2
        0,
        0,  # tech_score = 0
        22,
        0,  # rank = 22
    ]
)

# Block 1: player_id=1, 4 planets, score=2423
BIG_PLAYER1 = bytes(
    [
        33,
        0,  # player_raw = 33 → player_id = 1
        4,
        0,  # num_planets = 4
        211,
        0,
        0,
        0,  # resources_a = 211
        119,
        9,
        0,
        0,  # total_score = 2423
        43,
        0,  # starbases = 43
        3,
        0,  # ships_unarmed = 3
        19,
        0,  # ships_escort = 19
        0,
        0,  # ships_capital = 0
        0,
        0,  # tech_score = 0
        37,
        0,  # rank = 37
    ]
)

# Block 2: player_id=2, 6 planets, score=2152
BIG_PLAYER2 = bytes(
    [
        34,
        0,
        6,
        0,
        200,
        0,
        0,
        0,
        104,
        8,
        0,
        0,
        58,
        0,
        1,
        0,
        29,
        0,
        7,
        0,
        0,
        0,
        27,
        0,
    ]
)

# Block 4: player_id=4, 13 planets, score=1188
BIG_PLAYER4 = bytes(
    [
        36,
        0,
        13,
        0,
        138,
        0,
        0,
        0,
        164,
        4,
        0,
        0,
        49,
        0,
        1,
        0,
        33,
        0,
        0,
        0,
        0,
        0,
        23,
        0,
    ]
)


def _make_score_block(
    player_id: int = 0,
    num_planets: int = 0,
    resources_a: int = 0,
    total_score: int = 0,
    starbases: int = 0,
    ships_unarmed: int = 0,
    ships_escort: int = 0,
    ships_capital: int = 0,
    tech_score: int = 0,
    rank: int = 0,
) -> bytes:
    """Build a synthetic 24-byte PlayerScores block payload."""
    player_raw = player_id + PLAYER_RAW_OFFSET
    return struct.pack(
        "<HHIIHHHHHH",
        player_raw,
        num_planets,
        resources_a,
        total_score,
        starbases,
        ships_unarmed,
        ships_escort,
        ships_capital,
        tech_score,
        rank,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Constants and dataclass structure
# ─────────────────────────────────────────────────────────────────────────────


class TestConstants:
    """Verify module-level constants."""

    def test_block_type_value(self):
        assert BLOCK_TYPE_PLAYER_SCORES == 45

    def test_block_size_24(self):
        assert PLAYER_SCORES_BLOCK_SIZE == 24

    def test_player_raw_offset_32(self):
        assert PLAYER_RAW_OFFSET == 32

    def test_struct_format_matches_block_size(self):
        """Confirm the struct formula produces exactly 24 bytes."""
        assert struct.calcsize("<HHIIHHHHHH") == PLAYER_SCORES_BLOCK_SIZE


class TestPlayerScoreDataclass:
    """Verify PlayerScore dataclass fields and types."""

    def test_can_construct(self):
        ps = PlayerScore(
            player_id=0,
            num_planets=2,
            resources_a=29,
            total_score=172,
            starbases=2,
            ships_unarmed=1,
            ships_escort=3,
            ships_capital=0,
            tech_score=0,
            rank=18,
            raw=bytes(24),
        )
        assert ps.player_id == 0

    def test_raw_field_stores_bytes(self):
        data = _make_score_block(player_id=0, total_score=500)
        ps = decode_player_score(data)
        assert isinstance(ps.raw, bytes)
        assert len(ps.raw) == 24

    def test_raw_preserves_original(self):
        data = _make_score_block(player_id=3, num_planets=7)
        ps = decode_player_score(data)
        assert ps.raw == data


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: player_id decoding (player_raw → player_id)
# ─────────────────────────────────────────────────────────────────────────────


class TestPlayerIdDecoding:
    """Verify player_raw → player_id offset subtraction."""

    def test_player_id_zero(self):
        data = _make_score_block(player_id=0)
        ps = decode_player_score(data)
        assert ps.player_id == 0

    def test_player_id_one(self):
        data = _make_score_block(player_id=1)
        ps = decode_player_score(data)
        assert ps.player_id == 1

    def test_player_id_fifteen(self):
        data = _make_score_block(player_id=15)
        ps = decode_player_score(data)
        assert ps.player_id == 15

    def test_player_raw_is_player_id_plus_offset(self):
        """Verify the raw byte before subtraction is player_id + PLAYER_RAW_OFFSET."""
        for pid in range(16):
            data = _make_score_block(player_id=pid)
            ps = decode_player_score(data)
            assert ps.player_id == pid

    def test_player_id_from_real_m1(self):
        ps = decode_player_score(M1_PLAYER0)
        assert ps.player_id == 0

    def test_player_id_from_real_m2(self):
        ps = decode_player_score(M2_PLAYER1)
        assert ps.player_id == 1


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: Integer field decoding
# ─────────────────────────────────────────────────────────────────────────────


class TestNumericFields:
    """Verify all numeric fields are correctly parsed."""

    def test_num_planets(self):
        data = _make_score_block(num_planets=12)
        ps = decode_player_score(data)
        assert ps.num_planets == 12

    def test_num_planets_max_uint16(self):
        data = _make_score_block(num_planets=65535)
        ps = decode_player_score(data)
        assert ps.num_planets == 65535

    def test_resources_a(self):
        data = _make_score_block(resources_a=999)
        ps = decode_player_score(data)
        assert ps.resources_a == 999

    def test_total_score_large_value(self):
        data = _make_score_block(total_score=100000)
        ps = decode_player_score(data)
        assert ps.total_score == 100000

    def test_total_score_uint32_max(self):
        data = _make_score_block(total_score=4_294_967_295)
        ps = decode_player_score(data)
        assert ps.total_score == 4_294_967_295

    def test_starbases(self):
        data = _make_score_block(starbases=3)
        ps = decode_player_score(data)
        assert ps.starbases == 3

    def test_ships_unarmed(self):
        data = _make_score_block(ships_unarmed=7)
        ps = decode_player_score(data)
        assert ps.ships_unarmed == 7

    def test_ships_escort(self):
        data = _make_score_block(ships_escort=5)
        ps = decode_player_score(data)
        assert ps.ships_escort == 5

    def test_ships_capital(self):
        data = _make_score_block(ships_capital=2)
        ps = decode_player_score(data)
        assert ps.ships_capital == 2

    def test_tech_score(self):
        data = _make_score_block(tech_score=10)
        ps = decode_player_score(data)
        assert ps.tech_score == 10

    def test_rank(self):
        data = _make_score_block(rank=1)
        ps = decode_player_score(data)
        assert ps.rank == 1


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Error handling
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Verify decode_player_score raises on invalid input."""

    def test_raises_on_too_short(self):
        with pytest.raises(ValueError, match="24 bytes"):
            decode_player_score(bytes(10))

    def test_raises_on_empty(self):
        with pytest.raises(ValueError):
            decode_player_score(b"")

    def test_raises_on_too_long(self):
        with pytest.raises(ValueError, match="24 bytes"):
            decode_player_score(bytes(25))

    def test_accepts_exactly_24_bytes(self):
        data = bytes(24)
        ps = decode_player_score(data)
        assert ps is not None

    def test_batch_raises_on_bad_size_in_list(self):
        with pytest.raises(ValueError):
            decode_player_scores([bytes(10)])


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5: Real data validation
# ─────────────────────────────────────────────────────────────────────────────


class TestRealData2Player:
    """Validate against Game.m1 and Game.m2 (2-player game)."""

    def test_m1_player_id(self):
        ps = decode_player_score(M1_PLAYER0)
        assert ps.player_id == 0

    def test_m1_num_planets(self):
        ps = decode_player_score(M1_PLAYER0)
        assert ps.num_planets == 2

    def test_m1_resources_a(self):
        ps = decode_player_score(M1_PLAYER0)
        assert ps.resources_a == 29

    def test_m1_total_score(self):
        ps = decode_player_score(M1_PLAYER0)
        assert ps.total_score == 172

    def test_m1_rank(self):
        ps = decode_player_score(M1_PLAYER0)
        assert ps.rank == 18

    def test_m2_player_id(self):
        ps = decode_player_score(M2_PLAYER1)
        assert ps.player_id == 1

    def test_m2_num_planets(self):
        ps = decode_player_score(M2_PLAYER1)
        assert ps.num_planets == 1

    def test_m2_total_score(self):
        ps = decode_player_score(M2_PLAYER1)
        assert ps.total_score == 438

    def test_m2_rank(self):
        ps = decode_player_score(M2_PLAYER1)
        assert ps.rank == 19

    def test_raw_preserved_m1(self):
        ps = decode_player_score(M1_PLAYER0)
        assert ps.raw == M1_PLAYER0

    def test_raw_preserved_m2(self):
        ps = decode_player_score(M2_PLAYER1)
        assert ps.raw == M2_PLAYER1


class TestRealData16Player:
    """Validate against Game-big.m1 (16-player game)."""

    def test_big_p0_player_id(self):
        ps = decode_player_score(BIG_PLAYER0)
        assert ps.player_id == 0

    def test_big_p0_num_planets(self):
        ps = decode_player_score(BIG_PLAYER0)
        assert ps.num_planets == 16

    def test_big_p0_total_score(self):
        ps = decode_player_score(BIG_PLAYER0)
        assert ps.total_score == 1674

    def test_big_p1_player_id(self):
        ps = decode_player_score(BIG_PLAYER1)
        assert ps.player_id == 1

    def test_big_p1_num_planets(self):
        ps = decode_player_score(BIG_PLAYER1)
        assert ps.num_planets == 4

    def test_big_p1_total_score(self):
        ps = decode_player_score(BIG_PLAYER1)
        assert ps.total_score == 2423

    def test_big_p2_player_id(self):
        ps = decode_player_score(BIG_PLAYER2)
        assert ps.player_id == 2

    def test_big_p4_player_id(self):
        ps = decode_player_score(BIG_PLAYER4)
        assert ps.player_id == 4

    def test_big_p4_num_planets(self):
        ps = decode_player_score(BIG_PLAYER4)
        assert ps.num_planets == 13


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6: Batch decoder
# ─────────────────────────────────────────────────────────────────────────────


class TestBatchDecoder:
    """Validate decode_player_scores() (multi-block pipeline)."""

    def test_empty_list_returns_empty(self):
        result = decode_player_scores([])
        assert result == []

    def test_single_block_returns_one(self):
        result = decode_player_scores([M1_PLAYER0])
        assert len(result) == 1

    def test_two_player_game(self):
        result = decode_player_scores([M1_PLAYER0, M2_PLAYER1])
        assert len(result) == 2

    def test_order_preserved(self):
        result = decode_player_scores([M2_PLAYER1, M1_PLAYER0])
        assert result[0].player_id == 1
        assert result[1].player_id == 0

    def test_16_player_blocks(self):
        blocks = [BIG_PLAYER0, BIG_PLAYER1, BIG_PLAYER2, BIG_PLAYER4]
        result = decode_player_scores(blocks)
        assert len(result) == 4
        pids = [ps.player_id for ps in result]
        assert pids == [0, 1, 2, 4]

    def test_total_score_non_zero_in_all(self):
        result = decode_player_scores([BIG_PLAYER0, BIG_PLAYER1, BIG_PLAYER2])
        for ps in result:
            assert ps.total_score > 0

    def test_player_ids_sequential_in_big_game(self):
        blocks = [BIG_PLAYER0, BIG_PLAYER1, BIG_PLAYER2]
        result = decode_player_scores(blocks)
        for i, ps in enumerate(result):
            assert ps.player_id == i


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7: Property-based invariants
# ─────────────────────────────────────────────────────────────────────────────


class TestPropertyBasedInvariants:
    """Hypothesis-based tests for broad input coverage."""

    @given(
        player_id=st.integers(min_value=0, max_value=15),
        num_planets=st.integers(min_value=0, max_value=500),
        total_score=st.integers(min_value=0, max_value=2**32 - 1),
    )
    @settings(max_examples=80, deadline=None)
    def test_round_trip_key_fields(self, player_id, num_planets, total_score):
        data = _make_score_block(
            player_id=player_id,
            num_planets=num_planets,
            total_score=total_score,
        )
        ps = decode_player_score(data)
        assert ps.player_id == player_id
        assert ps.num_planets == num_planets
        assert ps.total_score == total_score

    @given(resources_a=st.integers(min_value=0, max_value=2**32 - 1))
    @settings(max_examples=60, deadline=None)
    def test_resources_a_roundtrip(self, resources_a):
        data = _make_score_block(resources_a=resources_a)
        ps = decode_player_score(data)
        assert ps.resources_a == resources_a

    @given(rank=st.integers(min_value=0, max_value=65535))
    @settings(max_examples=60, deadline=None)
    def test_rank_roundtrip(self, rank):
        data = _make_score_block(rank=rank)
        ps = decode_player_score(data)
        assert ps.rank == rank

    @given(data=st.binary(min_size=24, max_size=24))
    @settings(max_examples=100, deadline=None)
    def test_no_crash_on_arbitrary_24_bytes(self, data):
        """decode_player_score must never raise on valid-length input."""
        ps = decode_player_score(data)
        assert isinstance(ps.player_id, int)
        assert isinstance(ps.total_score, int)
