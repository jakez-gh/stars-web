"""Stars! order file serializer.

Provides functions to encode fleet waypoint orders and planet production
queue orders as binary blocks suitable for inclusion in a .x1 order file.

Block type IDs for order (.x#) files:
  3  = WAYPOINT_DELETE
  4  = WAYPOINT_ADD
  5  = WAYPOINT_CHANGE_TASK
 22  = PRODUCTION_QUEUE_CHANGE
 29  = CHANGE_RESEARCH

Reference for binary layout: docs/x1-order-file-format.md
"""

import struct
from dataclasses import dataclass, field

# ── Block type constants ───────────────────────────────────────────────────────

BLOCK_TYPE_FILE_FOOTER = 0
BLOCK_TYPE_WAYPOINT_DELETE = 3
BLOCK_TYPE_WAYPOINT_ADD = 4
BLOCK_TYPE_WAYPOINT_CHANGE_TASK = 5
BLOCK_TYPE_FILE_HEADER = 8
BLOCK_TYPE_PRODUCTION_QUEUE_CHANGE = 22

# Waypoint position-object type codes
OBJ_TYPE_PLANET = 17  # 0x11 — waypoint is orbiting a planet
OBJ_TYPE_DEEP_SPACE = 20  # 0x14 — waypoint is in deep space

# Standard production queue item IDs (item_type = QUEUE_ITEM_TYPE_STANDARD)
QUEUE_ITEM_IDS: dict[str, int] = {
    "Auto Mines": 0,
    "Auto Factories": 1,
    "Auto Defenses": 2,
    "Auto Alchemy": 3,
    "Auto Min Terraform": 4,
    "Auto Max Terraform": 5,
    "Auto Mineral Packets": 6,
    "Factory": 7,
    "Mine": 8,
    "Defense": 9,
    "Mineral Alchemy": 11,
    "Planetary Scanner": 27,
}

QUEUE_ITEM_TYPE_STANDARD = 2  # factory/mine/defense/etc.
QUEUE_ITEM_TYPE_DESIGN = 4  # ship or starbase design


# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass
class WaypointOrder:
    """A single waypoint to add to a fleet's route."""

    fleet_id: int
    x: int
    y: int
    warp: int = 5
    task: int = 0  # 0=None, 1=Transport, 2=Colonize, …
    obj_id: int = 0  # Target planet/fleet ID (0 = deep space)
    obj_type: int = OBJ_TYPE_PLANET
    waypoint_index: int = 0xFF  # 0xFF = append; 0–N = insert before index N


@dataclass
class ProductionItem:
    """A single item in a planet's production queue."""

    item_id: int  # Standard item ID (7=Factory, 8=Mine, …) or design slot index
    quantity: int
    item_type: int = QUEUE_ITEM_TYPE_STANDARD
    complete_percent: int = 0  # 0 for newly-added items

    @classmethod
    def from_name(cls, name: str, quantity: int) -> "ProductionItem":
        """Construct from a display name (standard items only).

        Args:
            name:     Item name, e.g. "Mine" or "Factory".
            quantity: How many to build.

        Raises:
            ValueError: If *name* is not a recognised standard item name.
        """
        item_id = QUEUE_ITEM_IDS.get(name)
        if item_id is None:
            raise ValueError(f"Unknown queue item name: {name!r}")
        return cls(item_id=item_id, quantity=quantity)


@dataclass
class ProductionQueueOrder:
    """Replacement production queue for one planet."""

    planet_id: int
    items: list[ProductionItem] = field(default_factory=list)


# ── Low-level encoding ─────────────────────────────────────────────────────────


def _block_header_bytes(type_id: int, size: int) -> bytes:
    """Encode a 2-byte block header (type_id × 10 | size)."""
    return struct.pack("<H", (type_id << 10) | (size & 0x3FF))


def encode_waypoint_add_block(order: WaypointOrder) -> bytes:
    """Encode raw (unencrypted) bytes for a WAYPOINT_ADD block (type 4).

    Layout — 12 bytes:

    .. code-block:: text

        Offset  Size  Field
        ------  ----  -----
          0      2    fleet_id          uint16 LE
          2      1    waypoint_index    uint8; 0xFF = append
          3      1    padding           0x00
          4      2    x                 uint16 LE
          6      2    y                 uint16 LE
          8      2    obj_id            uint16 LE
         10      1    (warp<<4)|task    uint8
         11      1    obj_type          uint8; 17=planet, 20=deep space

    Args:
        order: Waypoint order to encode.

    Returns:
        12 raw (unencrypted) bytes.
    """
    data = bytearray(12)
    struct.pack_into("<H", data, 0, order.fleet_id)
    data[2] = order.waypoint_index & 0xFF
    data[3] = 0x00
    struct.pack_into("<H", data, 4, order.x)
    struct.pack_into("<H", data, 6, order.y)
    struct.pack_into("<H", data, 8, order.obj_id)
    data[10] = ((order.warp & 0xF) << 4) | (order.task & 0xF)
    data[11] = order.obj_type & 0xFF
    return bytes(data)


