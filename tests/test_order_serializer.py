"""Tests for the .x1 order file serializer.

All unit tests are pure-Python, no Flask context needed.

For the byte-fixture tests the expected values were derived by hand
from the documented block layout in docs/x1-order-file-format.md and
verified by running the decode path over the encoded output.

⚠  No real Stars!-generated .x1 with actual order blocks was available
   for byte-for-byte external verification; see issue #45 notes.
"""

import os
import struct

import pytest

from stars_web.block_reader import read_blocks
from stars_web.order_serializer import (
    BLOCK_TYPE_PRODUCTION_QUEUE_CHANGE,
    BLOCK_TYPE_WAYPOINT_ADD,
    OBJ_TYPE_DEEP_SPACE,
    OBJ_TYPE_PLANET,
    QUEUE_ITEM_TYPE_STANDARD,
    ProductionItem,
    ProductionQueueOrder,
    WaypointOrder,
    build_order_file,
    encode_production_queue_change_block,
    encode_waypoint_add_block,
    wrap_block,
)

# ---------------------------------------------------------------------------
# Sample .x1 header extracted from starswine4/backup/Game.x1 (unencrypted)
# ---------------------------------------------------------------------------

_THIS_DIR = os.path.dirname(__file__)
_X1_PATH = os.path.join(
    _THIS_DIR,
    "..",
    "..",
    "starswine4",
    "backup",
    "Game.x1",
)


def _load_source_header() -> bytes | None:
    """Return the 16-byte FILE_HEADER block content from Game.x1, or None."""
    x1 = os.path.abspath(_X1_PATH)
    if not os.path.exists(x1):
        return None
    with open(x1, "rb") as f:
        raw = f.read()
    blocks = read_blocks(raw)
    if not blocks or blocks[0].file_header is None:
        return None
    return blocks[0].data  # 16 bytes of header content


# ---------------------------------------------------------------------------
# encode_waypoint_add_block
# ---------------------------------------------------------------------------


class TestEncodeWaypointAddBlock:
    """Unit tests for encode_waypoint_add_block()."""

    def _make(self, **kwargs) -> bytes:
        order = WaypointOrder(
            fleet_id=kwargs.get("fleet_id", 0),
            x=kwargs.get("x", 100),
            y=kwargs.get("y", 200),
            warp=kwargs.get("warp", 5),
            task=kwargs.get("task", 0),
            obj_id=kwargs.get("obj_id", 42),
            obj_type=kwargs.get("obj_type", OBJ_TYPE_PLANET),
            waypoint_index=kwargs.get("waypoint_index", 0xFF),
        )
        return encode_waypoint_add_block(order)

    def test_block_is_12_bytes(self):
        assert len(self._make()) == 12

    def test_fleet_id_at_bytes_0_1(self):
        data = self._make(fleet_id=3)
        assert struct.unpack_from("<H", data, 0)[0] == 3

    def test_waypoint_index_at_byte_2(self):
        data = self._make(waypoint_index=0)
        assert data[2] == 0

    def test_append_index_is_0xff(self):
        data = self._make(waypoint_index=0xFF)
        assert data[2] == 0xFF

    def test_padding_byte_3_is_zero(self):
        assert self._make()[3] == 0x00

    def test_x_at_bytes_4_5(self):
        data = self._make(x=1273)
        assert struct.unpack_from("<H", data, 4)[0] == 1273

    def test_y_at_bytes_6_7(self):
        data = self._make(y=1183)
        assert struct.unpack_from("<H", data, 6)[0] == 1183

    def test_obj_id_at_bytes_8_9(self):
        data = self._make(obj_id=20)
        assert struct.unpack_from("<H", data, 8)[0] == 20

    def test_warp_in_upper_nibble_of_byte_10(self):
        data = self._make(warp=6, task=0)
        assert (data[10] >> 4) == 6

    def test_task_in_lower_nibble_of_byte_10(self):
        data = self._make(warp=5, task=2)
        assert (data[10] & 0x0F) == 2

    def test_obj_type_at_byte_11(self):
        data = self._make(obj_type=OBJ_TYPE_DEEP_SPACE)
        assert data[11] == OBJ_TYPE_DEEP_SPACE

    def test_byte_fixture(self):
        """Exact byte-level regression test.

        Input: fleet_id=0, x=100, y=200, warp=5, task=0, obj_id=42,
               obj_type=17 (planet), waypoint_index=255 (append)

        Expected:
          00 00  fleet_id=0
          ff     waypoint_index=255
          00     padding
          64 00  x=100
          c8 00  y=200
          2a 00  obj_id=42
          50     (5<<4)|0
          11     obj_type=17
        """
        expected = bytes.fromhex("0000ff0064 00c8002a005011".replace(" ", ""))
        data = self._make(
            fleet_id=0,
            x=100,
            y=200,
            warp=5,
            task=0,
            obj_id=42,
            obj_type=17,
            waypoint_index=255,
        )
        assert data == expected


