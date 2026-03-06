"""Stars! fleet order block binary parser.

Handles Type 20 (FleetOrderBlock) from .m# game state files.

Each FleetOrder block describes the current movement order for a fleet:
the destination coordinates, the target object (if any), movement flags,
and whether the fleet is heading to a planet/object or open space.

All blocks are exactly 8 bytes.

Structure (8 bytes):
  bytes 0-1:  dest_x (uint16 LE) — destination X coordinate
  bytes 2-3:  dest_y (uint16 LE) — destination Y coordinate
  bytes 4-5:  target_id (uint16 LE) — planet/object ID at destination
              (0 when heading to open space)
  byte  6:    flags (uint8) — movement flags
              Observed values: 0x00, 0x40, 0x50, 0x60, 0x70, 0x80, 0x90
  byte  7:    order_type (uint8)
              0x11 (17) = TARGETED — fleet has a named target object
              0x14 (20) = OPEN_SPACE — fleet heading to coordinate only

Observations:
  - When order_type == ORDER_TYPE_TARGETED, target_id is non-zero (planet
    or fleet ID).
  - When order_type == ORDER_TYPE_OPEN_SPACE, target_id is zero.
  - One Type 20 block appears per fleet per player file.
  - Flags bits are not fully decoded; they likely encode warp speed and
    cargo-priority hints.

References:
  - starswine4/Game.m1, Game-big.m1 (real test data)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

# Block type ID
BLOCK_TYPE_FLEET_ORDER = 20

# Fixed size of every FleetOrder block
FLEET_ORDER_SIZE = 8

# Struct format: dest_x, dest_y, target_id (all uint16 LE) + flags, order_type (uint8)
_FLEET_ORDER_STRUCT = struct.Struct("<HHHBB")

# order_type byte values
ORDER_TYPE_TARGETED = 0x11  # fleet heading to a specific named object
ORDER_TYPE_OPEN_SPACE = 0x14  # fleet heading to open-space coordinates


@dataclass
class FleetOrder:
    """Parsed fleet order from a Type 20 block.

    Attributes:
        dest_x:     Destination X coordinate (uint16, bytes 0-1).
        dest_y:     Destination Y coordinate (uint16, bytes 2-3).
        target_id:  Target planet/object ID (uint16, bytes 4-5).
                    Zero when order_type is ORDER_TYPE_OPEN_SPACE.
        flags:      Movement flags byte (byte 6); warp speed and hints.
        order_type: 0x11 = targeted object, 0x14 = open-space coordinate.
        raw:        Full 8-byte payload for forward-compatible access.
    """

    dest_x: int
    dest_y: int
    target_id: int
    flags: int
    order_type: int
    raw: bytes = field(repr=False)

    @property
    def is_targeted(self) -> bool:
        """True when the fleet is heading to a specific named object."""
        return self.order_type == ORDER_TYPE_TARGETED

    @property
    def is_open_space(self) -> bool:
        """True when the fleet is heading to open-space coordinates."""
        return self.order_type == ORDER_TYPE_OPEN_SPACE


def decode_fleet_order(data: bytes) -> FleetOrder:
    """Parse a single FleetOrder (Type 20) block payload.

    Args:
        data: Exactly 8 bytes of block payload (without the block header).

    Returns:
        A FleetOrder with all fields populated.

    Raises:
        ValueError: If data is not exactly FLEET_ORDER_SIZE bytes.
        struct.error: If data cannot be unpacked.
    """
    if len(data) != FLEET_ORDER_SIZE:
        raise ValueError(f"FleetOrder requires exactly {FLEET_ORDER_SIZE} bytes, got {len(data)}")
    dest_x, dest_y, target_id, flags, order_type = _FLEET_ORDER_STRUCT.unpack(data)
    return FleetOrder(
        dest_x=dest_x,
        dest_y=dest_y,
        target_id=target_id,
        flags=flags,
        order_type=order_type,
        raw=bytes(data),
    )


def decode_fleet_orders(file_data: bytes) -> list[FleetOrder]:
    """Decode all FleetOrder blocks from a complete .m# file.

    Reads the file using :func:`~stars_web.block_reader.read_blocks` and
    returns one :class:`FleetOrder` per Type 20 block found.

    Args:
        file_data: Raw bytes of a full .m# player file.

    Returns:
        List of FleetOrder objects in file order.
    """
    from stars_web.block_reader import read_blocks

    orders: list[FleetOrder] = []
    for block in read_blocks(file_data):
        if block.type_id == BLOCK_TYPE_FLEET_ORDER:
            orders.append(decode_fleet_order(block.data))
    return orders
