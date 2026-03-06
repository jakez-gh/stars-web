"""Binary decoder for Stars! Type 6 (PlayerRaceData) blocks.

Two distinct size classes share block type 6:

**Compact variant (size < 50)**
    Appears to encode per-file game metadata or a brief player summary
    (exact semantics TBD). All instances of the size-15 block within a
    game have identical content. Stored verbatim with the first few bytes
    extracted as a known field (``record_type``).

    Offset  Size  Name          Notes
    ------  ----  ----          -----
    0       1     record_type   Opaque type byte (e.g. 0x0a = 10)
    1       2     field_01      uint16 LE
    3       2     field_03      uint16 LE
    5+      var   extra         Remaining raw bytes

**Full variant (size >= 50)**
    Full per-player race descriptor, including PRT, habitability
    preferences, and game context. Fixed header of 25 bytes followed by
    variable body.

    Offset  Size  Name          Notes
    ------  ----  ----          -----
    0       1     player_index  0-based player slot (0-8)
    1       1     prt_id        Primary Racial Trait (0-10)
    2       2     field_02      uint16 LE  (TBD; changes per turn)
    4       2     field_04      uint16 LE
    6       2     field_06      uint16 LE
    8       2     field_08      uint16 LE  (possibly score)
    10      2     field_10      uint16 LE  (possibly planets owned)
    12      4     game_id       uint32 LE; non-zero = multiplayer game  (5 uint16 + uint32)
    16      9     hab_data      Habitat settings (grav/temp/rad × low/ideal/high)
    25+     var   extra         Remaining body bytes

Habitat bytes are 0xFF when the player is immune to that factor.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

_LARGE_THRESHOLD = 50  # bytes; size >= this → full PlayerRaceData

# Compact header: record_type(1) + field_01(2) + field_03(2)
_FMT_COMPACT_HDR = "<BHH"
_COMPACT_HDR_SIZE = struct.calcsize(_FMT_COMPACT_HDR)  # 5

# Full header: player_index(1) + prt_id(1) + five uint16 + uint32 + 9 bytes hab
# B(1)+B(1)+H(2)+H(2)+H(2)+H(2)+H(2)+I(4) = 16 bytes, then 9 hab = 25 total
_FULL_HDR_STATIC = "<BBHHHHHI"
_FULL_HDR_STATIC_SIZE = struct.calcsize(_FULL_HDR_STATIC)  # 1+1+5*2+4 = 16
_HAB_DATA_SIZE = 9
_FULL_HDR_SIZE = _FULL_HDR_STATIC_SIZE + _HAB_DATA_SIZE  # 25

HAB_IMMUNE = 0xFF  # Byte value meaning "immune to this habitat factor"


@dataclass(frozen=True)
class PlayerCompact:
    """Compact Type 6 variant (size < 50 bytes) — brief player/game summary.

    Attributes:
        record_type:  Opaque type byte at offset 0.
        field_01:     uint16 at offset 1.
        field_03:     uint16 at offset 3.
        extra:        Remaining raw bytes from offset 5 onward.
    """

    record_type: int
    field_01: int
    field_03: int
    extra: bytes = field(hash=False, compare=False)

    def __str__(self) -> str:
        return (
            f"PlayerCompact(type={self.record_type:#04x}, "
            f"f1={self.field_01}, f3={self.field_03}, "
            f"extra_len={len(self.extra)})"
        )


@dataclass(frozen=True)
class PlayerRaceData:
    """Full Type 6 variant (size >= 50) — complete per-player race descriptor.

    Attributes:
        player_index:  0-based player slot number (0-8).
        prt_id:        Primary Racial Trait index (0 = HE … 10).
        field_02:      uint16 at offset 2 (TBD; varies per turn).
        field_04:      uint16 at offset 4.
        field_06:      uint16 at offset 6.
        field_08:      uint16 at offset 8 (possibly total score).
        field_10:      uint16 at offset 10 (possibly planets owned).
        game_id:       uint32 identifying the multiplayer game session.
        hab_data:      9 raw habitat bytes (gravity / temperature / radiation
                       low–ideal–high). ``0xFF`` = immune to that factor.
        extra:         Remaining body bytes after offset 25.
    """

    player_index: int
    prt_id: int
    field_02: int
    field_04: int
    field_06: int
    field_08: int
    field_10: int
    game_id: int
    hab_data: bytes = field(hash=False, compare=False)
    extra: bytes = field(hash=False, compare=False)

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    @property
    def is_multiplayer(self) -> bool:
        """True when ``game_id`` is non-zero (joined a multiplayer game)."""
        return self.game_id != 0

    @property
    def grav_immune(self) -> bool:
        """True when the race is immune to gravity."""
        return len(self.hab_data) >= 3 and self.hab_data[0] == HAB_IMMUNE

    @property
    def temp_immune(self) -> bool:
        """True when the race is immune to temperature."""
        return len(self.hab_data) >= 6 and self.hab_data[3] == HAB_IMMUNE

    @property
    def rad_immune(self) -> bool:
        """True when the race is immune to radiation."""
        return len(self.hab_data) >= 9 and self.hab_data[6] == HAB_IMMUNE

    def __str__(self) -> str:
        imm = "".join(
            [
                "G" if self.grav_immune else "g",
                "T" if self.temp_immune else "t",
                "R" if self.rad_immune else "r",
            ]
        )
        return (
            f"PlayerRaceData(player={self.player_index}, "
            f"prt={self.prt_id}, game_id={self.game_id:#010x}, "
            f"immunity={imm}, f8={self.field_08}, f10={self.field_10})"
        )


# --------------------------------------------------------------------------- #
# Decoders
# --------------------------------------------------------------------------- #


def decode_player_race_block(
    data: bytes,
) -> PlayerCompact | PlayerRaceData:
    """Decode a single Type 6 block.

    Dispatches on block size:
    - size < 50  → :class:`PlayerCompact`
    - size >= 50 → :class:`PlayerRaceData`

    Args:
        data: Raw decrypted block payload.

    Returns:
        A :class:`PlayerCompact` or :class:`PlayerRaceData` instance.

    Raises:
        ValueError: If ``data`` is shorter than 5 bytes (below minimum).
    """
    n = len(data)
    if n < _COMPACT_HDR_SIZE:
        raise ValueError(
            f"Type 6 block too short: expected >= {_COMPACT_HDR_SIZE} bytes, got {n}"
        )

    if n < _LARGE_THRESHOLD:
        record_type, field_01, field_03 = struct.unpack_from(
            _FMT_COMPACT_HDR, data
        )
        return PlayerCompact(
            record_type=record_type,
            field_01=field_01,
            field_03=field_03,
            extra=bytes(data[_COMPACT_HDR_SIZE:]),
        )

    # Full variant — parse static header (16 bytes) + 9 hab bytes
    (
        player_index,
        prt_id,
        field_02,
        field_04,
        field_06,
        field_08,
        field_10,
        game_id,
    ) = struct.unpack_from(_FULL_HDR_STATIC, data)
    static_size = struct.calcsize(_FULL_HDR_STATIC)  # 16
    hab_start = static_size
    hab_end = hab_start + _HAB_DATA_SIZE  # 25
    hab_data = bytes(data[hab_start:hab_end])
    extra = bytes(data[hab_end:])

    return PlayerRaceData(
        player_index=player_index,
        prt_id=prt_id,
        field_02=field_02,
        field_04=field_04,
        field_06=field_06,
        field_08=field_08,
        field_10=field_10,
        game_id=game_id,
        hab_data=hab_data,
        extra=extra,
    )


def decode_player_races(
    blocks: list,
) -> list[PlayerCompact | PlayerRaceData]:
    """Decode all Type 6 blocks from a block list.

    Args:
        blocks: Iterable of :class:`~stars_web.block_reader.Block` objects.
            Non-Type-6 blocks are silently skipped.

    Returns:
        List of decoded :class:`PlayerCompact` and :class:`PlayerRaceData`
        objects in file order.
    """
    results: list[PlayerCompact | PlayerRaceData] = []
    for blk in blocks:
        if blk.type_id == 6:
            results.append(decode_player_race_block(blk.data))
    return results
