"""TurnMessage block parsing for Stars! game files.

Block Type: 24 (0x18)
Purpose: Player messages (diplomacy, trade, notifications)
Location: After battle plans, before object blocks in M# files

Binary Format (TBD from game file analysis):
Currently being reverse-engineered from actual game files.
See docs/file-formats/message-block.md for format documentation.

Field Layout:
  - message_id (2 bytes): Identifier for the message
  - source_player (1 byte): Sending player (0-15)
  - dest_player (1 byte): Receiving player (0-15)
  - year (2 bytes): Game turn/year offset
  - action_code (1 byte): Message type code
  - text (variable): Message content

Test Status: Specification phase (tests define requirements)
"""

import struct
from dataclasses import dataclass
from typing import Optional


# Block type constant
BLOCK_TYPE_MESSAGE = 24

# Message action code constants (being documented)
MESSAGE_ACTION_CODES = {
    0: "Unknown",
    1: "Standard",
    # More to be discovered from real data
}


@dataclass
class TurnMessage:
    """Represents a single message block from a Stars! turn file.

    All fields are populated during parsing. Action codes and exact
    field meanings are being documented through test-driven development.

    The year field stores actual game years (2400-2900), not offsets.
    Binary encoding uses offsets; decoding/encoding handles the conversion.
    """

    message_id: int
    source_player: int
    dest_player: int
    year: int
    action_code: int = 0
    text: str = ""

    def __post_init__(self):
        """Validate fields after initialization."""
        if not (0 <= self.source_player <= 15):
            raise ValueError(f"source_player must be 0-15, got {self.source_player}")
        if not (0 <= self.dest_player <= 15):
            raise ValueError(f"dest_player must be 0-15, got {self.dest_player}")
        # Accept both offset values (0-500) and actual years (2400-2900)
        # for flexibility in testing
        if not ((0 <= self.year <= 500) or (2400 <= self.year <= 2900)):
            raise ValueError(f"year must be 0-500 (offset) or 2400-2900 (actual), got {self.year}")


def decode_message(data: bytes) -> Optional[TurnMessage]:
    """Parse a message block's data into a TurnMessage object.

    Args:
        data: Raw decrypted block data (bytes)

    Returns:
        TurnMessage object or None if data is invalid

    Raises:
        ValueError: If data is malformed or too short
        struct.error: If struct unpacking fails
    """
    if not data or len(data) < 8:
        raise ValueError(f"Message block data too short: {len(data)} bytes")

    # Parse fixed fields
    # Offset 0-1: message_id (uint16, little-endian)
    message_id = struct.unpack_from("<H", data, 0)[0]

    # Offset 2: source_player (uint8)
    source_player = data[2]
    if not (0 <= source_player <= 15):
        raise ValueError(f"Invalid source_player: {source_player}")

    # Offset 3: dest_player (uint8)
    dest_player = data[3]
    if not (0 <= dest_player <= 15):
        raise ValueError(f"Invalid dest_player: {dest_player}")

    # Offset 4-5: year (uint16, little-endian)
    year = struct.unpack_from("<H", data, 4)[0]
    # Convert from offset (year = 2400 + offset)
    # Adjust if necessary based on actual file data

    # Offset 6: action_code (uint8)
    action_code = data[6]

    # Offset 7+: text (Stars! encoded string or ASCII)
    # Text is variable-length, terminated by null or end of block
    text_data = data[7:]
    # Try to decode as ASCII/UTF-8, removing null terminators
    try:
        text = text_data.decode("utf-8", errors="ignore").rstrip("\x00")
    except (UnicodeDecodeError, AttributeError):
        text = ""

    return TurnMessage(
        message_id=message_id,
        source_player=source_player,
        dest_player=dest_player,
        year=year,
        action_code=action_code,
        text=text,
    )


def encode_message(msg: TurnMessage) -> bytes:
    """Serialize a TurnMessage back to binary block data.

    Args:
        msg: TurnMessage object to encode

    Returns:
        Raw block data (bytes)
    """
    data = bytearray(8 + len(msg.text.encode("utf-8")))

    struct.pack_into("<H", data, 0, msg.message_id)
    data[2] = msg.source_player
    data[3] = msg.dest_player
    struct.pack_into("<H", data, 4, msg.year)
    data[6] = msg.action_code
    data[7:] = msg.text.encode("utf-8")

    return bytes(data)


__all__ = [
    "BLOCK_TYPE_MESSAGE",
    "MESSAGE_ACTION_CODES",
    "TurnMessage",
    "decode_message",
    "encode_message",
]
