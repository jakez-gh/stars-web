"""Test Suite for WaypointTask Block Parsing (Tier-1 Binary Parsing)

Block Type: 19 (WaypointTaskBlock)
Purpose: Parse waypoint task details from .m# game state files.
Format: Fixed 18-byte block with destination coordinates, target ID,
        task configuration byte, and 10 bytes of task parameters.

References:
  - starswine4/Game.m1, Game-big.m1 (real test data)
  - stars-4x/starsapi-python BLOCKS dict: type 19 = "WaypointTaskBlock"
"""

import struct

import pytest
from hypothesis import given, settings, strategies as st

from stars_web.binary.waypoint_task import (
    WaypointTask,
    BLOCK_TYPE_WAYPOINT_TASK,
    WAYPOINT_TASK_SIZE,
    decode_waypoint_task,
    decode_waypoint_tasks,
)


# ─────────────────────────────────────────────────────────────────────────────
# Real binary fixtures (decrypted, from starswine4/ game files)
# ─────────────────────────────────────────────────────────────────────────────

# Game.m1 block 0: dest=(1254, 1200), target=18, task_byte=0x51, unknown_7=17
M1_TASK_0 = bytes(
    [
        230,
        4,  # dest_x = 1254
        176,
        4,  # dest_y = 1200
        18,
        0,  # target_id = 18
        81,  # task_byte = 0x51
        17,  # unknown_7 = 17
        0,
        16,
        0,
        16,
        0,
        16,
        0,
        0,
        0,
        112,  # task_body (10 bytes)
    ]
)

# Game.m1 block 1: dest=(1273, 1183), target=20, task_byte=0x51, unknown_7=17
M1_TASK_1 = bytes(
    [
        249,
        4,  # dest_x = 1273
        159,
        4,  # dest_y = 1183
        20,
        0,  # target_id = 20
        81,  # task_byte = 0x51
        17,  # unknown_7 = 17
        0,
        32,
        0,
        32,
        0,
        32,
        0,
        32,
        0,
        112,  # task_body (10 bytes)
    ]
)

# Game-big.m1 block 0: dest=(1644, 2877), target=307, task_byte=0x65, unknown_7=17
BIG_TASK_0 = bytes(
    [
        108,
        6,  # dest_x = 1644
        61,
        11,  # dest_y = 2877
        51,
        1,  # target_id = 307
        101,  # task_byte = 0x65
        17,  # unknown_7 = 17
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,  # task_body (10 zeros)
    ]
)


def _make_task(
    dest_x: int = 0,
    dest_y: int = 0,
    target_id: int = 0,
    task_byte: int = 0,
    unknown_7: int = 0,
    task_body: bytes = bytes(10),
) -> bytes:
    """Build a synthetic 18-byte WaypointTask block payload."""
    header = struct.pack("<HHH", dest_x, dest_y, target_id)
    return header + bytes([task_byte, unknown_7]) + task_body


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Constants and dataclass
# ─────────────────────────────────────────────────────────────────────────────


class TestConstants:
    def test_block_type_value(self):
        assert BLOCK_TYPE_WAYPOINT_TASK == 19

    def test_block_size_18(self):
        assert WAYPOINT_TASK_SIZE == 18

    def test_struct_size_check(self):
        """Header fields alone (HHH = 6 bytes) + 1+1+10 = 18."""
        assert struct.calcsize("<HHH") + 1 + 1 + 10 == WAYPOINT_TASK_SIZE


class TestWaypointTaskDataclass:
    def test_can_construct(self):
        wt = WaypointTask(
            dest_x=0,
            dest_y=0,
            target_id=0,
            task_byte=0,
            unknown_7=0,
            task_body=bytes(10),
            raw=bytes(18),
        )
        assert wt.dest_x == 0

    def test_task_body_is_bytes(self):
        wt = WaypointTask(
            dest_x=1,
            dest_y=2,
            target_id=3,
            task_byte=4,
            unknown_7=5,
            task_body=bytes(10),
            raw=bytes(18),
        )
        assert isinstance(wt.task_body, bytes)

    def test_task_body_length_ten(self):
        wt = WaypointTask(
            dest_x=0,
            dest_y=0,
            target_id=0,
            task_byte=0,
            unknown_7=0,
            task_body=bytes(10),
            raw=bytes(18),
        )
        assert len(wt.task_body) == 10


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Coordinate and target_id decoding
# ─────────────────────────────────────────────────────────────────────────────


