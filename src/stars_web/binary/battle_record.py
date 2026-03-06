"""Binary decoder for Stars! Type 31 (BattleRecord) blocks.

Type 31 blocks carry the combat log for a single space battle that occurred
during the host turn.  The format is structured in three sections:

**Fixed header (16 bytes)**

    Offset  Size  Name          Notes
    ------  ----  ----          -----
    0       1     battle_id     Sequence number of this battle (1, 2, 3, …)
    1       1     reserved      Reserved byte (observed 0x00)
    2       1     version       Block format version (observed 0x02)
    3       1     num_tokens    Number of fleet token records that follow
    4       1     battle_size_x Battle board width hint (observed 0x00/0x10)
    5       1     battle_size_y Battle board height hint (observed 0x03/0x40/0x80)
    6       2     block_size    Total block size in bytes (uint16 LE)
    8       2     x             Galaxy X coordinate of the battle (uint16 LE)
    10      2     y             Galaxy Y coordinate of the battle (uint16 LE)
    12      4     header_extra  Additional header context bytes (opaque)

**Token records (num_tokens × 24 bytes each)**

Each 24-byte token record describes one fleet stack (one design, one player)
participating in the battle.  The internal layout is partially decoded:

    Within each 24-byte token
    Offset  Size  Notes
    ------  ----  -----
    0-23    24    Raw token bytes (see :class:`BattleToken`)

**Event data (variable, remainder of block)**

The battle event log encodes round-by-round actions:  tokens move, fire
weapons, take damage, and are destroyed.  The event format is complex and
vendor-specific; it is stored verbatim as ``events_raw``.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

BLOCK_TYPE_BATTLE = 31
_HEADER_SIZE = 16
_TOKEN_SIZE = 24


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BattleToken:
    """One fleet-stack participant in a battle.

    The 24-byte per-token format is partially understood.  All raw bytes are
    preserved in ``raw`` for advanced callers who need the full record.

    Attributes:
        raw: Full 24 raw bytes of the token record.
    """

    raw: bytes

    def __str__(self) -> str:
        return f"BattleToken(raw={self.raw[:6].hex()}…)"

    def __len__(self) -> int:
        return len(self.raw)


@dataclass(frozen=True)
class BattleRecord:
    """A complete Type 31 battle log block.

    Attributes:
        battle_id:    1-based sequence number for this battle in the turn.
        num_tokens:   Count of fleet stacks that participated.
        block_size:   Total block size as recorded in the header (bytes).
        x:            Galaxy X coordinate where the battle took place.
        y:            Galaxy Y coordinate where the battle took place.
        header_extra: Remaining 4 bytes of the fixed header (opaque).
        tokens:       Ordered tuple of :class:`BattleToken` records.
        events_raw:   Raw bytes of the battle event log (complex sub-format).
        raw:          Full raw block bytes.
    """

    battle_id: int
    num_tokens: int
    block_size: int
    x: int
    y: int
    header_extra: bytes
    tokens: tuple[BattleToken, ...]
    events_raw: bytes = field(hash=False, compare=False)
    raw: bytes = field(hash=False, compare=False)

    def __str__(self) -> str:
        return (
            f"BattleRecord(id={self.battle_id}, "
            f"x={self.x}, y={self.y}, "
            f"tokens={self.num_tokens}, "
            f"event_bytes={len(self.events_raw)})"
        )

    @property
    def token_count(self) -> int:
        """Number of tokens actually decoded (should equal ``num_tokens``)."""
        return len(self.tokens)


# --------------------------------------------------------------------------- #
# Decoders
# --------------------------------------------------------------------------- #


def decode_battle_block(data: bytes) -> BattleRecord:
    """Decode a single Type 31 battle record block.

    Args:
        data: Raw decrypted block payload.

    Returns:
        A :class:`BattleRecord` containing the battle header, tokens, and
        raw event bytes.

    Raises:
        ValueError: If ``data`` is shorter than the 16-byte required header.
    """
    n = len(data)
    if n < _HEADER_SIZE:
        raise ValueError(
            f"Type 31 block too short: expected >= {_HEADER_SIZE} bytes, got {n}"
        )

    battle_id = data[0]
    # data[1] reserved
    # data[2] version
    num_tokens = data[3]
    block_size = struct.unpack_from("<H", data, 6)[0]
    x = struct.unpack_from("<H", data, 8)[0]
    y = struct.unpack_from("<H", data, 10)[0]
    header_extra = bytes(data[12:16])

    # Parse token records
    tokens: list[BattleToken] = []
    offset = _HEADER_SIZE
    for _ in range(num_tokens):
        end = offset + _TOKEN_SIZE
        if end > n:
            # Partial token at end of data — take what's available, zero-pad
            token_bytes = bytes(data[offset:n]).ljust(_TOKEN_SIZE, b"\x00")
            tokens.append(BattleToken(raw=token_bytes))
            offset = n
            break
        tokens.append(BattleToken(raw=bytes(data[offset:end])))
        offset = end

    events_raw = bytes(data[offset:])

    return BattleRecord(
        battle_id=battle_id,
        num_tokens=num_tokens,
        block_size=block_size,
        x=x,
        y=y,
        header_extra=header_extra,
        tokens=tuple(tokens),
        events_raw=events_raw,
        raw=bytes(data),
    )


def decode_battles(blocks: list) -> list[BattleRecord]:
    """Decode all Type 31 blocks from a block list.

    Args:
        blocks: Iterable of :class:`~stars_web.block_reader.Block` objects.
            Non-Type-31 blocks are silently skipped.

    Returns:
        List of :class:`BattleRecord` objects in file order.
    """
    results: list[BattleRecord] = []
    for blk in blocks:
        if blk.type_id == BLOCK_TYPE_BATTLE:
            results.append(decode_battle_block(blk.data))
    return results
