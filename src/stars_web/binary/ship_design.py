"""Binary decoder for Stars! Type 43 (ShipDesign) blocks.

Two variants exist based on block size:

**2-byte variant** – design *count* for the owning player:
    struct: ``<H`` → ``count`` (uint16 LE)

**18-byte variant** – a single ship design record:
    Offset  Size  Name           Notes
    ------  ----  ----           -----
    0       1     design_id      Slot index, 0-15
    1       1     player_tag     Opaque per-player/race identifier
    2       2     cost_iron      Iron cost (uint16 LE)
    4       2     cost_boron     Boron cost (uint16 LE)
    6       2     cost_germ_pack Germanium + flags packed (uint16 LE)
    8       2     slots_a        Component-slot count A (uint16 LE)
    10      2     slots_b        Component-slot count B (uint16 LE)
    12      2     slots_c        Component-slot count C (uint16 LE)
    14      2     tech_flags     0xC000 | count bits (uint16 LE)
    16      2     padding        Usually 0x0020; reserved

Field semantics beyond the design slot / player tag are partially
reversed; unknown fields are preserved verbatim for future work.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

_FMT_COUNT = "<H"
_FMT_COUNT_SIZE = struct.calcsize(_FMT_COUNT)  # 2

_FMT_DESIGN = "<BBHHHHHHHHb"  # intentionally keeps fields separate; 17 bytes?
# Actually correct format: BB = 2 bytes, then 8 × H = 16 bytes → 18 total ✓
_FMT_DESIGN = "<BBHHHHHHHH"
_FMT_DESIGN_SIZE = struct.calcsize(_FMT_DESIGN)  # 1+1+2×8 = 18


@dataclass(frozen=True)
class ShipDesignCount:
    """2-byte Type 43 variant: total ship designs owned by this player."""

    count: int  # uint16 — number of design records present in this file

    def __str__(self) -> str:
        return f"ShipDesignCount(count={self.count})"


@dataclass(frozen=True)
class ShipDesign:
    """18-byte Type 43 variant: a single ship design record.

    Attributes:
        design_id:      Slot index (0-15) identifying this design slot.
        player_tag:     Opaque byte identifying the owning player/race.
        cost_iron:      Iron cost component.
        cost_boron:     Boron cost component.
        cost_germ_pack: Packed uint16; low byte ≈ germanium cost, high byte
                        encodes additional flags.
        slots_a:        Component-slot count field A.
        slots_b:        Component-slot count field B.
        slots_c:        Component-slot count field C.
        tech_flags:     Encoded technology / equipment flags (0xC000 | bits).
        padding:        Reserved; typically 0x0020.
    """

    design_id: int
    player_tag: int
    cost_iron: int
    cost_boron: int
    cost_germ_pack: int
    slots_a: int
    slots_b: int
    slots_c: int
    tech_flags: int
    padding: int

    @property
    def cost_germanium(self) -> int:
        """Low byte of ``cost_germ_pack``."""
        return self.cost_germ_pack & 0xFF

    @property
    def tech_count(self) -> int:
        """Number of tech/equipment slots (low 6 bits of ``tech_flags``)."""
        return self.tech_flags & 0x003F

    def __str__(self) -> str:
        return (
            f"ShipDesign(id={self.design_id}, player={self.player_tag:#04x}, "
            f"iron={self.cost_iron}, boron={self.cost_boron}, "
            f"germ={self.cost_germanium}, tech={self.tech_count})"
        )


# --------------------------------------------------------------------------- #
# Decoders
# --------------------------------------------------------------------------- #


def decode_ship_design_block(
    data: bytes,
) -> ShipDesignCount | ShipDesign:
    """Decode a single Type 43 block.

    Dispatches on ``len(data)``:
    - 2 bytes  → :class:`ShipDesignCount`
    - 18 bytes → :class:`ShipDesign`

    Args:
        data: Raw decrypted block payload (2 or 18 bytes).

    Returns:
        A :class:`ShipDesignCount` or :class:`ShipDesign` instance.

    Raises:
        ValueError: If ``data`` is not 2 or 18 bytes.
    """
    n = len(data)
    if n == _FMT_COUNT_SIZE:
        (count,) = struct.unpack(_FMT_COUNT, data)
        return ShipDesignCount(count=count)
    if n == _FMT_DESIGN_SIZE:
        (
            design_id,
            player_tag,
            cost_iron,
            cost_boron,
            cost_germ_pack,
            slots_a,
            slots_b,
            slots_c,
            tech_flags,
            padding,
        ) = struct.unpack(_FMT_DESIGN, data)
        return ShipDesign(
            design_id=design_id,
            player_tag=player_tag,
            cost_iron=cost_iron,
            cost_boron=cost_boron,
            cost_germ_pack=cost_germ_pack,
            slots_a=slots_a,
            slots_b=slots_b,
            slots_c=slots_c,
            tech_flags=tech_flags,
            padding=padding,
        )
    raise ValueError(f"Type 43 block must be 2 or 18 bytes, got {n}")


def decode_ship_designs(
    blocks: list,
) -> list[ShipDesignCount | ShipDesign]:
    """Decode all Type 43 blocks from a block list.

    Args:
        blocks: Iterable of :class:`~stars_web.block_reader.Block` objects.
            Non-Type-43 blocks are silently skipped.

    Returns:
        List of decoded :class:`ShipDesignCount` and :class:`ShipDesign`
        objects in file order.
    """
    results: list[ShipDesignCount | ShipDesign] = []
    for blk in blocks:
        if blk.type_id == 43:
            results.append(decode_ship_design_block(blk.data))
    return results