class TestCoordinateDecoding:
    def test_dest_x(self):
        wt = decode_waypoint_task(_make_task(dest_x=1273))
        assert wt.dest_x == 1273

    def test_dest_y(self):
        wt = decode_waypoint_task(_make_task(dest_y=1183))
        assert wt.dest_y == 1183

    def test_target_id(self):
        wt = decode_waypoint_task(_make_task(target_id=20))
        assert wt.target_id == 20

    def test_target_id_large(self):
        wt = decode_waypoint_task(_make_task(target_id=307))
        assert wt.target_id == 307

    def test_dest_x_zero(self):
        wt = decode_waypoint_task(_make_task(dest_x=0))
        assert wt.dest_x == 0

    def test_max_coordinate(self):
        wt = decode_waypoint_task(_make_task(dest_x=32767, dest_y=32767))
        assert wt.dest_x == 32767
        assert wt.dest_y == 32767


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: task_byte, unknown_7, task_body
# ─────────────────────────────────────────────────────────────────────────────


class TestTaskFields:
    def test_task_byte(self):
        wt = decode_waypoint_task(_make_task(task_byte=0x51))
        assert wt.task_byte == 0x51

    def test_unknown_7(self):
        wt = decode_waypoint_task(_make_task(unknown_7=17))
        assert wt.unknown_7 == 17

    def test_task_body_length(self):
        wt = decode_waypoint_task(_make_task())
        assert len(wt.task_body) == 10

    def test_task_body_content(self):
        body = bytes(range(10))
        wt = decode_waypoint_task(_make_task(task_body=body))
        assert wt.task_body == body

    def test_task_body_is_bytes(self):
        wt = decode_waypoint_task(_make_task())
        assert isinstance(wt.task_body, bytes)

    def test_raw_is_full_18_bytes(self):
        data = _make_task(dest_x=100, dest_y=200)
        wt = decode_waypoint_task(data)
        assert wt.raw == data
        assert len(wt.raw) == 18

    def test_raw_is_bytes_type(self):
        data = _make_task()
        wt = decode_waypoint_task(data)
        assert isinstance(wt.raw, bytes)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Error handling
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    def test_raises_on_empty(self):
        with pytest.raises(ValueError, match="18 bytes"):
            decode_waypoint_task(b"")

    def test_raises_on_too_short(self):
        with pytest.raises(ValueError, match="18 bytes"):
            decode_waypoint_task(bytes(10))

    def test_raises_on_too_long(self):
        with pytest.raises(ValueError, match="18 bytes"):
            decode_waypoint_task(bytes(20))

    def test_accepts_exactly_18_bytes(self):
        wt = decode_waypoint_task(bytes(18))
        assert wt is not None

    def test_batch_raises_on_bad_size(self):
        with pytest.raises(ValueError):
            decode_waypoint_tasks([bytes(10)])


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5: Real data validation
# ─────────────────────────────────────────────────────────────────────────────


