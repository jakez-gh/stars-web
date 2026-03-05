"""Test Suite for BattlePlan Block Parsing (Tier-1 Binary Parsing)

Block Type: 30 (BattlePlanBlock)
Purpose: Parse battle plan slot configuration from .m# game state files.
Location: 5 blocks per player file, one per plan slot 0..4.

Key finding: d[0] = (slot_index << 4) | player_id
Body bytes d[1..N] are identical between m1 and m2 for the same slot.

Related Issues: Tier-1 binary parsing work
Pattern: Test-driven development

References:
  - starswine4/Game.m1, Game.m2, Game-big.m1 (real test data)
  - stars-4x/starsapi-python BLOCKS dict: type 30 = "BattlePlanBlock"
"""

import pytest
from hypothesis import given, settings, strategies as st

from stars_web.binary.battle_plan import (
    BattlePlan,
    BLOCK_TYPE_BATTLE_PLAN,
    BATTLE_PLAN_SLOT_COUNT,
    decode_battle_plan,
    decode_battle_plans,
)


# ─────────────────────────────────────────────────────────────────────────────
# Real binary fixtures (decrypted, extracted from starswine4/ game files)
# All body bytes are identical between Game.m1 and Game.m2 for the same slot.
# ─────────────────────────────────────────────────────────────────────────────

# ── Game.m1 (player 0, 2-player game) ───────────────────────────────────────
# Slot 0: d[0]=0x00 → slot=0 player=0
M1_PLAN_S0 = bytes([0, 4, 19, 2, 5, 179, 45, 113, 222, 90])
# Slot 1: d[0]=0x10 → slot=1 player=0
M1_PLAN_S1 = bytes([16, 4, 50, 2, 8, 186, 69, 80, 194, 161, 141, 65, 146])
# Slot 2: d[0]=0x20 → slot=2 player=0
M1_PLAN_S2 = bytes([32, 3, 67, 2, 8, 188, 30, 30, 91, 50, 215, 38, 146])
# Slot 3: d[0]=0x30 → slot=3 player=0
M1_PLAN_S3 = bytes([48, 1, 5, 2, 4, 194, 100, 220, 40])
# Slot 4: d[0]=0x40 → slot=4 player=0
M1_PLAN_S4 = bytes([64, 0, 1, 2, 5, 178, 52, 213, 218, 38])

ALL_M1_PLANS = [M1_PLAN_S0, M1_PLAN_S1, M1_PLAN_S2, M1_PLAN_S3, M1_PLAN_S4]

# ── Game.m2 (player 1, 2-player game) ───────────────────────────────────────
# Same body bytes as m1, only player nibble differs
M2_PLAN_S0 = bytes([1, 4, 19, 2, 5, 179, 45, 113, 222, 90])
M2_PLAN_S1 = bytes([17, 4, 50, 2, 8, 186, 69, 80, 194, 161, 141, 65, 146])
M2_PLAN_S2 = bytes([33, 3, 67, 2, 8, 188, 30, 30, 91, 50, 215, 38, 146])
M2_PLAN_S3 = bytes([49, 1, 5, 2, 4, 194, 100, 220, 40])
M2_PLAN_S4 = bytes([65, 0, 1, 2, 5, 178, 52, 213, 218, 38])

ALL_M2_PLANS = [M2_PLAN_S0, M2_PLAN_S1, M2_PLAN_S2, M2_PLAN_S3, M2_PLAN_S4]


def _make_plan(slot: int, player: int, body: bytes = b"\x00\x00\x00\x00") -> bytes:
    """Build a synthetic BattlePlan block payload."""
    header = bytes([(slot << 4) | (player & 0x0F)])
    return header + body


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Constants
# ─────────────────────────────────────────────────────────────────────────────


class TestConstants:
    """Verify module-level constants."""

    def test_block_type_value(self):
        assert BLOCK_TYPE_BATTLE_PLAN == 30

    def test_slot_count_five(self):
        assert BATTLE_PLAN_SLOT_COUNT == 5


class TestBattlePlanDataclass:
    """Verify BattlePlan dataclass fields."""

    def test_can_construct(self):
        bp = BattlePlan(slot_index=0, player_id=0, raw_body=b"\x01\x02")
        assert bp.slot_index == 0

    def test_raw_body_stored_correctly(self):
        body = b"\xAB\xCD\xEF"
        bp = BattlePlan(slot_index=1, player_id=2, raw_body=body)
        assert bp.raw_body == body

    def test_raw_body_is_bytes(self):
        bp = BattlePlan(slot_index=0, player_id=0, raw_body=bytes([1, 2, 3]))
        assert isinstance(bp.raw_body, bytes)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: slot_index and player_id extraction
