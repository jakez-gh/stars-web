"""Stars! player scores block binary parser.

Handles Type 45 (PlayerScoresBlock) from .m# game state files.

Each .m# file contains one PlayerScores block per player in the game.
The block is a fixed 24-byte structure encoding a snapshot of the player's
score at the time the file was generated.

Layout (24 bytes):
  bytes 0-1:   player_raw (uint16 LE) — player_id = player_raw - PLAYER_RAW_OFFSET
  bytes 2-3:   num_planets (uint16 LE) — confirmed by cross-file analysis
  bytes 4-7:   resources_a (uint32 LE) — smaller score component (uncertain semantics)
  bytes 8-11:  total_score (uint32 LE) — larger score value, likely victory points
  bytes 12-13: starbases (uint16 LE) — unconfirmed; possibly starbase count
  bytes 14-15: ships_unarmed (uint16 LE) — unconfirmed
  bytes 16-17: ships_escort (uint16 LE) — unconfirmed
  bytes 18-19: ships_capital (uint16 LE) — unconfirmed
  bytes 20-21: tech_score (uint16 LE) — unconfirmed; 0 in early-game data
  bytes 22-23: rank (uint16 LE) — unconfirmed; possibly tech advancement total

Notes:
  - The 'player_raw' field in .m1 = 0x20 (player 0), in .m2 = 0x21 (player 1), etc.
  - A 16-player game has 16 PlayerScore blocks per .m# file, one per player.
  - All field semantics except player_id and num_planets are uncertain; field names
    reflect the best available interpretation from game data analysis.
  - The block is identical between .m1 and .m2 files for shared players.

References:
  - starswine4/Game.m1, Game.m2, Game-big.m1 (real test data)
  - stars-4x/starsapi-python BLOCKS dict: type 45 = "PlayerScoresBlock"
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

# Block type ID
BLOCK_TYPE_PLAYER_SCORES = 45

# Block size (always fixed)
PLAYER_SCORES_BLOCK_SIZE = 24

# Offset applied to raw player_id field to get 0-based player index
PLAYER_RAW_OFFSET = 0x20  # 32


@dataclass
class PlayerScore:
    """Parsed player score from a Type 45 block.

    Attributes:
        player_id:     0-based player index (player_raw - 0x20).
        num_planets:   Number of planets the player owns (bytes 2-3).
        resources_a:   Smaller score component — uncertain semantics,
                       possibly resources-per-year (bytes 4-7, uint32).
        total_score:   Larger score value — likely total victory points
                       (bytes 8-11, uint32).
        starbases:     Unconfirmed; likely starbase count (bytes 12-13).
        ships_unarmed: Unconfirmed; possibly unarmed ship count (bytes 14-15).
        ships_escort:  Unconfirmed; possibly escort ship count (bytes 16-17).
        ships_capital: Unconfirmed; possibly capital ship count (bytes 18-19).
        tech_score:    Unconfirmed; 0 in early-game data (bytes 20-21).
        rank:          Unconfirmed; uncertain semantics (bytes 22-23).
        raw:           Complete 24-byte payload for forward compatibility.
    """

    player_id: int
    num_planets: int
    resources_a: int
    total_score: int
    starbases: int
    ships_unarmed: int
    ships_escort: int
    ships_capital: int
    tech_score: int
    rank: int
    raw: bytes


def decode_player_score(data: bytes) -> PlayerScore:
    """Parse a single Type 45 PlayerScores block.

    Args:
        data: Raw block payload bytes (must be exactly 24 bytes).

    Returns:
        PlayerScore with all fields decoded.

    Raises:
        ValueError: If data is not exactly 24 bytes.
    """
    if len(data) != PLAYER_SCORES_BLOCK_SIZE:
        raise ValueError(
            f"PlayerScores block must be exactly {PLAYER_SCORES_BLOCK_SIZE} bytes, "
            f"got {len(data)}"
        )

    (
        player_raw,  # uint16 — d[0:2]
        num_planets,  # uint16 — d[2:4]
        resources_a,  # uint32 — d[4:8]
        total_score,  # uint32 — d[8:12]
        starbases,  # uint16 — d[12:14]
        ships_unarmed,  # uint16 — d[14:16]
        ships_escort,  # uint16 — d[16:18]
        ships_capital,  # uint16 — d[18:20]
        tech_score,  # uint16 — d[20:22]
        rank,  # uint16 — d[22:24]
    ) = struct.unpack_from("<HHIIHHHHHH", data)

    player_id = player_raw - PLAYER_RAW_OFFSET

    return PlayerScore(
        player_id=player_id,
        num_planets=num_planets,
        resources_a=resources_a,
        total_score=total_score,
        starbases=starbases,
        ships_unarmed=ships_unarmed,
        ships_escort=ships_escort,
        ships_capital=ships_capital,
        tech_score=tech_score,
        rank=rank,
        raw=bytes(data),
    )


def decode_player_scores(blocks: list[bytes]) -> list[PlayerScore]:
    """Decode a list of Type 45 block payloads into PlayerScore objects.

    Args:
        blocks: List of raw 24-byte payloads.

    Returns:
        List of PlayerScore objects in the same order as input.

    Raises:
        ValueError: If any block is not exactly 24 bytes.
    """
    return [decode_player_score(b) for b in blocks]
