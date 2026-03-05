"""Stars! waypoint task block binary parser.

Handles Type 19 (WaypointTaskBlock) from .m# game state files.

Each WaypointTask block describes a specific task assigned to a waypoint:
the destination coordinates, the target planet/object, task configuration,
and cargo quantities involved.

All observed blocks are exactly 18 bytes.

Structure (18 bytes):
  bytes 0-1:  dest_x (uint16 LE) — destination X coordinate
  bytes 2-3:  dest_y (uint16 LE) — destination Y coordinate
  bytes 4-5:  target_id (uint16 LE) — planet or object ID at destination
  byte  6:    task_byte — packed task type / fleet flags (not fully decoded)
  byte  7:    unknown_7 — observed value 17 (0x11) in all blocks
  bytes 8-17: task_body (10 bytes) — task parameters (cargo amounts, etc.;
              semantics not fully known)

Notes:
  - WaypointTask (Type 19) supplements WaypointBlock (Type 20), which sets
    the warp speed, destination, and basic task type.
  - The task_body bytes appear to encode cargo quantities in some format;
    exact encoding is uncertain.
  - Only the top-level coordinates (dest_x, dest_y, target_id) are reliably
    decoded.  All other bytes are preserved as raw data.

References:
  - starswine4/Game.m1, Game-big.m1 (real test data)
  - stars-4x/starsapi-python BLOCKS dict: type 19 = "WaypointTaskBlock"
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

# Block type ID
BLOCK_TYPE_WAYPOINT_TASK = 19

# Block size (fixed — all observed blocks are 18 bytes)
WAYPOINT_TASK_SIZE = 18


@dataclass
class WaypointTask:
    """Parsed waypoint task from a Type 19 block.

    Attributes:
        dest_x:     Destination X coordinate (uint16, bytes 0-1).
        dest_y:     Destination Y coordinate (uint16, bytes 2-3).
        target_id:  Planet or object ID at the destination (uint16, bytes 4-5).
        task_byte:  Packed task type flags — semantics uncertain (byte 6).
        unknown_7:  Byte 7 — observed value 0x11 in all known blocks.
        task_body:  Remaining 10 bytes (bytes 8-17) — task parameters;
                    may encode cargo amounts, load/unload flags, etc.
        raw:        Complete 18-byte payload for forward-compatible access.
    """

    dest_x: int
    dest_y: int
    target_id: int
    task_byte: int
    unknown_7: int
    task_body: bytes
    raw: bytes


def decode_waypoint_task(data: bytes) -> WaypointTask:
    """Parse a single Type 19 WaypointTask block.

    Args:
        data: Raw block payload (must be exactly 18 bytes).

    Returns:
        WaypointTask with all fields populated.

    Raises:
        ValueError: If data is not exactly 18 bytes.
    """
    if len(data) != WAYPOINT_TASK_SIZE:
        raise ValueError(
            f"WaypointTask block must be exactly {WAYPOINT_TASK_SIZE} bytes, " f"got {len(data)}"
        )

    dest_x, dest_y, target_id = struct.unpack_from("<HHH", data)
    task_byte = data[6]
    unknown_7 = data[7]
    task_body = bytes(data[8:18])

    return WaypointTask(
        dest_x=dest_x,
        dest_y=dest_y,
        target_id=target_id,
        task_byte=task_byte,
        unknown_7=unknown_7,
        task_body=task_body,
        raw=bytes(data),
    )


def decode_waypoint_tasks(blocks: list[bytes]) -> list[WaypointTask]:
    """Decode a list of Type 19 block payloads.

    Args:
        blocks: List of raw 18-byte payloads.

    Returns:
        List of WaypointTask objects in input order.

    Raises:
        ValueError: If any block is not exactly 18 bytes.
    """
    return [decode_waypoint_task(b) for b in blocks]
