"""Stars! game state loader.

Loads all game files (.xy, .m#, .h#, .hst) from a game directory
and assembles a unified GameState object with parsed planets, fleets,
game settings, and player info.
"""

import os
import struct
from dataclasses import dataclass, field

from stars_web.block_reader import read_blocks, Block
from stars_web.planet_names import get_planet_name
from stars_web.stars_string import decode_stars_string


# Universe size labels by ID
UNIVERSE_SIZES = {0: "Tiny", 1: "Small", 2: "Medium", 3: "Large", 4: "Huge"}

# Density labels by ID
DENSITY_LABELS = {0: "Sparse", 1: "Normal", 2: "Dense", 3: "Packed"}

# Starting distance labels by ID
STARTING_DISTANCES = {0: "Close", 1: "Moderate", 2: "Farther", 3: "Distant"}

# Hull names by ID (0-31 = ships, 32-36 = starbases)
HULL_NAMES = {
    0: "Small Freighter",
    1: "Medium Freighter",
    2: "Large Freighter",
    3: "Super Freighter",
    4: "Scout",
    5: "Frigate",
    6: "Destroyer",
    7: "Cruiser",
    8: "Battle Cruiser",
    9: "Battleship",
    10: "Dreadnought",
    11: "Privateer",
    12: "Rogue",
    13: "Galleon",
    14: "Mini Colony Ship",
    15: "Colony Ship",
    16: "Mini Bomber",
    17: "B-17 Bomber",
    18: "Stealth Bomber",
    19: "B-52 Bomber",
    20: "Midget Miner",
    21: "Mini Miner",
    22: "Miner",
    23: "Maxi Miner",
    24: "Ultra Miner",
    25: "Fuel Transport",
    26: "Super Fuel Xport",
    27: "Mini Mine Layer",
    28: "Super Mine Layer",
    29: "Nubian",
    30: "Mini Morph",
    31: "Meta Morph",
    32: "Orbital Fort",
    33: "Space Dock",
    34: "Space Station",
    35: "Ultra Station",
    36: "Death Star",
}

# Block type constant for ship/starbase designs
BLOCK_TYPE_DESIGN = 26


@dataclass
class Planet:
    """A planet on the star map."""

    planet_id: int
    name_id: int
    name: str
    x: int
    y: int
    owner: int = -1  # -1 = unowned, 0-15 = player index
    population: int = 0
    mines: int = 0
    factories: int = 0
    defenses: int = 0
    ironium: int = 0
    boranium: int = 0
    germanium: int = 0
    ironium_conc: int = 0
    boranium_conc: int = 0
    germanium_conc: int = 0
    gravity: int = 0
    temperature: int = 0
    radiation: int = 0
    has_starbase: bool = False
    is_homeworld: bool = False
    has_environment_info: bool = False
    has_surface_minerals: bool = False


@dataclass
class Fleet:
    """A fleet on the star map."""

    fleet_id: int
    owner: int
    x: int
    y: int
    ship_count: int = 0
    # Minimal for now — expand as we parse more fields


@dataclass
class ShipDesign:
    """A ship or starbase design.

    Full designs include armor, slots, and build stats.
    Partial designs (other players' ships) only have mass.
    """

    design_number: int
    is_starbase: bool
    hull_id: int
    hull_name: str
    name: str
    armor: int = 0
    mass: int = 0
    slot_count: int = 0
    slots: list[tuple[int, int, int]] = field(default_factory=list)
    is_full_design: bool = True
    turn_designed: int = 0
    total_built: int = 0
    total_remaining: int = 0


@dataclass
class GameSettings:
    """Parsed game settings from the planets block (type 7)."""

    game_name: str = ""
    universe_size: int = 0
    universe_size_label: str = ""
    density: int = 0
    density_label: str = ""
    player_count: int = 0
    planet_count: int = 0
    starting_distance: int = 0
    starting_distance_label: str = ""
    game_settings_bits: int = 0
    # Decoded setting flags
    beginner_max_minerals: bool = False
    slow_tech: bool = False
    accelerated_bbs: bool = False
    no_random_events: bool = False
    computer_alliances: bool = False
    public_scores: bool = False
    galaxy_clumping: bool = False


@dataclass
class GameState:
    """Complete game state assembled from all game files."""

    game_id: int = 0
    year: int = 2400
    turn: int = 0
    version: str = ""
    player_index: int = 0
    settings: GameSettings = field(default_factory=GameSettings)
    planets: list[Planet] = field(default_factory=list)
    fleets: list[Fleet] = field(default_factory=list)
    designs: list[ShipDesign] = field(default_factory=list)