# ---------------------------------------------------------------------------
# encode_production_queue_change_block
# ---------------------------------------------------------------------------


class TestEncodeProductionQueueChangeBlock:
    """Unit tests for encode_production_queue_change_block()."""

    def test_empty_queue_is_2_bytes(self):
        order = ProductionQueueOrder(planet_id=1, items=[])
        data = encode_production_queue_change_block(order)
        assert len(data) == 2

    def test_planet_id_at_bytes_0_1(self):
        order = ProductionQueueOrder(planet_id=42, items=[])
        data = encode_production_queue_change_block(order)
        assert struct.unpack_from("<H", data, 0)[0] == 42

    def test_one_item_is_6_bytes(self):
        order = ProductionQueueOrder(
            planet_id=1,
            items=[ProductionItem(item_id=8, quantity=5)],
        )
        assert len(encode_production_queue_change_block(order)) == 6

    def test_two_items_is_10_bytes(self):
        order = ProductionQueueOrder(
            planet_id=1,
            items=[
                ProductionItem(item_id=8, quantity=5),
                ProductionItem(item_id=7, quantity=2),
            ],
        )
        assert len(encode_production_queue_change_block(order)) == 10

    def test_item_id_encoded_in_upper_6_bits_of_chunk1(self):
        order = ProductionQueueOrder(
            planet_id=0,
            items=[ProductionItem(item_id=8, quantity=1)],
        )
        data = encode_production_queue_change_block(order)
        chunk1 = struct.unpack_from("<H", data, 2)[0]
        assert chunk1 >> 10 == 8  # item_id = Mine

    def test_quantity_in_lower_10_bits_of_chunk1(self):
        order = ProductionQueueOrder(
            planet_id=0,
            items=[ProductionItem(item_id=8, quantity=99)],
        )
        data = encode_production_queue_change_block(order)
        chunk1 = struct.unpack_from("<H", data, 2)[0]
        assert (chunk1 & 0x3FF) == 99

    def test_item_type_in_lower_4_bits_of_chunk2(self):
        order = ProductionQueueOrder(
            planet_id=0,
            items=[ProductionItem(item_id=8, quantity=1, item_type=QUEUE_ITEM_TYPE_STANDARD)],
        )
        data = encode_production_queue_change_block(order)
        chunk2 = struct.unpack_from("<H", data, 4)[0]
        assert (chunk2 & 0xF) == QUEUE_ITEM_TYPE_STANDARD

    def test_byte_fixture_two_items(self):
        """Exact byte-level regression for Mine×5 + Factory×2 on planet 7.

        Mine ID=8   qty=5 → chunk1 = (8<<10)|5 = 0x2005 → 05 20; chunk2=0x0002 → 02 00
        Factory ID=7 qty=2 → chunk1 = (7<<10)|2 = 0x1C02 → 02 1c; chunk2=0x0002 → 02 00
        """
        expected = bytes.fromhex("0700" "0520" "0200" "021c" "0200")
        order = ProductionQueueOrder(
            planet_id=7,
            items=[
                ProductionItem(item_id=8, quantity=5),
                ProductionItem(item_id=7, quantity=2),
            ],
        )
        assert encode_production_queue_change_block(order) == expected


# ---------------------------------------------------------------------------
# ProductionItem.from_name
# ---------------------------------------------------------------------------


class TestProductionItemFromName:
    def test_mine_resolves(self):
        item = ProductionItem.from_name("Mine", 3)
        assert item.item_id == 8
        assert item.quantity == 3

    def test_factory_resolves(self):
        assert ProductionItem.from_name("Factory", 1).item_id == 7

    def test_defense_resolves(self):
        assert ProductionItem.from_name("Defense", 10).item_id == 9

    def test_unknown_name_raises(self):
        with pytest.raises(ValueError, match="Unknown queue item name"):
            ProductionItem.from_name("Spaceship Mk IV", 1)


