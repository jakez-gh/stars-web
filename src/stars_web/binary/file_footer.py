"""Stars! file footer block binary parser.

Handles Type 0 (FileFooterBlock) from .m# game state files.

The file footer is a 2-byte block containing the game year offset.
It is the last block in every .m# file.

Structure:
  bytes 0-1: year_offset (uint16 LE)
             game_year = STARS_BASE_YEAR + year_offset
             where STARS_BASE_YEAR = 2400

References:
  - starswine4/Game.m1: footer = [18, 0] → year_offset=18 → year 2418
  - starswine4/Game-big.m1: footer = [33, 0] → year_offset=33 → year 2433
  - stars-4x/starsapi-python BLOCKS dict: type 0 = "FileFooterBlock"
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

# Block type ID
BLOCK_TYPE_FILE_FOOTER = 0

# Block size (always fixed)
FILE_FOOTER_SIZE = 2

# Stars! base year (game year 1 = 2401, year 0 = 2400)
STARS_BASE_YEAR = 2400


@dataclass
class FileFooter:
    """Parsed file footer from a Type 0 block.

    Attributes:
        year_offset: Number of years elapsed since the game started at year
                     STARS_BASE_YEAR (2400).  Observed range: 0..~100+.
        game_year:   Absolute game year = STARS_BASE_YEAR + year_offset.
    """

    year_offset: int
    game_year: int


def decode_file_footer(data: bytes) -> FileFooter:
    """Parse a single Type 0 FileFooter block.

    Args:
        data: Raw block payload (must be exactly 2 bytes).

    Returns:
        FileFooter with year_offset and game_year.

    Raises:
        ValueError: If data is not exactly 2 bytes.
    """
    if len(data) != FILE_FOOTER_SIZE:
        raise ValueError(
            f"FileFooter block must be exactly {FILE_FOOTER_SIZE} bytes, " f"got {len(data)}"
        )

    (year_offset,) = struct.unpack_from("<H", data)
    return FileFooter(
        year_offset=year_offset,
        game_year=STARS_BASE_YEAR + year_offset,
    )