class TestRealDataM1:
    def test_m1_task0_dest_x(self):
        wt = decode_waypoint_task(M1_TASK_0)
        assert wt.dest_x == 1254

    def test_m1_task0_dest_y(self):
        wt = decode_waypoint_task(M1_TASK_0)
        assert wt.dest_y == 1200

    def test_m1_task0_target_id(self):
        wt = decode_waypoint_task(M1_TASK_0)
        assert wt.target_id == 18

    def test_m1_task0_task_byte(self):
        wt = decode_waypoint_task(M1_TASK_0)
        assert wt.task_byte == 0x51

    def test_m1_task0_unknown_7_is_17(self):
        wt = decode_waypoint_task(M1_TASK_0)
        assert wt.unknown_7 == 17

    def test_m1_task0_task_body_length(self):
        wt = decode_waypoint_task(M1_TASK_0)
        assert len(wt.task_body) == 10

    def test_m1_task1_dest(self):
        wt = decode_waypoint_task(M1_TASK_1)
        assert wt.dest_x == 1273
        assert wt.dest_y == 1183

    def test_m1_task1_target_id(self):
        wt = decode_waypoint_task(M1_TASK_1)
        assert wt.target_id == 20

    def test_m1_task1_unknown_7_is_17(self):
        wt = decode_waypoint_task(M1_TASK_1)
        assert wt.unknown_7 == 17

    def test_m1_raw_matches_input_task0(self):
        wt = decode_waypoint_task(M1_TASK_0)
        assert wt.raw == M1_TASK_0

    def test_m1_raw_matches_input_task1(self):
        wt = decode_waypoint_task(M1_TASK_1)
        assert wt.raw == M1_TASK_1


class TestRealDataBig:
    def test_big_task0_dest_x(self):
        wt = decode_waypoint_task(BIG_TASK_0)
        assert wt.dest_x == 1644

    def test_big_task0_dest_y(self):
        wt = decode_waypoint_task(BIG_TASK_0)
        assert wt.dest_y == 2877

    def test_big_task0_target_id(self):
        wt = decode_waypoint_task(BIG_TASK_0)
        assert wt.target_id == 307

    def test_big_task0_task_byte(self):
        wt = decode_waypoint_task(BIG_TASK_0)
        assert wt.task_byte == 0x65

    def test_big_task0_unknown_7_is_17(self):
        wt = decode_waypoint_task(BIG_TASK_0)
        assert wt.unknown_7 == 17


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6: Batch decoder
# ─────────────────────────────────────────────────────────────────────────────


class TestBatchDecoder:
    def test_empty_list(self):
        result = decode_waypoint_tasks([])
        assert result == []

    def test_single_block(self):
        result = decode_waypoint_tasks([M1_TASK_0])
        assert len(result) == 1

    def test_multiple_blocks_order(self):
        result = decode_waypoint_tasks([M1_TASK_0, M1_TASK_1, BIG_TASK_0])
        assert result[0].target_id == 18
        assert result[1].target_id == 20
        assert result[2].target_id == 307

    def test_all_are_waypoint_task_instances(self):
        result = decode_waypoint_tasks([M1_TASK_0, M1_TASK_1])
        assert all(isinstance(wt, WaypointTask) for wt in result)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7: Property-based invariants
# ─────────────────────────────────────────────────────────────────────────────


class TestPropertyBased:
    @given(
        dest_x=st.integers(min_value=0, max_value=32767),
        dest_y=st.integers(min_value=0, max_value=32767),
        target_id=st.integers(min_value=0, max_value=65535),
    )
    @settings(max_examples=80, deadline=None)
    def test_coordinate_roundtrip(self, dest_x, dest_y, target_id):
        data = _make_task(dest_x=dest_x, dest_y=dest_y, target_id=target_id)
        wt = decode_waypoint_task(data)
        assert wt.dest_x == dest_x
        assert wt.dest_y == dest_y
        assert wt.target_id == target_id

    @given(task_body=st.binary(min_size=10, max_size=10))
    @settings(max_examples=80, deadline=None)
    def test_task_body_roundtrip(self, task_body):
        data = _make_task(task_body=task_body)
        wt = decode_waypoint_task(data)
        assert wt.task_body == task_body

    @given(data=st.binary(min_size=18, max_size=18))
    @settings(max_examples=80, deadline=None)
    def test_no_crash_on_arbitrary_bytes(self, data):
        wt = decode_waypoint_task(data)
        assert isinstance(wt.dest_x, int)
        assert isinstance(wt.task_body, bytes)