def parse_design_block(block: Block) -> ShipDesign | None:
    """Parse a type-26 ship/starbase design block.

    Design block format (from starsapi DesignBlock.java):
      byte 0: flags — 0x07=full design, 0x03=partial
      byte 1: (designNumber << 2) | 0x01, bit 6=isStarbase
      byte 2: hullId (0-31 ships, 32-36 starbases)
      byte 3: pic

    Full design (flag bit 2 set):
      bytes 4-5:  armor (u16 LE)
      byte  6:    slotCount
      bytes 7-8:  turnDesigned (u16 LE)
      bytes 9-12: totalBuilt (u32 LE)
      bytes 13-16: totalRemaining (u32 LE)
      bytes 17+:  slots (4 bytes each: category u16 + itemId u8 + count u8)
      then:       Stars!-encoded name

    Partial design (other players' ships):
      bytes 4-5: mass (u16 LE)
      bytes 6+:  Stars!-encoded name
    """
    if block.type_id != BLOCK_TYPE_DESIGN:
        return None

    data = block.data
    byte0 = data[0]
    byte1 = data[1]
    hull_id = data[2]

    is_full_design = bool(byte0 & 0x04)
    design_number = (byte1 >> 2) & 0x0F
    is_starbase = bool(byte1 & 0x40)
    hull_name = HULL_NAMES.get(hull_id, f"Unknown Hull {hull_id}")

    if is_full_design:
        armor = struct.unpack_from("<H", data, 4)[0]
        slot_count = data[6]
        turn_designed = struct.unpack_from("<H", data, 7)[0]
        total_built = struct.unpack_from("<I", data, 9)[0]
        total_remaining = struct.unpack_from("<I", data, 13)[0]

        slots: list[tuple[int, int, int]] = []
        slot_offset = 17
        for _ in range(slot_count):
            cat = struct.unpack_from("<H", data, slot_offset)[0]
            item_id = data[slot_offset + 2]
            count = data[slot_offset + 3]
            slots.append((cat, item_id, count))
            slot_offset += 4

        name, _ = decode_stars_string(data, slot_offset)
        mass = 0
    else:
        mass = struct.unpack_from("<H", data, 4)[0]
        armor = 0
        slot_count = 0
        slots = []
        turn_designed = 0
        total_built = 0
        total_remaining = 0
        name, _ = decode_stars_string(data, 6)

    return ShipDesign(
        design_number=design_number,
        is_starbase=is_starbase,
        hull_id=hull_id,
        hull_name=hull_name,
        name=name,
        armor=armor,
        mass=mass,
        slot_count=slot_count,
        slots=slots,
        is_full_design=is_full_design,
        turn_designed=turn_designed,
        total_built=total_built,
        total_remaining=total_remaining,
    )


def _parse_planets_from_xy(blocks: list[Block]) -> tuple[list[Planet], GameSettings]:
    """Extract planet positions and game settings from .xy file blocks."""
    planets = []
    settings = GameSettings()

    for block in blocks:
        if block.type_id != 7:
            continue

        data = block.data

        # Game settings from the planets block header
        settings.universe_size = struct.unpack_from("<H", data, 4)[0]
        settings.universe_size_label = UNIVERSE_SIZES.get(
            settings.universe_size, f"Unknown ({settings.universe_size})"
        )
        settings.density = struct.unpack_from("<H", data, 6)[0]
        settings.density_label = DENSITY_LABELS.get(
            settings.density, f"Unknown ({settings.density})"
        )
        settings.player_count = struct.unpack_from("<H", data, 8)[0]
        settings.planet_count = struct.unpack_from("<H", data, 10)[0]
        settings.starting_distance = struct.unpack_from("<H", data, 12)[0]
        settings.starting_distance_label = STARTING_DISTANCES.get(
            settings.starting_distance, f"Unknown ({settings.starting_distance})"
        )
        settings.game_settings_bits = struct.unpack_from("<H", data, 16)[0]

        # Decode setting flags
        bits = settings.game_settings_bits
        settings.beginner_max_minerals = bool(bits & 0x01)
        settings.slow_tech = bool(bits & 0x02)
        settings.accelerated_bbs = bool(bits & 0x20)
        settings.no_random_events = bool(bits & 0x80)
        settings.computer_alliances = bool(bits & 0x10)
        settings.public_scores = bool(bits & 0x40)
        settings.galaxy_clumping = bool(bits & 0x100)

        # Game name at bytes 32-63
        game_name_raw = data[32:64]
        settings.game_name = game_name_raw.split(b"\x00")[0].decode("ascii", errors="replace")

        # Planet coordinates from extra_data
        x = 1000
        for i in range(settings.planet_count):
            planet_word = struct.unpack_from("<I", block.extra_data, i * 4)[0]
            name_id = planet_word >> 22
            y = (planet_word >> 10) & 0xFFF
            x_offset = planet_word & 0x3FF
            x = x + x_offset

            planets.append(
                Planet(
                    planet_id=i,
                    name_id=name_id,
                    name=get_planet_name(name_id),
                    x=x,
                    y=y,
                )
            )
        break  # Only one planets block per file

    return planets, settings