def encode_production_queue_change_block(order: ProductionQueueOrder) -> bytes:
    """Encode raw (unencrypted) bytes for a PRODUCTION_QUEUE_CHANGE block (type 22).

    Layout:

    .. code-block:: text

        Offset  Size  Field
        ------  ----  -----
          0      2    planet_id         uint16 LE
          2+     4×n  items

        Each item (4 bytes):
          chunk1 (uint16 LE): (item_id << 10) | (quantity & 0x3FF)
          chunk2 (uint16 LE): (complete_percent << 4) | item_type

    Args:
        order: Production queue replacement order.

    Returns:
        Raw (unencrypted) bytes; length = 2 + 4 × len(order.items).
    """
    data = bytearray(2 + len(order.items) * 4)
    struct.pack_into("<H", data, 0, order.planet_id)
    for i, item in enumerate(order.items):
        offset = 2 + i * 4
        chunk1 = (item.item_id << 10) | (item.quantity & 0x3FF)
        chunk2 = ((item.complete_percent & 0xFFF) << 4) | (item.item_type & 0xF)
        struct.pack_into("<H", data, offset, chunk1)
        struct.pack_into("<H", data, offset + 2, chunk2)
    return bytes(data)


def wrap_block(type_id: int, raw_data: bytes) -> bytes:
    """Prefix *raw_data* with a 2-byte block header.

    The returned bytes are *unencrypted*.  Pass them through
    ``Decryptor.decrypt_bytes()`` (XOR-symmetric, so it also encrypts)
    before writing to a .x# file.

    Args:
        type_id:  Block type ID (0–63).
        raw_data: Unencrypted block payload.

    Returns:
        2-byte header + *raw_data*.
    """
    return _block_header_bytes(type_id, len(raw_data)) + raw_data


# ── High-level file builder ────────────────────────────────────────────────────


def build_order_file(
    source_header_bytes: bytes,
    waypoint_orders: list[WaypointOrder] | None = None,
    production_orders: list[ProductionQueueOrder] | None = None,
) -> bytes:
    """Build a complete, encrypted .x1 order file.

    The original host-generated .x1 file (which the Stars! host writes for the
    player to fill in) must be provided so that encryption parameters (salt,
    game_id, turn, player) are preserved; the host uses those same parameters
    to decrypt the file.

    Args:
        source_header_bytes: The 16-byte payload of the FILE_HEADER block from
                             the original host-generated .x1 file (not including
                             the 2-byte block header prefix).
        waypoint_orders:     Waypoints to add; each becomes a WAYPOINT_ADD block.
        production_orders:   Production queues to replace; each becomes a
                             PRODUCTION_QUEUE_CHANGE block.

    Returns:
        Raw bytes of the new .x1 file, ready to write to disk.
    """
    from stars_web.decryptor import Decryptor
    from stars_web.file_header import FileHeader

    hdr = FileHeader(source_header_bytes)
    enc = Decryptor()
    enc.init_decryption(
        salt=hdr.salt,
        game_id=hdr.game_id,
        turn=hdr.turn,
        player_index=hdr.player_index,
        shareware=hdr.shareware,
    )

    result = bytearray()

    # Unencrypted file-header block
    result += _block_header_bytes(BLOCK_TYPE_FILE_HEADER, 16)
    result += source_header_bytes

    # Encrypted order blocks
    for order in waypoint_orders or []:
        raw = encode_waypoint_add_block(order)
        encrypted = bytes(enc.decrypt_bytes(bytearray(raw)))
        result += _block_header_bytes(BLOCK_TYPE_WAYPOINT_ADD, len(raw))
        result += encrypted

    for order in production_orders or []:
        raw = encode_production_queue_change_block(order)
        encrypted = bytes(enc.decrypt_bytes(bytearray(raw)))
        result += _block_header_bytes(BLOCK_TYPE_PRODUCTION_QUEUE_CHANGE, len(raw))
        result += encrypted

    # File footer
    result += _block_header_bytes(BLOCK_TYPE_FILE_FOOTER, 0)
    return bytes(result)
