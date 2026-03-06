"""Stars! production queue block binary parser.

Handles Type 28 (ProductionQueueBlock) from .m# game state files.

Each ProductionQueue block represents the build queue for one planet.
The block payload is a sequence of 4-byte items; the total block length
is always a multiple of 4.

Structure (variable, N × 4 bytes):
  Each item (4 bytes):
    bytes 0-1: item_type (uint16 LE) — identifies what to build.
               Common values observed across test data:
                 0x3001 (12289) — ship design item (with design encoded in
                                  the low byte, so 0x3001 = design? unclear)
                 0x13FC (5116)  — mine layer or factory variant
                 0x07FB (2043)  — mine variant
                 0x17FB (6139)  — mine variant
                 0x03FC (1020)  — mine/factory variant
                 0x0FFC (4092)  — mine/factory variant
               Full semantics of item_type bits are not yet decoded.
    bytes 2-3: quantity (uint16 LE) — number of units to build.

Observations:
  - Multiple Type 28 blocks can appear per file (one per planet with a
    non-empty queue, typically).
  - Single-item queues produce 4-byte blocks.
  - The 9-item "maintenance" queues (36 bytes) seen in Game-big.m1 are all
    identical items with quantity=2.
  - All block sizes observed: 4, 8, 12, 16, 36, 40, 48.

References:
  - starswine4/Game.m1, Game-big.m1 (real test data)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

# Block type ID
BLOCK_TYPE_PRODUCTION_QUEUE = 28

# Bytes per production item
PRODUCTION_ITEM_SIZE = 4

# Struct format for one production item (uint16 LE × 2)
_ITEM_STRUCT = struct.Struct("<HH")


@dataclass(frozen=True)
class ProductionItem:
    """A single item in a planet's production queue.

    Attributes:
        item_type:  Type ID of the item to build (uint16).  The exact
                    encoding of item_type bits (ship design index, building
                    category, etc.) is not yet fully decoded.
        quantity:   Number of units to build (uint16).
    """

    item_type: int
    quantity: int


@dataclass
class ProductionQueue:
    """Parsed production queue from a Type 28 block.

    Attributes:
        items:  Ordered list of items in the build queue.
        raw:    Complete block payload bytes.
    """

    items: list[ProductionItem]
    raw: bytes = field(repr=False)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)


def decode_production_queue(data: bytes) -> ProductionQueue:
    """Parse a single ProductionQueue (Type 28) block payload.

    Args:
        data: Block payload; must be a non-empty multiple of
              PRODUCTION_ITEM_SIZE (4) bytes.

    Returns:
        A ProductionQueue with all items decoded.

    Raises:
        ValueError: If data is empty or not a multiple of
                    PRODUCTION_ITEM_SIZE bytes.
    """
    if len(data) == 0:
        raise ValueError("ProductionQueue data must be non-empty")
    if len(data) % PRODUCTION_ITEM_SIZE != 0:
        raise ValueError(
            f"ProductionQueue data length {len(data)} is not a multiple of "
            f"{PRODUCTION_ITEM_SIZE}"
        )
    items: list[ProductionItem] = []
    for offset in range(0, len(data), PRODUCTION_ITEM_SIZE):
        item_type, quantity = _ITEM_STRUCT.unpack_from(data, offset)
        items.append(ProductionItem(item_type=item_type, quantity=quantity))
    return ProductionQueue(items=items, raw=bytes(data))


def decode_production_queues(file_data: bytes) -> list[ProductionQueue]:
    """Decode all ProductionQueue blocks from a complete .m# file.

    Reads the file using :func:`~stars_web.block_reader.read_blocks` and
    returns one :class:`ProductionQueue` per Type 28 block found.

    Args:
        file_data: Raw bytes of a full .m# player file.

    Returns:
        List of ProductionQueue objects in file order (one per planet
        that has a build queue).
    """
    from stars_web.block_reader import read_blocks

    queues: list[ProductionQueue] = []
    for block in read_blocks(file_data):
        if block.type_id == BLOCK_TYPE_PRODUCTION_QUEUE:
            queues.append(decode_production_queue(block.data))
    return queues