# ─────────────────────────────────────────────────────────────────────────────


class TestSlotPlayerDecoding:
    """Verify d[0] = (slot << 4) | player encoding."""

    def test_slot0_player0(self):
        data = _make_plan(0, 0)
        bp = decode_battle_plan(data)
        assert bp.slot_index == 0
        assert bp.player_id == 0

    def test_slot1_player0(self):
        data = _make_plan(1, 0)
        bp = decode_battle_plan(data)
        assert bp.slot_index == 1
        assert bp.player_id == 0

    def test_slot4_player0(self):
        data = _make_plan(4, 0)
        bp = decode_battle_plan(data)
        assert bp.slot_index == 4
        assert bp.player_id == 0

    def test_slot0_player1(self):
        data = _make_plan(0, 1)
        bp = decode_battle_plan(data)
        assert bp.slot_index == 0
        assert bp.player_id == 1

    def test_slot3_player1(self):
        data = _make_plan(3, 1)
        bp = decode_battle_plan(data)
        assert bp.slot_index == 3
        assert bp.player_id == 1

    def test_slot0_player15(self):
        """Maximum player_id = 15 (16-player game)."""
        data = _make_plan(0, 15)
        bp = decode_battle_plan(data)
        assert bp.slot_index == 0
        assert bp.player_id == 15

    def test_slot4_player15(self):
        data = _make_plan(4, 15)
        bp = decode_battle_plan(data)
        assert bp.slot_index == 4
        assert bp.player_id == 15


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: raw_body extraction
# ─────────────────────────────────────────────────────────────────────────────


