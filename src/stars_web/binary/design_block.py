"""Binary decoder for Stars! Type 26 (ShipDesign) blocks.

Type 26 blocks carry ship and starbase design records, parsed when reading a
player's `.m#` file.  Two variants exist in the same block type:

**Full design (own player, ``byte0 & 0x04`` is set)**
    Contains full structural information including armor, slot layout,
    build history, and the Stars!-encoded design name.

    Offset  Size  Name             Notes
    ------  ----  ----             -----
    0       1     flags            0x07 = full, 0x03 = partial
    1       1     design_byte1     (design_number << 2) | 0x01; bit 6 = is_starbase
    2       1     hull_id          0-31 = ships, 32-36 = starbases
    3       1     pic              Hull picture index
    4       2     armor            uint16 LE
    6       1     slot_count       Number of component slots
    7       2     turn_designed    Turn the design was first created (uint16 LE)
    9       4     total_built      Cumulative ships built (uint32 LE)
    13      4     total_remaining  Ships still in service (uint32 LE)
    17+     4*N   slots            N × 4-byte slot records (see DesignSlot)
    17+4N+  var   name             Stars!-encoded design name

**Partial design (enemy/ally sighting, ``byte0 & 0x04`` is NOT set)**
    Only carries enough to identify the design — hull type, estimated mass,
    and the design name (if known).

    Offset  Size  Name             Notes
    ------  ----  ----             -----
    0       1     flags            0x03 (partial)
    1       1     design_byte1     (design_number << 2) | 0x01; bit 6 = is_starbase
    2       1     hull_id
    3       1     pic
    4       2     mass             Estimated hull mass (uint16 LE)
    6+      var   name             Stars!-encoded design name

**Slot record (4 bytes each)**
    Offset  Size  Name      Notes
    ------  ----  ----      -----
    0       2     category  Component category bitfield (uint16 LE)
    2       1     item_id   Item index within category
    3       1     count     Number of components in this slot
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from stars_web.stars_string import decode_stars_string

BLOCK_TYPE_DESIGN = 26
_FLAG_FULL = 0x04  # byte0 bit 2 → full design vs partial


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DesignSlot:
    """A single component slot in a :class:`FullDesign`.

    Attributes:
        category: Component category bitfield (uint16).
        item_id:  Item index within the category.
        count:    Number of components installed.
    """

    category: int
    item_id: int
    count: int

    def __str__(self) -> str:
        return f"Slot(cat={self.category:#06x}, item={self.item_id}, count={self.count})"


@dataclass(frozen=True)
class PartialDesign:
    """Type 26 partial design — enemy/ally ship sighting.

    Only the hull type, estimated mass, and name are available.

    Attributes:
        design_number: Slot index for this design (0-15).
        is_starbase:   True if this design is a starbase.
        hull_id:       Hull type index (0-36).
        pic:           Hull picture index.
        mass:          Estimated mass in kT.
        name:          Design name (empty if not yet known).
        raw:           Full raw block bytes for debugging.
    """

    design_number: int
    is_starbase: bool
    hull_id: int
    pic: int
    mass: int
    name: str
    raw: bytes = field(hash=False, compare=False)

    def __str__(self) -> str:
        sb = "/SB" if self.is_starbase else ""
        return (
            f"PartialDesign(#{self.design_number}{sb}, "
            f"hull={self.hull_id}, mass={self.mass}kT, name={self.name!r})"
        )


@dataclass(frozen=True)
class FullDesign:
    """Type 26 full design — own player's ship or starbase design.

    Attributes:
        design_number:   Slot index for this design (0-15).
        is_starbase:     True if this design is a starbase.
        hull_id:         Hull type index (0-36).
        pic:             Hull picture index.
        armor:           Total armor (kDP).
        slot_count:      Number of component slots.
        turn_designed:   Turn the design was first created.
        total_built:     Cumulative ships built from this design.
        total_remaining: Ships from this design still in service.
        slots:           Ordered tuple of :class:`DesignSlot` records.
        name:            Design name.
        raw:             Full raw block bytes for debugging.
    """

    design_number: int
    is_starbase: bool
    hull_id: int
    pic: int
    armor: int
    slot_count: int
    turn_designed: int
    total_built: int
    total_remaining: int
    slots: tuple[DesignSlot, ...]
    name: str
    raw: bytes = field(hash=False, compare=False)

    def __str__(self) -> str:
        sb = "/SB" if self.is_starbase else ""
        return (
            f"FullDesign(#{self.design_number}{sb}, "
            f"hull={self.hull_id}, armor={self.armor}kDP, "
            f"slots={self.slot_count}, built={self.total_built}, "
            f"name={self.name!r})"
        )


# --------------------------------------------------------------------------- #
# Decoders
# --------------------------------------------------------------------------- #


def decode_design_block(data: bytes) -> PartialDesign | FullDesign:
    """Decode a single Type 26 block.

    Dispatches based on ``byte0 & 0x04``:
    - Set → :class:`FullDesign` (own player's complete design record)
    - Clear → :class:`PartialDesign` (enemy/ally sighting with limited data)

    Args:
        data: Raw decrypted block payload.

    Returns:
        :class:`PartialDesign` or :class:`FullDesign`.

    Raises:
        ValueError: If ``data`` is too short.
    """
    n = len(data)
    if n < 4:
        raise ValueError(f"Type 26 block too short: expected >= 4 bytes, got {n}")

    byte0 = data[0]
    byte1 = data[1]
    hull_id = data[2]
    pic = data[3]

    is_full = bool(byte0 & _FLAG_FULL)
    design_number = (byte1 >> 2) & 0x0F
    is_starbase = bool(byte1 & 0x40)

    raw = bytes(data)

    if is_full:
        if n < 17:
            raise ValueError(
                f"Full design block too short: expected >= 17 bytes, got {n}"
            )
        armor = struct.unpack_from("<H", data, 4)[0]
        slot_count = data[6]
        turn_designed = struct.unpack_from("<H", data, 7)[0]
        total_built = struct.unpack_from("<I", data, 9)[0]
        total_remaining = struct.unpack_from("<I", data, 13)[0]

        slots: list[DesignSlot] = []
        offset = 17
        for _ in range(slot_count):
            if offset + 4 > n:
                break
            cat = struct.unpack_from("<H", data, offset)[0]
            item_id = data[offset + 2]
            count = data[offset + 3]
            slots.append(DesignSlot(category=cat, item_id=item_id, count=count))
            offset += 4

        if offset < n:
            name, _ = decode_stars_string(data, offset)
        else:
            name = ""

        return FullDesign(
            design_number=design_number,
            is_starbase=is_starbase,
            hull_id=hull_id,
            pic=pic,
            armor=armor,
            slot_count=slot_count,
            turn_designed=turn_designed,
            total_built=total_built,
            total_remaining=total_remaining,
            slots=tuple(slots),
            name=name,
            raw=raw,
        )

    # Partial design
    if n < 6:
        raise ValueError(
            f"Partial design block too short: expected >= 6 bytes, got {n}"
        )
    mass = struct.unpack_from("<H", data, 4)[0]
    name_str = ""
    if n > 6:
        name_str, _ = decode_stars_string(data, 6)

    return PartialDesign(
        design_number=design_number,
        is_starbase=is_starbase,
        hull_id=hull_id,
        pic=pic,
        mass=mass,
        name=name_str,
        raw=raw,
    )


def decode_designs(blocks: list) -> list[PartialDesign | FullDesign]:
    """Decode all Type 26 blocks from a block list.

    Args:
        blocks: Iterable of :class:`~stars_web.block_reader.Block` objects.
            Non-Type-26 blocks are silently skipped.

    Returns:
        List of :class:`PartialDesign` and :class:`FullDesign` in file order.
    """
    results: list[PartialDesign | FullDesign] = []
    for blk in blocks:
        if blk.type_id == BLOCK_TYPE_DESIGN:
            results.append(decode_design_block(blk.data))
    return results