def _read_variable_length(data: bytes, offset: int, code: int) -> tuple[int, int]:
    """Read a variable-length integer based on 2-bit code.

    Code: 0=0 bytes (value 0), 1=1 byte, 2=2 bytes, 3=4 bytes.
    Returns (value, bytes_consumed).
    """
    if code == 0:
        return 0, 0
    elif code == 1:
        return data[offset], 1
    elif code == 2:
        return struct.unpack_from("<H", data, offset)[0], 2
    else:  # code == 3
        return struct.unpack_from("<I", data, offset)[0], 4


def _parse_planet_block(block: Block, planets_by_id: dict[int, Planet]) -> None:
    """Parse a type-13 or type-14 planet block and update planet state."""
    data = block.data
    if len(data) < 4:
        return

    # Fixed header: bytes 0-3
    planet_number = data[0] | ((data[1] & 0x07) << 8)
    owner = (data[1] >> 3) & 0x1F
    if owner == 31:
        owner = -1

    flags = struct.unpack_from("<H", data, 2)[0]
    is_homeworld = bool(flags & 0x80)
    is_in_use = bool(flags & 0x04)
    has_env_info = bool(flags & 0x02)
    bit_off_for_remote = bool(flags & 0x01)
    has_starbase = bool(flags & 0x0200)
    is_terraformed = bool(flags & 0x0400)
    has_installations = bool(flags & 0x0800)
    _has_artifact = bool(flags & 0x1000)
    has_surface_minerals = bool(flags & 0x2000)
    _has_route = bool(flags & 0x4000)

    planet = planets_by_id.get(planet_number)
    if planet is None:
        return

    planet.owner = owner
    planet.has_starbase = has_starbase
    planet.is_homeworld = is_homeworld

    idx = 4

    # Section 1: Environment info
    can_see_env = has_env_info or ((has_surface_minerals or is_in_use) and not bit_off_for_remote)
    if can_see_env and idx < len(data):
        # Pre-environment length byte encodes how many fractional
        # mineral concentration bytes follow. Each 2-bit field
        # contributes to the total. There is NO +1 offset —
        # proven by type-14 planet 17 (11 bytes total, pre_env=0x00
        # yields frac_len=0, giving exact fit: 4+1+0+6=11).
        pre_env_byte = data[idx]
        idx += 1
        frac_len = ((pre_env_byte >> 4) & 3) + ((pre_env_byte >> 2) & 3) + (pre_env_byte & 3)
        idx += frac_len  # Skip fractional mineral concentration bytes

        if idx + 6 <= len(data):
            planet.ironium_conc = data[idx]
            planet.boranium_conc = data[idx + 1]
            planet.germanium_conc = data[idx + 2]
            planet.gravity = data[idx + 3]
            planet.temperature = data[idx + 4]
            planet.radiation = data[idx + 5]
            planet.has_environment_info = True
            idx += 6

        if is_terraformed:
            idx += 3  # Skip original grav/temp/rad

        if owner >= 0 and idx + 2 <= len(data):
            idx += 2  # Skip estimates short

    # Section 2: Surface minerals
    if (has_surface_minerals or is_in_use) and idx < len(data):
        planet.has_surface_minerals = True
        length_byte = data[idx]
        idx += 1

        iron_code = length_byte & 0x03
        bor_code = (length_byte >> 2) & 0x03
        germ_code = (length_byte >> 4) & 0x03
        pop_code = (length_byte >> 6) & 0x03

        val, consumed = _read_variable_length(data, idx, iron_code)
        planet.ironium = val
        idx += consumed

        val, consumed = _read_variable_length(data, idx, bor_code)
        planet.boranium = val
        idx += consumed

        val, consumed = _read_variable_length(data, idx, germ_code)
        planet.germanium = val
        idx += consumed

        val, consumed = _read_variable_length(data, idx, pop_code)
        planet.population = val * 100  # Population stored in hundreds
        idx += consumed

    # Section 3: Installations
    if has_installations and idx + 8 <= len(data):
        # Skip excessPop byte
        idx += 1
        mines_low = data[idx]
        idx += 1
        packed = data[idx]
        idx += 1
        factories_mid = data[idx]
        idx += 1

        planet.mines = mines_low | ((packed & 0x0F) << 8)
        planet.factories = ((packed & 0xF0) >> 4) | (factories_mid << 4)
        planet.defenses = data[idx]
        idx += 4  # Skip defenses + unknownByte + scanner byte + padding


