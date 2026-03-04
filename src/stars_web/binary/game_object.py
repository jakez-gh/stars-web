"""Game object block parsing for Stars! game files.

Block Type: 25 (0x19)
Purpose: Map objects (minefields, wormholes, salvage, packets)
Location: After message blocks, before file footer in M# files

Field Layout (variable-length):
  Bytes 0-1: Object count (uint16 LE)
  Bytes 2+: Object data (varies by type)

Object Types:
  0 = Minefield
  1 = Wormhole
  2 = Salvage
  3 = Packet

Each object starts with type byte, then type-specific fields.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Union


BLOCK_TYPE_OBJECT = 25


class ObjectType(IntEnum):
    """Object type identifiers in block data."""

    MINEFIELD = 0
    WORMHOLE = 1
    SALVAGE = 2
    PACKET = 3


@dataclass
class Minefield:
    """Represents a minefield on the map.

    Minefields are deployed by players and grow/decay over time.
    They damage ships and fleets that enter their radius.

    Fields:
      x, y: Position on map (-10000 to 10000)
      radius: Detection/damage radius (1-200)
      owner: Player who deployed mine (0-15), or 16 for neutral
      quantity: Number of mines (1-10000+)
    """

    x: int
    y: int
    radius: int
    owner: int
    quantity: int

    def __post_init__(self):
        """Validate minefield fields."""
        if not (-10000 <= self.x <= 10000):
            raise ValueError(f"x must be -10000 to 10000, got {self.x}")
        if not (-10000 <= self.y <= 10000):
            raise ValueError(f"y must be -10000 to 10000, got {self.y}")
        if not (0 <= self.owner <= 16):
            raise ValueError(f"owner must be 0-16, got {self.owner}")
        if not (1 <= self.radius <= 200):
            raise ValueError(f"radius must be 1-200, got {self.radius}")
        if not (1 <= self.quantity):
            raise ValueError(f"quantity must be >= 1, got {self.quantity}")


@dataclass
class Wormhole:
    """Represents a wormhole pair on the map.

    Wormholes provide fast travel between distant locations.
    Stability affects passage risk.

    Fields:
      x1, y1: First endpoint
      x2, y2: Second endpoint
      stability: Stability rating (0-100%)
    """

    x1: int
    y1: int
    x2: int
    y2: int
    stability: int

    def __post_init__(self):
        """Validate wormhole fields."""
        if not (-10000 <= self.x1 <= 10000 and -10000 <= self.y1 <= 10000):
            raise ValueError(f"Endpoint 1 out of bounds: ({self.x1}, {self.y1})")
        if not (-10000 <= self.x2 <= 10000 and -10000 <= self.y2 <= 10000):
            raise ValueError(f"Endpoint 2 out of bounds: ({self.x2}, {self.y2})")
        if not (0 <= self.stability <= 100):
            raise ValueError(f"stability must be 0-100, got {self.stability}")


@dataclass
class Salvage:
    """Represents salvage materials on the map.

    Leftover resources from destroyed ships or packets.

    Fields:
      x, y: Position on map
      ironium, boranium, germanium: Mineral amounts
      colonists: Population units
    """

    x: int
    y: int
    ironium: int
    boranium: int
    germanium: int
    colonists: int = 0

    def __post_init__(self):
        """Validate salvage fields."""
        if not (-10000 <= self.x <= 10000 and -10000 <= self.y <= 10000):
            raise ValueError(f"Position out of bounds: ({self.x}, {self.y})")
        if not (self.ironium >= 0 and self.boranium >= 0 and self.germanium >= 0):
            raise ValueError("Mineral amounts must be non-negative")
        if not (self.colonists >= 0):
            raise ValueError("Colonists must be non-negative")


@dataclass
class Packet:
    """Represents a cargo packet in transit.

    Packets are cargo transfers between locations.

    Fields:
      x, y: Current position
      owner: Owner player (0-15)
      cargo_type: Type of cargo (mineral, colonists, etc.)
      cargo_amount: Quantity of cargo
    """

    x: int
    y: int
    owner: int
    cargo_type: int
    cargo_amount: int

    def __post_init__(self):
        """Validate packet fields."""
        if not (-10000 <= self.x <= 10000 and -10000 <= self.y <= 10000):
            raise ValueError(f"Position out of bounds: ({self.x}, {self.y})")
        if not (0 <= self.owner <= 15):
            raise ValueError(f"owner must be 0-15, got {self.owner}")
        if not (self.cargo_amount >= 0):
            raise ValueError("cargo_amount must be non-negative")


def decode_objects(data: bytes) -> List[Union[Minefield, Wormhole, Salvage, Packet]]:
    """Parse an object block's data into game objects.

    Args:
        data: Raw decrypted block data (bytes)

    Returns:
        List of parsed game objects (Minefield, Wormhole, Salvage, or Packet)

    Raises:
        ValueError: If data is malformed
        struct.error: If struct unpacking fails
    """
    if not data or len(data) < 2:
        raise ValueError(f"Object block data too short: {len(data)} bytes")

    objects = []
    count = struct.unpack_from("<H", data, 0)[0]

    offset = 2
    for _ in range(count):
        if offset >= len(data):
            break

        obj_type = data[offset]

        try:
            if obj_type == ObjectType.MINEFIELD:
                if offset + 9 > len(data):
                    raise ValueError("Truncated minefield data")

                x = struct.unpack_from("<h", data, offset + 1)[0]
                y = struct.unpack_from("<h", data, offset + 3)[0]
                radius = data[offset + 5]
                owner = data[offset + 6]
                quantity = struct.unpack_from("<H", data, offset + 7)[0]

                obj = Minefield(x=x, y=y, radius=radius, owner=owner, quantity=quantity)
                objects.append(obj)
                offset += 9

            elif obj_type == ObjectType.WORMHOLE:
                if offset + 10 > len(data):
                    raise ValueError("Truncated wormhole data")

                x1 = struct.unpack_from("<h", data, offset + 1)[0]
                y1 = struct.unpack_from("<h", data, offset + 3)[0]
                x2 = struct.unpack_from("<h", data, offset + 5)[0]
                y2 = struct.unpack_from("<h", data, offset + 7)[0]
                stability = data[offset + 9]

                obj = Wormhole(x1=x1, y1=y1, x2=x2, y2=y2, stability=stability)
                objects.append(obj)
                offset += 10

            elif obj_type == ObjectType.SALVAGE:
                if offset + 12 > len(data):
                    raise ValueError("Truncated salvage data")

                x = struct.unpack_from("<h", data, offset + 1)[0]
                y = struct.unpack_from("<h", data, offset + 3)[0]
                ironium = struct.unpack_from("<H", data, offset + 5)[0]
                boranium = struct.unpack_from("<H", data, offset + 7)[0]
                germanium = struct.unpack_from("<H", data, offset + 9)[0]
                colonists = struct.unpack_from("<H", data, offset + 11)[0]

                obj = Salvage(
                    x=x,
                    y=y,
                    ironium=ironium,
                    boranium=boranium,
                    germanium=germanium,
                    colonists=colonists,
                )
                objects.append(obj)
                offset += 13

            elif obj_type == ObjectType.PACKET:
                if offset + 9 > len(data):
                    raise ValueError("Truncated packet data")

                x = struct.unpack_from("<h", data, offset + 1)[0]
                y = struct.unpack_from("<h", data, offset + 3)[0]
                owner = data[offset + 5]
                cargo_type = data[offset + 6]
                cargo_amount = struct.unpack_from("<H", data, offset + 7)[0]

                obj = Packet(
                    x=x,
                    y=y,
                    owner=owner,
                    cargo_type=cargo_type,
                    cargo_amount=cargo_amount,
                )
                objects.append(obj)
                offset += 9

            else:
                raise ValueError(f"Unknown object type: {obj_type}")

        except (ValueError, struct.error) as e:
            raise ValueError(f"Error parsing object at offset {offset}: {e}")

    return objects


def encode_objects(objects: List[Union[Minefield, Wormhole, Salvage, Packet]]) -> bytes:
    """Serialize objects back to binary block data.

    Args:
        objects: List of game objects to encode

    Returns:
        Raw block data (bytes)
    """
    data = bytearray(2)
    struct.pack_into("<H", data, 0, len(objects))

    for obj in objects:
        if isinstance(obj, Minefield):
            data.append(ObjectType.MINEFIELD)
            data.extend(struct.pack("<h", obj.x))
            data.extend(struct.pack("<h", obj.y))
            data.append(obj.radius)
            data.append(obj.owner)
            data.extend(struct.pack("<H", obj.quantity))

        elif isinstance(obj, Wormhole):
            data.append(ObjectType.WORMHOLE)
            data.extend(struct.pack("<h", obj.x1))
            data.extend(struct.pack("<h", obj.y1))
            data.extend(struct.pack("<h", obj.x2))
            data.extend(struct.pack("<h", obj.y2))
            data.append(obj.stability)

        elif isinstance(obj, Salvage):
            data.append(ObjectType.SALVAGE)
            data.extend(struct.pack("<h", obj.x))
            data.extend(struct.pack("<h", obj.y))
            data.extend(struct.pack("<H", obj.ironium))
            data.extend(struct.pack("<H", obj.boranium))
            data.extend(struct.pack("<H", obj.germanium))
            data.extend(struct.pack("<H", obj.colonists))

        elif isinstance(obj, Packet):
            data.append(ObjectType.PACKET)
            data.extend(struct.pack("<h", obj.x))
            data.extend(struct.pack("<h", obj.y))
            data.append(obj.owner)
            data.append(obj.cargo_type)
            data.extend(struct.pack("<H", obj.cargo_amount))

    return bytes(data)


__all__ = [
    "BLOCK_TYPE_OBJECT",
    "ObjectType",
    "Minefield",
    "Wormhole",
    "Salvage",
    "Packet",
    "decode_objects",
    "encode_objects",
]
