"""Stars! file block reader.

Reads a complete Stars! binary file into a list of parsed blocks.
Handles block header parsing, decryption initialization from the
file header block (type 8), and XOR decryption of all other blocks.

Block header format (2 bytes, uint16 LE):
  bits 10-15: type_id (6 bits, 0-63)
  bits 0-9:   size (10 bits, 0-1023)

Reference: stars-4x/starsapi-python by raptor (2014).
"""

import struct
from dataclasses import dataclass

from stars_web.decryptor import Decryptor
from stars_web.file_header import FileHeader


# Block type IDs
FILE_HEADER_TYPE = 8
FILE_FOOTER_TYPE = 0
PLANETS_TYPE = 7


@dataclass
class Block:
    """A single parsed block from a Stars! file."""

    type_id: int
    size: int
    data: bytes
    encrypted: bool = False
    file_header: FileHeader | None = None
    extra_data: bytes = b""  # For type 7 (planets): planet coordinate data


def read_blocks(file_bytes: bytes | bytearray) -> list[Block]:
    """Parse a Stars! file into a list of Block objects.

    The first block must be a file header (type 8, unencrypted).
    It provides the parameters needed to initialize decryption
    for all subsequent blocks.

    Args:
        file_bytes: Raw bytes of a Stars! file.

    Returns:
        List of Block objects with decrypted data.
    """
    if not file_bytes:
        return []

    blocks: list[Block] = []
    decryptor = Decryptor()
    offset = 0

    while offset + 2 <= len(file_bytes):
        # Read 2-byte block header
        block_header = struct.unpack_from("<H", file_bytes, offset)[0]
        type_id = block_header >> 10
        size = block_header & 0x3FF
        offset += 2

        # Read block data
        data = file_bytes[offset : offset + size]
        offset += size

        if type_id == FILE_HEADER_TYPE:
            # File header block — not encrypted
            file_hdr = FileHeader(data)
            block = Block(
                type_id=type_id,
                size=size,
                data=bytes(data),
                encrypted=False,
                file_header=file_hdr,
            )
            # Initialize decryptor for subsequent blocks
            decryptor.init_decryption(
                salt=file_hdr.salt,
                game_id=file_hdr.game_id,
                turn=file_hdr.turn,
                player_index=file_hdr.player_index,
                shareware=file_hdr.shareware,
            )

        elif type_id == FILE_FOOTER_TYPE:
            # Footer block — not encrypted
            block = Block(
                type_id=type_id,
                size=size,
                data=bytes(data),
                encrypted=False,
            )

        else:
            # All other blocks are encrypted
            decrypted = decryptor.decrypt_bytes(bytearray(data))
            block = Block(
                type_id=type_id,
                size=size,
                data=bytes(decrypted),
                encrypted=True,
            )

            # Type 7 (planets) has extra unencrypted data appended:
            # planet_count * 4 bytes of planet coordinate data.
            # The planet_count is at offset 10-11 in the decrypted block data.
            if type_id == PLANETS_TYPE and len(decrypted) >= 12:
                planet_count = struct.unpack_from("<H", decrypted, 10)[0]
                extra_size = planet_count * 4
                block.extra_data = bytes(file_bytes[offset : offset + extra_size])
                offset += extra_size

        blocks.append(block)

    return blocks