def _parse_fleet_block(block: Block) -> Fleet | None:
    """Parse a type-16 or type-17 fleet block."""
    data = block.data
    if len(data) < 14:
        return None

    fleet_number = data[0] | ((data[1] & 0x01) << 8)
    owner = (data[1] >> 1) & 0x7F
    _kind_byte = data[4]  # fleet type; will be used for fleet classification
    x = struct.unpack_from("<H", data, 8)[0]
    y = struct.unpack_from("<H", data, 10)[0]
    ship_types_mask = struct.unpack_from("<H", data, 12)[0]

    # Count total ships
    ship_count_two_bytes = (data[5] & 0x08) == 0
    ship_count = 0
    idx = 14
    for bit in range(16):
        if ship_types_mask & (1 << bit):
            if ship_count_two_bytes and idx + 2 <= len(data):
                count = struct.unpack_from("<H", data, idx)[0]
                idx += 2
            elif idx < len(data):
                count = data[idx]
                idx += 1
            else:
                count = 0
            ship_count += count

    return Fleet(
        fleet_id=fleet_number,
        owner=owner,
        x=x,
        y=y,
        ship_count=ship_count,
    )


def load_game(game_dir: str, player: int = 0) -> GameState:
    """Load a complete game state from a directory of Stars! files.

    Args:
        game_dir: Directory containing Game.xy, Game.m1, etc.
        player: Player number (1-based) to load. Default=0 means auto-detect.

    Returns:
        Assembled GameState.
    """
    state = GameState()

    # Find the game name prefix (e.g., "Game")
    xy_files = [f for f in os.listdir(game_dir) if f.lower().endswith(".xy")]
    if not xy_files:
        raise FileNotFoundError(f"No .xy file found in {game_dir}")
    game_prefix = xy_files[0].rsplit(".", 1)[0]

    # 1. Parse .xy file for planet positions and game settings
    xy_path = os.path.join(game_dir, f"{game_prefix}.xy")
    with open(xy_path, "rb") as f:
        xy_bytes = f.read()
    xy_blocks = read_blocks(xy_bytes)

    # Get file header info
    hdr = xy_blocks[0].file_header
    state.game_id = hdr.game_id
    state.version = f"{hdr.version_major}.{hdr.version_minor}.{hdr.version_increment}"

    # Parse planets and settings from XY
    state.planets, state.settings = _parse_planets_from_xy(xy_blocks)

    # Build planet lookup by ID
    planets_by_id = {p.planet_id: p for p in state.planets}

    # 2. Find player files (.m#)
    if player == 0:
        # Auto-detect: find first .m# file
        m_files = sorted(
            f
            for f in os.listdir(game_dir)
            if f.lower().startswith(game_prefix.lower() + ".m") and f[-1].isdigit()
        )
        if m_files:
            player = int(m_files[0].rsplit(".m", 1)[1])
        else:
            player = 1

    state.player_index = player - 1  # Convert to 0-based

    m_path = os.path.join(game_dir, f"{game_prefix}.m{player}")
    if os.path.exists(m_path):
        with open(m_path, "rb") as f:
            m_bytes = f.read()
        m_blocks = read_blocks(m_bytes)

        m_hdr = m_blocks[0].file_header
        state.turn = m_hdr.turn
        state.year = m_hdr.year

        for block in m_blocks:
            if block.type_id in (13, 14):
                _parse_planet_block(block, planets_by_id)
            elif block.type_id in (16, 17):
                fleet = _parse_fleet_block(block)
                if fleet is not None:
                    state.fleets.append(fleet)
            elif block.type_id == BLOCK_TYPE_DESIGN:
                design = parse_design_block(block)
                if design is not None:
                    state.designs.append(design)

    return state