# ---------------------------------------------------------------------------
# wrap_block
# ---------------------------------------------------------------------------


class TestWrapBlock:
    def test_prepends_two_byte_header(self):
        raw = b"\x01\x02\x03\x04"
        result = wrap_block(BLOCK_TYPE_WAYPOINT_ADD, raw)
        assert len(result) == 6  # 2 header + 4 data

    def test_header_encodes_type_and_size(self):
        raw = b"\x00" * 12
        result = wrap_block(BLOCK_TYPE_WAYPOINT_ADD, raw)
        hdr = struct.unpack_from("<H", result, 0)[0]
        assert (hdr >> 10) == BLOCK_TYPE_WAYPOINT_ADD
        assert (hdr & 0x3FF) == 12

    def test_data_unchanged(self):
        raw = b"\xDE\xAD\xBE\xEF"
        result = wrap_block(0, raw)
        assert result[2:] == raw


# ---------------------------------------------------------------------------
# build_order_file (integration round-trip)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.path.exists(os.path.abspath(_X1_PATH)),
    reason="Game.x1 not present in starswine4/backup/",
)
class TestBuildOrderFile:
    """Integration tests that require Game.x1 from starswine4/backup/."""

    def setup_method(self):
        self.header_bytes = _load_source_header()
        assert self.header_bytes is not None

    def test_output_starts_with_file_header_block(self):
        result = build_order_file(self.header_bytes)
        # Block header: type=8, size=16
        hdr = struct.unpack_from("<H", result, 0)[0]
        assert hdr >> 10 == 8
        assert hdr & 0x3FF == 16

    def test_output_ends_with_footer_block(self):
        result = build_order_file(self.header_bytes)
        # Last 2 bytes should be footer block header: type=0, size=0
        last = struct.unpack_from("<H", result, len(result) - 2)[0]
        assert last == 0  # (0 << 10) | 0

    def test_empty_orders_produces_minimal_file(self):
        # header (18 bytes) + footer (2 bytes) = 20 bytes
        result = build_order_file(self.header_bytes)
        assert len(result) == 20

    def test_waypoint_order_adds_block(self):
        order = WaypointOrder(fleet_id=0, x=100, y=200, warp=5)
        result = build_order_file(self.header_bytes, waypoint_orders=[order])
        # 18 (header) + 2+12 (wp block) + 2 (footer) = 34 bytes
        assert len(result) == 34

    def test_waypoint_round_trip(self):
        """Encrypt then decrypt must recover original payload."""
        order = WaypointOrder(fleet_id=2, x=500, y=300, warp=7, task=2, obj_id=15)
        result = build_order_file(self.header_bytes, waypoint_orders=[order])

        blocks = read_blocks(result)
        # blocks: file_header [0], waypoint_add [1], footer [2]
        assert len(blocks) == 3
        wp_block = blocks[1]
        assert wp_block.type_id == BLOCK_TYPE_WAYPOINT_ADD

        d = wp_block.data
        assert struct.unpack_from("<H", d, 0)[0] == 2  # fleet_id
        assert struct.unpack_from("<H", d, 4)[0] == 500  # x
        assert struct.unpack_from("<H", d, 6)[0] == 300  # y
        assert (d[10] >> 4) == 7  # warp
        assert (d[10] & 0xF) == 2  # task

    def test_production_order_round_trip(self):
        """Encrypt then decrypt must recover production queue payload."""
        items = [
            ProductionItem(item_id=8, quantity=5),  # Mine x5
            ProductionItem(item_id=7, quantity=2),  # Factory x2
        ]
        order = ProductionQueueOrder(planet_id=3, items=items)
        result = build_order_file(self.header_bytes, production_orders=[order])

        blocks = read_blocks(result)
        pq_block = blocks[1]
        assert pq_block.type_id == BLOCK_TYPE_PRODUCTION_QUEUE_CHANGE

        d = pq_block.data
        assert struct.unpack_from("<H", d, 0)[0] == 3  # planet_id
        # Mine: chunk1 >> 10 == 8, chunk1 & 0x3FF == 5
        c1 = struct.unpack_from("<H", d, 2)[0]
        assert c1 >> 10 == 8
        assert c1 & 0x3FF == 5
