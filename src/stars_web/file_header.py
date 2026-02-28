"""Stars! file header parser.

The file header block (type_id=8) is the first block in every Stars! file.
It contains 16 bytes of unencrypted metadata used to initialize decryption
and identify the file.

Layout (16 bytes, all little-endian):
  offset 0-3:   magic "J3J3" (4 bytes ASCII)
  offset 4-7:   game_id (uint32)
  offset 8-9:   version (packed uint16: major[4]|minor[7]|increment[5])
  offset 10-11: turn (uint16)
  offset 12-13: player_data (packed uint16: salt[11 upper]|player[5 lower])
  offset 14:    file_type (uint8: 0=xy, 1=x#, 2=hst, 3=m#, 4=h#, 5=r#)
  offset 15:    flags (uint8: bit0=submitted, bit1=host_using,
                bit2=multiple_turns, bit3=game_over, bit4=shareware)
"""

import struct
from dataclasses import dataclass


MAGIC = b"J3J3"
HEADER_SIZE = 16


@dataclass
class FileHeader:
    """Parsed Stars! file header."""

    magic: bytes
    game_id: int
    version_major: int
    version_minor: int
    version_increment: int
    turn: int
    year: int
    player_index: int
    salt: int
    file_type: int
    flags: int
    turn_submitted: bool
    host_using: bool
    multiple_turns: bool
    game_over: bool
    shareware: bool

    def __init__(self, data: bytes | bytearray):
        if len(data) < HEADER_SIZE:
            raise ValueError(
                f"File header must be at least {HEADER_SIZE} bytes, got {len(data)}"
            )

        self.magic = bytes(data[0:4])
        if self.magic != MAGIC:
            raise ValueError(
                f"Invalid magic: expected {MAGIC!r}, got {self.magic!r}"
            )

        self.game_id = struct.unpack_from("<I", data, 4)[0]

        version_data = struct.unpack_from("<H", data, 8)[0]
        self.version_major = version_data >> 12
        self.version_minor = (version_data >> 5) & 0x7F
        self.version_increment = version_data & 0x1F

        self.turn = struct.unpack_from("<H", data, 10)[0]
        self.year = 2400 + self.turn

        player_data = struct.unpack_from("<H", data, 12)[0]
        self.salt = player_data >> 5
        self.player_index = player_data & 0x1F

        self.file_type = data[14]
        self.flags = data[15]

        self.turn_submitted = bool(self.flags & (1 << 0))
        self.host_using = bool(self.flags & (1 << 1))
        self.multiple_turns = bool(self.flags & (1 << 2))
        self.game_over = bool(self.flags & (1 << 3))
        self.shareware = bool(self.flags & (1 << 4))
