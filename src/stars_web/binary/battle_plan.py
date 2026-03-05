"""Stars! battle plan block binary parser.

Handles Type 30 (BattlePlanBlock) from .m# game state files.

Each .m# file contains exactly 5 BattlePlan blocks (one per plan slot).
The same 5 plans appear in all player files for a given game turn — the
plan body bytes are identical across .m1, .m2, ... .m16; only the player_id
nibble in byte 0 differs.

Structure:
  byte 0:        (slot_index << 4) | player_id
                    slot_index : high nibble [7:4] — 0-based plan index (0..4)
                    player_id  : low  nibble [3:0] — 0-based player index
  bytes 1 .. N:  battle plan body — variable length (8-12 bytes observed).
                 The body is shared state and is currently treated as opaque.
                 Observed layout hints:
                   d[1]    — plan modifier byte (values 0-4 seen)
                   d[2]    — plan identifier byte
                   d[3]    — always 2 in observed data (separator?)
                   d[4]    — tactic or target type byte (4-8 observed)
                   d[5..]  — remaining undecoded bytes

Notes:
  - Body byte semantics are not fully reverse-engineered.  Only the slot/player
    encoding (d[0]) is confirmed from cross-file analysis.
  - The body bytes are identical between m1 and m2 files for the same slot.
  - 5 slots are standard (Stars! allows 5 battle plans per player).

References:
  - starswine4/Game.m1, Game.m2, Game-big.m1 (real test data)
  - stars-4x/starsapi-python BLOCKS dict: type 30 = "BattlePlanBlock"
"""

from __future__ import annotations

from dataclasses import dataclass

# Block type ID
BLOCK_TYPE_BATTLE_PLAN = 30

# Standard number of battle plan slots per player
BATTLE_PLAN_SLOT_COUNT = 5

# Byte-0 encoding masks
_SLOT_MASK = 0xF0  # high nibble → slot_index
_PLAYER_MASK = 0x0F  # low  nibble → player_id


@dataclass
class BattlePlan:
    """Parsed battle plan from a Type 30 block.

    Attributes:
        slot_index:  0-based plan slot (0..4), from high nibble of d[0].
        player_id:   0-based player number, from low nibble of d[0].
        raw_body:    Undecoded plan body bytes (d[1:]).  All currently known
                     field semantics are uncertain, so the full body is stored
                     for forward-compatible access.  Compare raw_body across
                     m1/m2 files — they should be identical for the same slot.
    """

    slot_index: int
    player_id: int
    raw_body: bytes


def decode_battle_plan(data: bytes) -> BattlePlan:
    """Parse a single Type 30 BattlePlan block.

    Args:
        data: Raw block payload (at least 1 byte; body may be 0 bytes).

    Returns:
        BattlePlan with slot_index, player_id, and raw_body populated.

    Raises:
        ValueError: If data is empty.
    """
    if len(data) == 0:
        raise ValueError("BattlePlan block data must not be empty")

    slot_index = (data[0] & _SLOT_MASK) >> 4
    player_id = data[0] & _PLAYER_MASK
    raw_body = bytes(data[1:])

    return BattlePlan(
        slot_index=slot_index,
        player_id=player_id,
        raw_body=raw_body,
    )


def decode_battle_plans(blocks: list[bytes]) -> list[BattlePlan]:
    """Decode a list of Type 30 block payloads.

    Args:
        blocks: List of raw block payloads (typically 5 per player file).

    Returns:
        List of BattlePlan objects in the same order as input.

    Raises:
        ValueError: If any block is empty.
    """
    return [decode_battle_plan(b) for b in blocks]