class TestBodyExtraction:
    """Verify body bytes are correctly separated from the header byte."""

    def test_body_after_header(self):
        body = bytes([10, 20, 30, 40])
        data = _make_plan(0, 0, body)
        bp = decode_battle_plan(data)
        assert bp.raw_body == body

    def test_body_empty_when_only_header(self):
        data = bytes([0x00])  # just the header byte
        bp = decode_battle_plan(data)
        assert bp.raw_body == b""

    def test_body_length_matches_input_minus_1(self):
        body = bytes(range(12))
        data = _make_plan(2, 0, body)
        bp = decode_battle_plan(data)
        assert len(bp.raw_body) == 12

    def test_body_unchanged(self):
        body = bytes([1, 2, 3, 4, 5, 6, 7, 8])
        data = _make_plan(3, 1, body)
        bp = decode_battle_plan(data)
        assert bp.raw_body == body

    def test_body_is_bytes_not_bytearray(self):
        data = bytearray([0x10, 1, 2, 3])  # input as bytearray
        bp = decode_battle_plan(data)
        assert isinstance(bp.raw_body, bytes)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Error handling
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Verify decode_battle_plan raises on invalid input."""

    def test_raises_on_empty_data(self):
        with pytest.raises(ValueError):
            decode_battle_plan(b"")

    def test_raises_on_empty_bytearray(self):
        with pytest.raises(ValueError):
            decode_battle_plan(bytearray())

    def test_accepts_single_byte(self):
        bp = decode_battle_plan(bytes([0x00]))
        assert bp.slot_index == 0
        assert bp.raw_body == b""

    def test_batch_raises_on_empty_block(self):
        with pytest.raises(ValueError):
            decode_battle_plans([b""])


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5: Real data validation (Game.m1 2-player game)
# ─────────────────────────────────────────────────────────────────────────────


class TestRealDataM1:
    """Validate against Game.m1 BattlePlan blocks."""

    def test_s0_slot_index(self):
        bp = decode_battle_plan(M1_PLAN_S0)
        assert bp.slot_index == 0

    def test_s0_player_id(self):
        bp = decode_battle_plan(M1_PLAN_S0)
        assert bp.player_id == 0

    def test_s0_body_length(self):
        bp = decode_battle_plan(M1_PLAN_S0)
        assert len(bp.raw_body) == 9

    def test_s1_slot_index(self):
        bp = decode_battle_plan(M1_PLAN_S1)
        assert bp.slot_index == 1

    def test_s1_body_length(self):
        bp = decode_battle_plan(M1_PLAN_S1)
        assert len(bp.raw_body) == 12

    def test_s2_slot_index(self):
        bp = decode_battle_plan(M1_PLAN_S2)
        assert bp.slot_index == 2

    def test_s3_slot_index(self):
        bp = decode_battle_plan(M1_PLAN_S3)
        assert bp.slot_index == 3

    def test_s3_body_length(self):
        bp = decode_battle_plan(M1_PLAN_S3)
        assert len(bp.raw_body) == 8

    def test_s4_slot_index(self):
        bp = decode_battle_plan(M1_PLAN_S4)
        assert bp.slot_index == 4

    def test_s4_player_id(self):
        bp = decode_battle_plan(M1_PLAN_S4)
        assert bp.player_id == 0

    def test_all_five_slots_present(self):
        plans = decode_battle_plans(ALL_M1_PLANS)
        slots = [bp.slot_index for bp in plans]
        assert sorted(slots) == [0, 1, 2, 3, 4]

    def test_all_plans_same_player(self):
        plans = decode_battle_plans(ALL_M1_PLANS)
        assert all(bp.player_id == 0 for bp in plans)


class TestRealDataM2:
    """Validate against Game.m2 BattlePlan blocks."""

    def test_m2_s0_player_id(self):
        bp = decode_battle_plan(M2_PLAN_S0)
        assert bp.player_id == 1

    def test_m2_s1_player_id(self):
        bp = decode_battle_plan(M2_PLAN_S1)
        assert bp.player_id == 1

    def test_m2_all_plans_player1(self):
        plans = decode_battle_plans(ALL_M2_PLANS)
        assert all(bp.player_id == 1 for bp in plans)

    def test_bodies_identical_between_m1_m2(self):
        """Plan bodies must be identical across player files for same slot."""
        for i, (p1, p2) in enumerate(zip(ALL_M1_PLANS, ALL_M2_PLANS)):
            bp1 = decode_battle_plan(p1)
            bp2 = decode_battle_plan(p2)
            assert bp1.raw_body == bp2.raw_body, f"Slot {i}: body mismatch between m1 and m2"

    def test_m2_slot_indices_same_as_m1(self):
        plans_m1 = decode_battle_plans(ALL_M1_PLANS)
        plans_m2 = decode_battle_plans(ALL_M2_PLANS)
        for bp1, bp2 in zip(plans_m1, plans_m2):
            assert bp1.slot_index == bp2.slot_index


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6: Batch decoder
# ─────────────────────────────────────────────────────────────────────────────


class TestBatchDecoder:
    """Validate decode_battle_plans() multi-block pipeline."""

    def test_empty_list_returns_empty(self):
        result = decode_battle_plans([])
        assert result == []

    def test_single_block(self):
        result = decode_battle_plans([M1_PLAN_S0])
        assert len(result) == 1

    def test_five_blocks_preserves_order(self):
        result = decode_battle_plans(ALL_M1_PLANS)
        assert len(result) == 5

    def test_m1_slot_sequence(self):
        result = decode_battle_plans(ALL_M1_PLANS)
        assert [bp.slot_index for bp in result] == [0, 1, 2, 3, 4]

    def test_all_are_battle_plan_instances(self):
        result = decode_battle_plans(ALL_M1_PLANS)
        assert all(isinstance(bp, BattlePlan) for bp in result)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7: Property-based invariants
# ─────────────────────────────────────────────────────────────────────────────


class TestPropertyBasedInvariants:
    """Hypothesis-based tests for broad input coverage."""

    @given(
        slot=st.integers(min_value=0, max_value=4),
        player=st.integers(min_value=0, max_value=15),
    )
    @settings(max_examples=80, deadline=None)
    def test_round_trip_slot_and_player(self, slot, player):
        data = _make_plan(slot, player)
        bp = decode_battle_plan(data)
        assert bp.slot_index == slot
        assert bp.player_id == player

    @given(body=st.binary(min_size=0, max_size=16))
    @settings(max_examples=80, deadline=None)
    def test_body_roundtrip(self, body):
        data = _make_plan(0, 0, body)
        bp = decode_battle_plan(data)
        assert bp.raw_body == body

    @given(data=st.binary(min_size=1, max_size=20))
    @settings(max_examples=100, deadline=None)
    def test_no_crash_on_arbitrary_bytes(self, data):
        """decode_battle_plan must never raise when data has at least 1 byte."""
        bp = decode_battle_plan(data)
        assert isinstance(bp.slot_index, int)
        assert isinstance(bp.player_id, int)
        assert isinstance(bp.raw_body, bytes)
