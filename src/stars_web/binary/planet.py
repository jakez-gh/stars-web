"""Stars! planet block binary parser/encoder.

Handles Type 13 (full planet detail) and Type 14 (partial/scanned planet) blocks.

Type 13 appears in .m# files for planets owned by the player — full detail with
population, minerals, installations, and starbases.

Type 14 appears in .m# files for planets the player has scanned — partial data
including mineral concentrations and hab values, but no installations.

Block format (variable length, flag-driven):
  Fixed header (4 bytes):
    byte 0:   planet_number[7:0]
    byte 1:   planet_number[10:8] (bits 0-2) | owner[4:0] (bits 3-7)
    bytes 2-3: flags (uint16 LE)

  Flag bits:
    bit 0:  NOT remote mining (inverted — 0 means remote mining active)
    bit 1:  has environment info (always set for owned planets)
    bit 2:  is in use (has population or is colonized)
    bit 7:  is homeworld
    bit 8:  has additional env data (used in Type 14 to trigger env section)
    bit 9:  has starbase
    bit 10: is terraformed (additional 3-byte original hab values follow env)
    bit 11: has installations (mines/factories/defenses)
    bit 12: has artifact
    bit 13: has surface minerals
    bit 14: has route/destination

  The owner value 31 (0x1F) means unowned.

  Optional sections (in order, based on flags):

    Environment section (Type 13: if bit 1 set; Type 14: always present):
      1 byte:  pre_env_byte
               frac_len = ((byte>>4)&3) + ((byte>>2)&3) + (byte&3)
      N bytes: fractional mineral concentration data (frac_len bytes, ignored)
      6 bytes: ironium_conc, boranium_conc, germanium_conc,
               gravity, temperature, radiation
      [if terraformed] 3 bytes: original gravity, temp, rad
      [if owned]       2 bytes: estimates (ignored)

    Surface minerals section (if bit 13 set):
      1 byte:  length code
               bits 0-1: ironium code
               bits 2-3: boranium code
               bits 4-5: germanium code
               bits 6-7: population code
               Code values: 0=0 bytes (value is 0), 1=1 byte, 2=2 bytes, 3=4 bytes
      N bytes: ironium (0/1/2/4 bytes, unsigned LE)
      N bytes: boranium
      N bytes: germanium
      N bytes: population (in hundreds — multiply by 100 for actual count)

    Installations section (if bit 11 set):
      1 byte:  excess_population
      1 byte:  mines_low (lower 8 bits of mine count)
      1 byte:  packed: mines_high[3:0] | factories_low[3:0]
      1 byte:  factories_high (upper 8 bits shifted by 4)
      1 byte:  defenses
      3 bytes: scanner/unknown (ignored)

      mines     = mines_low | ((packed & 0x0F) << 8)
      factories = ((packed & 0xF0) >> 4) | (factories_high << 4)

    Starbase section (if bit 9 set):
      4 bytes: starbase_data (ignored, reserved)

References:
  - file-format-discovery.md (local)
  - stars-4x/starsapi-python by raptor (2014) — reference implementation

Note from file-format-discovery.md, section 9:
  The frac_len formula does NOT include a +1 offset. Both reference Java and
  Python implementations are WRONG on this point. The correct formula is:
    frac_len = ((byte>>4)&3) + ((byte>>2)&3) + (byte&3)
  without the leading +1.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

# Block type IDs
BLOCK_TYPE_PLANET_FULL = 13
BLOCK_TYPE_PLANET_PARTIAL = 14

# Owner sentinel: 31 (0x1F) means unowned
OWNER_UNOWNED = 31

# Flag bit masks
_FLAG_HAS_ENV = 0x0002
_FLAG_IN_USE = 0x0004
_FLAG_HOMEWORLD = 0x0080
_FLAG_HAS_ENV2 = 0x0100  # triggers env section in Type 14 blocks
_FLAG_HAS_STARBASE = 0x0200
_FLAG_TERRAFORMED = 0x0400
_FLAG_HAS_INSTALLATIONS = 0x0800
_FLAG_HAS_SURFACE_MINERALS = 0x2000
_FLAG_HAS_ROUTE = 0x4000

# Variable-length mineral code → byte count
_CODE_TO_BYTES = {0: 0, 1: 1, 2: 2, 3: 4}


@dataclass
class PlanetDetail:
    """Parsed planet detail from a Type 13 or Type 14 block.

    Attributes:
        planet_number: Zero-based planet index in the universe.
        owner:         Player index (0-based) or OWNER_UNOWNED (31) if unowned.
        flags:         Raw 16-bit flag word from block header.
        is_full:       True for Type 13 (own planet), False for Type 14 (scanned).

        is_homeworld:  True if this is the player's homeworld.
        has_starbase:  True if a starbase orbits this planet.
        is_terraformed: True if planet hab has been terraform-modified.
        has_installations: True if mines/factories/defenses data is present.
        has_surface_minerals: True if surface mineral amounts are present.
        in_use:        True if the planet is occupied/colonized.

        ironium_conc:  Ironium mineral concentration (0-100).
        boranium_conc: Boranium mineral concentration.
        germanium_conc: Germanium mineral concentration.
        gravity:       Gravity hab value (raw encoded, 0-255).
        temperature:   Temperature hab value.
        radiation:     Radiation hab value.

        ironium:       Surface ironium in kT.
        boranium:      Surface boranium in kT.
        germanium:     Surface germanium in kT.
        population:    Population (colonists, actual count = stored * 100).

        excess_population: Overflow colonist count (for transports).
        mines:         Operating mine count.
        factories:     Operating factory count.
        defenses:      Defense installations count.
    """

    planet_number: int
    owner: int
    flags: int
    is_full: bool = True

    is_homeworld: bool = False
    has_starbase: bool = False
    is_terraformed: bool = False
    has_installations: bool = False
    has_surface_minerals: bool = False
    in_use: bool = False

    ironium_conc: int = 0
    boranium_conc: int = 0
    germanium_conc: int = 0
    gravity: int = 0
    temperature: int = 0
    radiation: int = 0

    ironium: int = 0
    boranium: int = 0
    germanium: int = 0
    population: int = 0

    excess_population: int = 0
    mines: int = 0
    factories: int = 0
    defenses: int = 0


def decode_planet(data: bytes, block_type: int = BLOCK_TYPE_PLANET_FULL) -> PlanetDetail:
    """Parse a single planet block (Type 13 or 14) into a PlanetDetail.

    Args:
        data:       Raw block payload bytes (excluding the 2-byte block header).
        block_type: BLOCK_TYPE_PLANET_FULL (13) or BLOCK_TYPE_PLANET_PARTIAL (14).

    Returns:
        PlanetDetail with all available fields populated.

    Raises:
        ValueError: If data is too short for the fixed header or the flag-driven
                    sections overflow the block.
    """
    if len(data) < 4:
        raise ValueError(f"Planet block too short: {len(data)} bytes (need ≥4)")

    # ── Fixed header ──────────────────────────────────────────────────────────
    planet_number = data[0] | ((data[1] & 0x07) << 8)
    owner = (data[1] >> 3) & 0x1F
    flags = struct.unpack_from("<H", data, 2)[0]

    is_full = block_type == BLOCK_TYPE_PLANET_FULL
    detail = PlanetDetail(
        planet_number=planet_number,
        owner=owner,
        flags=flags,
        is_full=is_full,
        is_homeworld=bool(flags & _FLAG_HOMEWORLD),
        has_starbase=bool(flags & _FLAG_HAS_STARBASE),
        is_terraformed=bool(flags & _FLAG_TERRAFORMED),
        has_installations=bool(flags & _FLAG_HAS_INSTALLATIONS),
        has_surface_minerals=bool(flags & _FLAG_HAS_SURFACE_MINERALS),
        in_use=bool(flags & _FLAG_IN_USE),
    )

    offset = 4

    # ── Environment section ───────────────────────────────────────────────────
    # Present when:
    #   Type 13 (full):    bit 1 (_FLAG_HAS_ENV) is set
    #   Type 14 (partial): always (unconditionally — that's the purpose of the block)
    has_env = bool(flags & _FLAG_HAS_ENV) if is_full else True

    if has_env and offset < len(data):
        pre_env = data[offset]
        offset += 1
        frac_len = ((pre_env >> 4) & 3) + ((pre_env >> 2) & 3) + (pre_env & 3)
        # Skip fractional mineral concentration bytes
        offset += frac_len

        if offset + 6 <= len(data):
            detail.ironium_conc = data[offset]
            detail.boranium_conc = data[offset + 1]
            detail.germanium_conc = data[offset + 2]
            detail.gravity = data[offset + 3]
            detail.temperature = data[offset + 4]
            detail.radiation = data[offset + 5]
            offset += 6

        # Terraformed planets have 3 extra bytes (original hab values, ignored)
        if detail.is_terraformed:
            offset += 3

        # Owned planets have 2 extra estimate bytes (ignored)
        if owner != OWNER_UNOWNED:
            offset += 2

    # ── Surface minerals section ──────────────────────────────────────────────
    if detail.has_surface_minerals and offset < len(data):
        lc = data[offset]
        offset += 1
        iron_code = lc & 0x03
        bor_code = (lc >> 2) & 0x03
        germ_code = (lc >> 4) & 0x03
        pop_code = (lc >> 6) & 0x03

        detail.ironium, offset = _read_var_int(data, offset, iron_code)
        detail.boranium, offset = _read_var_int(data, offset, bor_code)
        detail.germanium, offset = _read_var_int(data, offset, germ_code)
        pop_raw, offset = _read_var_int(data, offset, pop_code)
        detail.population = pop_raw * 100

    # ── Installations section ─────────────────────────────────────────────────
    if detail.has_installations and offset + 8 <= len(data):
        detail.excess_population = data[offset]
        mines_low = data[offset + 1]
        packed = data[offset + 2]
        factories_high = data[offset + 3]
        detail.defenses = data[offset + 4]
        # mines_high in packed bits 0-3, factories_low in bits 4-7
        mines_high = packed & 0x0F
        factories_low = (packed & 0xF0) >> 4
        detail.mines = mines_low | (mines_high << 8)
        detail.factories = factories_low | (factories_high << 4)
        offset += 8  # 5 fields + 3 padding/scanner bytes

    # Starbase section: 4 bytes if bit 9 set (ignored, to be extended later)
    # We just advance past them to allow future parsing.

    return detail


def decode_planets(blocks: list[tuple[int, bytes]]) -> list[PlanetDetail]:
    """Decode a list of raw planet block payloads.

    Args:
        blocks: List of (block_type, data) pairs.  block_type must be 13 or 14.

    Returns:
        List of PlanetDetail objects (one per block).

    Raises:
        ValueError: If any block_type is not 13 or 14.
    """
    results: list[PlanetDetail] = []
    for block_type, data in blocks:
        if block_type not in (BLOCK_TYPE_PLANET_FULL, BLOCK_TYPE_PLANET_PARTIAL):
            raise ValueError(f"Expected planet block type 13 or 14, got {block_type}")
        results.append(decode_planet(data, block_type))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _read_var_int(data: bytes, offset: int, code: int) -> tuple[int, int]:
    """Read a variable-length unsigned integer at *offset* using *code*.

    Args:
        data:   full block data bytes.
        offset: current byte position.
        code:   0 → value is 0 (0 bytes), 1 → uint8, 2 → uint16 LE, 3 → uint32 LE.

    Returns:
        (value, new_offset) tuple.
    """
    if code == 0:
        return 0, offset
    n = _CODE_TO_BYTES[code]
    if offset + n > len(data):
        return 0, offset
    if n == 1:
        value = data[offset]
    elif n == 2:
        value = struct.unpack_from("<H", data, offset)[0]
    else:
        value = struct.unpack_from("<I", data, offset)[0]
    return value, offset + n
