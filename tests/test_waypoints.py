"""Tests for Stars! waypoint parsing (block type 20)."""

import struct
import pytest

from stars_web.game_state import (
    parse_waypoint_block,
    WAYPOINT_TASKS,
)
from stars_web.block_reader import Block


# ── Waypoint task names ─────────────────────────────────────────────


class TestWaypointTasks:
    """Waypoint task IDs should map to known names."""

    def test_none_is_0(self):
        assert WAYPOINT_TASKS[0] == "None"

    def test_transport_is_1(self):
        assert WAYPOINT_TASKS[1] == "Transport"

    def test_colonize_is_2(self):
        assert WAYPOINT_TASKS[2] == "Colonize"

    def test_route_is_8(self):
        assert WAYPOINT_TASKS[8] == "Route"


# ── Parse waypoint blocks ──────────────────────────────────────────


class TestParseWaypointBlock:
    """Parse waypoint blocks (type 20)."""

    def _make_waypoint_block(
        self,
        x=1000,
        y=1100,
        position_object=18,
        warp=5,
        task=0,
        position_object_type=17,
    ):
        """Build a synthetic waypoint block."""
        data = bytearray(8)
        struct.pack_into("<H", data, 0, x)
        struct.pack_into("<H", data, 2, y)
        struct.pack_into("<H", data, 4, position_object)
        data[6] = (warp << 4) | (task & 0x0F)
        data[7] = position_object_type
        return Block(type_id=20, size=len(data), data=bytes(data))

    def test_basic_waypoint(self):
        block = self._make_waypoint_block(x=1290, y=1164, warp=5, task=0)
        wp = parse_waypoint_block(block)
        assert wp.x == 1290
        assert wp.y == 1164
        assert wp.warp == 5
        assert wp.task == 0
        assert wp.task_name == "None"

    def test_position_object(self):
        block = self._make_waypoint_block(position_object=23)
        wp = parse_waypoint_block(block)
        assert wp.position_object == 23

    def test_position_object_type_planet(self):
        block = self._make_waypoint_block(position_object_type=17)
        wp = parse_waypoint_block(block)
        assert wp.position_object_type == 17

    def test_position_object_type_deep_space(self):
        block = self._make_waypoint_block(position_object=0, position_object_type=20)
        wp = parse_waypoint_block(block)
        assert wp.position_object_type == 20

    def test_transport_task(self):
        block = self._make_waypoint_block(task=1)
        wp = parse_waypoint_block(block)
        assert wp.task == 1
        assert wp.task_name == "Transport"

    def test_colonize_task(self):
        block = self._make_waypoint_block(task=2)
        wp = parse_waypoint_block(block)
        assert wp.task == 2
        assert wp.task_name == "Colonize"

    def test_warp_zero(self):
        block = self._make_waypoint_block(warp=0)
        wp = parse_waypoint_block(block)
        assert wp.warp == 0

    def test_wrong_block_type_returns_none(self):
        block = Block(type_id=13, size=8, data=b"\x00" * 8)
        assert parse_waypoint_block(block) is None


# ── Integration: parse waypoints from real game file ────────────────


class TestParseWaypointsFromFile:
    """Parse waypoint blocks from real Stars! game files."""

    @pytest.fixture
    def m1_data(self):
        import os
        from stars_web.block_reader import read_blocks

        path = os.path.join("docs", "images", "original_fat_client_screenshots", "Game.m1")
        if not os.path.exists(path):
            pytest.skip("Game.m1 not found")
        data = open(path, "rb").read()
        return read_blocks(data)

    def test_waypoint_blocks_exist(self, m1_data):
        wp_blocks = [b for b in m1_data if b.type_id == 20]
        assert len(wp_blocks) == 7

    def test_all_waypoints_parse(self, m1_data):
        wp_blocks = [b for b in m1_data if b.type_id == 20]
        waypoints = [parse_waypoint_block(b) for b in wp_blocks]
        assert all(wp is not None for wp in waypoints)
        assert all(wp.x > 0 and wp.y > 0 for wp in waypoints)

    def test_waypoint_warp_range(self, m1_data):
        wp_blocks = [b for b in m1_data if b.type_id == 20]
        waypoints = [parse_waypoint_block(b) for b in wp_blocks]
        for wp in waypoints:
            assert 0 <= wp.warp <= 10

    def test_all_waypoints_have_task_names(self, m1_data):
        wp_blocks = [b for b in m1_data if b.type_id == 20]
        waypoints = [parse_waypoint_block(b) for b in wp_blocks]
        for wp in waypoints:
            assert len(wp.task_name) > 0
