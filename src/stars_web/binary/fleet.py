"""Stars! fleet block binary parser.

Handles Type 16 (full fleet) and Type 17 (partial/enemy fleet) blocks from .m# files.

Type 16 (FleetBlock): Full fleet data for fleets owned by the player.
  Includes position, ship composition, orbit info, waypoint count.

Type 17 (PartialFleetBlock): Partial data for enemy fleets the player has observed.
  Only includes position, owner, and basic ship count.

Fixed header (14 bytes):
  byte 0:    fleet_number[7:0]
  byte 1:    fleet_number[8] (bit 0) | owner[6:0] (bits 1-7)
  bytes 2-3: unknown
  byte 4:    kind (0=write-only, 4=has-cargo, 7=full-data)
  byte 5:    flags
               bit 3: if CLEAR → ship counts are 2 bytes each;
                       if SET  → ship counts are 1 byte each
  bytes 6-7: orbit_planet_id (uint16 LE) — planet this fleet is orbiting/targeting
  bytes 8-9:  x position (uint16 LE)
  bytes 10-11: y position (uint16 LE)
  bytes 12-13: ship_designs_mask (uint16 LE — one bit per design slot 0-15)

Variable ship counts (after header):
  For each bit i set in ship_designs_mask (bit 0 = lowest), read the ship count
  for design slot i using either 1 or 2 bytes depending on flags bit 3.

Remaining data:
  After ship counts, remaining bytes before the last byte (when kind == 7)
  include unknown fields (fuel, cargo, etc. — not fully decoded).

  Last byte (when kind == 7): waypoint_count — number of subsequent
  WaypointBlock (Type 20) entries that belong to this fleet.

References:
  - docs/file-format-discovery.md (section 10)
  - blocks/__init__.py from stars-4x/starsapi-python: type 16 = "FleetBlock"
  - stars-4x/starsapi-python: type 17 = "PartialFleetBlock"
  - game_state.py _parse_fleet_block() (existing inline implementation)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

# Block type IDs
BLOCK_TYPE_FLEET_FULL = 16
BLOCK_TYPE_FLEET_PARTIAL = 17

# Fleet block 'kind' values
FLEET_KIND_WRITE = 0  # write-only legacy flag
FLEET_KIND_CARGO = 4  # has cargo section
FLEET_KIND_FULL = 7  # full data including waypoint count at end

# Flag masks
_FLAG_SHIP_COUNT_2_BYTES = 0x08  # if CLEAR → 2-byte ship counts; SET → 1-byte


@dataclass
class FleetDetail:
    """Parsed fleet data from a Type 16 or Type 17 block.

    Attributes:
        fleet_id:       Fleet serial number (0-based).
        owner:          Player index (0-based).
        kind:           Fleet block kind byte (0/4/7).
        flags:          Raw flags byte.
        orbit_planet_id: ID of planet this fleet is at (from bytes 6-7).
                         May be 0 for deep-space fleets.
        x:              X position on the star map (uint16).
        y:              Y position on the star map (uint16).
        ship_designs_mask: Bitmask of which design slots have ships (uint16).
        ship_counts:    Mapping from design slot index (0-15) to ship count.
        total_ship_count: Sum of all ship counts.
        wp_count:       Number of waypoints (last byte when kind == 7).
        is_full:        True for Type 16 (own fleet), False for Type 17 (enemy).
        extra_bytes:    Unparsed bytes between ship counts and wp_count.
                        Includes fuel, cargo, and other undecoded fields.
    """

    fleet_id: int
    owner: int
    kind: int
    flags: int
    orbit_planet_id: int
    x: int
    y: int
    ship_designs_mask: int
    ship_counts: dict[int, int] = field(default_factory=dict)
    total_ship_count: int = 0
    wp_count: int = 0
    is_full: bool = True
    extra_bytes: bytes = b""


def decode_fleet(data: bytes, block_type: int = BLOCK_TYPE_FLEET_FULL) -> FleetDetail:
    """Parse a single fleet block (Type 16 or 17) into a FleetDetail.

    Args:
        data:       Raw block payload bytes (excluding the 2-byte block header).
        block_type: BLOCK_TYPE_FLEET_FULL (16) or BLOCK_TYPE_FLEET_PARTIAL (17).

    Returns:
        FleetDetail with all parseable fields populated.

    Raises:
        ValueError: If data is too short for the 14-byte fixed header.
        ValueError: If block_type is not 16 or 17.
    """
    if block_type not in (BLOCK_TYPE_FLEET_FULL, BLOCK_TYPE_FLEET_PARTIAL):
        raise ValueError(f"Expected fleet block type 16 or 17, got {block_type}")

    if len(data) < 14:
        raise ValueError(f"Fleet block too short: {len(data)} bytes (need ≥14)")

    # ── Fixed header ──────────────────────────────────────────────────────────
    fleet_id = data[0] | ((data[1] & 0x01) << 8)
    owner = (data[1] >> 1) & 0x7F
    kind = data[4]
    flags = data[5]
    orbit_planet_id = struct.unpack_from("<H", data, 6)[0]
    x = struct.unpack_from("<H", data, 8)[0]
    y = struct.unpack_from("<H", data, 10)[0]
    ship_designs_mask = struct.unpack_from("<H", data, 12)[0]

    is_full = block_type == BLOCK_TYPE_FLEET_FULL

    detail = FleetDetail(
        fleet_id=fleet_id,
        owner=owner,
        kind=kind,
        flags=flags,
        orbit_planet_id=orbit_planet_id,
        x=x,
        y=y,
        ship_designs_mask=ship_designs_mask,
        is_full=is_full,
    )

    # ── Variable ship counts ──────────────────────────────────────────────────
    # Flags bit 3: if CLEAR, each ship count is 2 bytes; if SET, 1 byte.
    two_byte_counts = (flags & _FLAG_SHIP_COUNT_2_BYTES) == 0
    offset = 14
    total_ships = 0

    for bit in range(16):
        if ship_designs_mask & (1 << bit):
            if two_byte_counts and offset + 2 <= len(data):
                count = struct.unpack_from("<H", data, offset)[0]
                offset += 2
            elif not two_byte_counts and offset < len(data):
                count = data[offset]
                offset += 1
            else:
                count = 0
            detail.ship_counts[bit] = count
            total_ships += count

    detail.total_ship_count = total_ships

    # ── Waypoint count + extra bytes ──────────────────────────────────────────
    # When kind == 7, the last byte is the waypoint count.
    # Bytes between offset and the end (exclusive of last byte) are unparsed.
    if kind == FLEET_KIND_FULL and len(data) > offset:
        detail.wp_count = data[-1]
        detail.extra_bytes = bytes(data[offset : len(data) - 1])
    elif len(data) > offset:
        detail.extra_bytes = bytes(data[offset:])

    return detail


def decode_fleets(blocks: list[tuple[int, bytes]]) -> list[FleetDetail]:
    """Decode a list of raw fleet block payloads.

    Args:
        blocks: List of (block_type, data) pairs. block_type must be 16 or 17.

    Returns:
        List of FleetDetail objects (one per block).

    Raises:
        ValueError: If any block_type is not 16 or 17.
    """
    return [decode_fleet(data, bt) for bt, data in blocks]
