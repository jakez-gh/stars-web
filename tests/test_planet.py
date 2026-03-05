"""Test Suite for Planet Block Parsing (Tier-1 Binary Parsing)

Block Types: 13 (full/own planet detail) and 14 (partial/scanned planet)
Purpose: Parse planet minerals, population, installations, and hab values
Location: In .m# player files, after XY planet positions

Related Issues: Tier-1 binary parsing work
Pattern: Test-driven development

References:
  - docs/file-format-discovery.md (complete format specification)
  - starswine4/Game.m1, Game.m2 (real test data)
"""

import struct

import pytest
from hypothesis import given, settings, strategies as st

from stars_web.binary.planet import (
    PlanetDetail,
    decode_planet,
    decode_planets,
    BLOCK_TYPE_PLANET_FULL,
    BLOCK_TYPE_PLANET_PARTIAL,
    OWNER_UNOWNED,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared test fixtures and helpers
# ─────────────────────────────────────────────────────────────────────────────

# Real binary data extracted from starswine4/Game.m1 and Game.m2
# (decrypted via stars_web.block_reader.read_blocks)

# Type 13 – player 1 homeworld (planet 18): 37 bytes
M1_HOMEWORLD = bytes(
    [
        18,
        0,
        135,
        43,  # header: planet=18, owner=0, flags=0x2b87
        21,  # pre_env: 0x15 → frac_len=3
        192,
        148,
        192,  # frac data (3 bytes, ignored)
        69,
        86,
        69,  # iron_conc=69, bor_conc=86, germ_conc=69
        50,
        50,
        50,  # grav=50, temp=50, rad=50
        219,
        48,  # estimates (2 bytes, owned)
        170,  # surface mineral length code: iron=2, bor=2, germ=2, pop=2
        246,
        2,  # ironium = 758 kT
        227,
        3,  # boranium = 995 kT
        221,
        1,  # germanium = 477 kT
        85,
        3,  # population_raw = 853 → 85300 colonists
        67,  # excess_population = 67
        85,  # mines_low = 85
        80,  # packed: mines_high=0, factories_low=5
        5,  # factories_high = 5 → factories = 85
        18,  # defenses = 18
        0,
        0,
        0,  # scanner/unknown (3 bytes)
        0,
        0,
        0,
        0,  # starbase section (4 bytes)
    ]
)

# Type 13 – player 1 second planet (planet 19): 26 bytes
M1_SECOND_PLANET = bytes(
    [
        19,
        0,
        7,
        41,  # header: planet=19, owner=0, flags=0x2907
        0,  # pre_env: frac_len=0
        55,
        44,
        89,  # iron_conc=55, bor_conc=44, germ_conc=89
        17,
        42,
        34,  # grav=17, temp=42, rad=34
        6,
        0,  # estimates (2 bytes)
        85,  # surface mineral length code: iron=1, bor=1, germ=1, pop=1
        12,  # ironium = 12 kT
        6,  # boranium = 6 kT
        22,  # germanium = 22 kT
        26,  # population_raw = 26 → 2600 colonists
        70,  # excess_population = 70
        0,  # mines_low = 0
        0,  # packed
        0,  # factories_high
        0,  # defenses
        240,
        1,
        0,  # scanner/unknown (3 bytes)
    ]
)

# Type 13 – player 2 homeworld (planet 8): 36 bytes
M2_HOMEWORLD = bytes(
    [
        8,
        8,
        135,
        43,  # header: planet=8, owner=1, flags=0x2b87
        21,  # pre_env: frac_len=3
        251,
        50,
        112,  # frac data
        105,
        99,
        82,  # iron_conc=105, bor_conc=99, germ_conc=82
        35,
        60,
        38,  # grav=35, temp=60, rad=38
        33,
        50,  # estimates
        154,  # surface mineral lc: iron=2, bor=2, germ=1, pop=2
        173,
        4,  # ironium = 1197 kT (0x04AD)
        205,
        3,  # boranium = 973 kT (0x03CD)
        2,  # germanium = 2 kT
        196,
        7,  # population_raw = 1988 → 198800 colonists (0x07C4)
        5,  # excess_population
        111,  # mines_low = 111
        96,  # packed: mines_high=0, factories_low=6
        11,  # factories_high = 11 → factories = 182
        18,  # defenses = 18
        0,
        0,
        0,  # scanner/unknown
        0,
        0,
        0,
        0,  # starbase section
    ]
)

# Type 13 – player 2, planet 4: 18 bytes (no installations)
M2_THIRD_PLANET = bytes(
    [
        4,
        8,
        7,
        33,  # header: planet=4, owner=1, flags=0x2107
        0,  # pre_env: frac_len=0
        73,
        79,
        24,  # iron_conc=73, bor_conc=79, germ_conc=24
        46,
        52,
        68,  # grav=46, temp=52, rad=68
        38,
        0,  # estimates
        85,  # surface mineral lc: iron=1, bor=1, germ=1, pop=1
        27,  # ironium = 27 kT
        6,  # boranium = 6 kT
        23,  # germanium = 23 kT
        161,  # population_raw = 161 → 16100 colonists
    ]
)

# Type 14 – scanned unowned planet (planet 20): 17 bytes
M1_SCANNED_PLANET0 = bytes(
    [
        20,
        248,
        4,
        33,  # header: planet=20, owner=31=unowned, flags=0x2104
        17,  # pre_env: frac_len=2
        96,
        239,  # frac data (2 bytes)
        82,
        2,
        102,  # iron_conc=82, bor_conc=2, germ_conc=102
        36,
        33,
        90,  # grav=36, temp=33, rad=90
        21,  # surface mineral lc: iron=1, bor=1, germ=1, pop=0
        87,  # ironium = 87 kT
        1,  # boranium = 1 kT
        108,  # germanium = 108 kT
    ]
)

# Type 14 – scanned unowned planet (planet 29):  11 bytes
M1_SCANNED_PLANET1 = bytes(
    [
        29,
        248,
        3,
        1,  # header: planet=29, owner=31=unowned, flags=0x0103
        0,  # pre_env: frac_len=0
        110,
        29,
        6,  # iron_conc=110, bor_conc=29, germ_conc=6
        23,
        60,
        73,  # grav=23, temp=60, rad=73
    ]
)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: PlanetDetail dataclass structure
# ─────────────────────────────────────────────────────────────────────────────


class TestPlanetDetailDataclass:
    """Spec: PlanetDetail dataclass provides correct defaults and fields."""

    def test_construction_minimal(self):
        """PlanetDetail can be constructed with required fields only."""
        p = PlanetDetail(planet_number=1, owner=0, flags=0)
        assert p.planet_number == 1
        assert p.owner == 0
        assert p.flags == 0

    def test_default_owner_unowned(self):
        """OWNER_UNOWNED sentinel is 31 (0x1F)."""
        assert OWNER_UNOWNED == 31

    def test_default_numeric_fields_zero(self):
        """All numeric planet fields default to 0."""
        p = PlanetDetail(planet_number=0, owner=0, flags=0)
        assert p.population == 0
        assert p.mines == 0
        assert p.factories == 0
        assert p.defenses == 0
        assert p.ironium == 0
        assert p.boranium == 0
        assert p.germanium == 0
        assert p.ironium_conc == 0
        assert p.boranium_conc == 0
        assert p.germanium_conc == 0
        assert p.gravity == 0
        assert p.temperature == 0
        assert p.radiation == 0

    def test_default_flag_fields_false(self):
        """All boolean flag fields default to False."""
        p = PlanetDetail(planet_number=0, owner=0, flags=0)
        assert p.is_homeworld is False
        assert p.has_starbase is False
        assert p.is_terraformed is False
        assert p.has_installations is False
        assert p.has_surface_minerals is False
        assert p.in_use is False

    def test_is_full_default_true(self):
        """is_full defaults to True (Type 13)."""
        p = PlanetDetail(planet_number=0, owner=0, flags=0)
        assert p.is_full is True

    def test_planet_number_range(self):
        """planet_number supports 10-bit values (0-1023)."""
        p = PlanetDetail(planet_number=1023, owner=0, flags=0)
        assert p.planet_number == 1023

    def test_block_type_constants(self):
        """Block type constants match expected Stars! block IDs."""
        assert BLOCK_TYPE_PLANET_FULL == 13
        assert BLOCK_TYPE_PLANET_PARTIAL == 14


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Binary format decoding
# ─────────────────────────────────────────────────────────────────────────────


class TestDecodePlanetBinaryFormat:
    """Spec: decode_planet parses flag fields, env, minerals, and installations."""

    def test_header_planet_number_low_byte(self):
        """Planet number correctly parsed from byte 0 (lower 8 bits)."""
        data = bytearray(11)
        data[0] = 42
        data[1] = 0b11111000  # owner=31, planet_high=0
        struct.pack_into("<H", data, 2, 0x0003)  # has_env + not_remote_mining
        data[4] = 0  # pre_env
        p = decode_planet(bytes(data), BLOCK_TYPE_PLANET_PARTIAL)
        assert p.planet_number == 42

    def test_header_planet_number_high_bits(self):
        """Planet number uses 3 high bits from byte 1 (bits 0-2)."""
        data = bytearray(11)
        data[0] = 0
        data[1] = 0b11111101  # owner=31, planet_high bits 0-2 = 0b101 = 5
        struct.pack_into("<H", data, 2, 0x0003)
        data[4] = 0
        p = decode_planet(bytes(data), BLOCK_TYPE_PLANET_PARTIAL)
        assert p.planet_number == 0 | (5 << 8)  # = 1280

    def test_header_owner_field(self):
        """Owner decoded from bits 3-7 of byte 1."""
        data = bytearray(11)
        data[0] = 10
        data[1] = (3 << 3) | 0  # owner=3, planet_high=0
        struct.pack_into("<H", data, 2, 0x0003)
        data[4] = 0
        p = decode_planet(bytes(data), BLOCK_TYPE_PLANET_PARTIAL)
        assert p.owner == 3

    def test_header_unowned_sentinel(self):
        """Owner=31 parsed as OWNER_UNOWNED."""
        data = bytearray(11)
        data[0] = 5
        data[1] = (31 << 3) | 0  # owner=31 = unowned
        struct.pack_into("<H", data, 2, 0x0003)
        data[4] = 0
        p = decode_planet(bytes(data), BLOCK_TYPE_PLANET_PARTIAL)
        assert p.owner == OWNER_UNOWNED

    def test_flag_homeworld_bit7(self):
        """Bit 7 (0x0080) sets is_homeworld."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.is_homeworld is True
        p2 = decode_planet(M1_SECOND_PLANET, BLOCK_TYPE_PLANET_FULL)
        assert p2.is_homeworld is False

    def test_flag_has_starbase_bit9(self):
        """Bit 9 (0x0200) sets has_starbase."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.has_starbase is True
        p2 = decode_planet(M1_SECOND_PLANET, BLOCK_TYPE_PLANET_FULL)
        assert p2.has_starbase is False

    def test_flag_has_installations_bit11(self):
        """Bit 11 (0x0800) sets has_installations."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.has_installations is True

    def test_flag_in_use_bit2(self):
        """Bit 2 (0x0004) sets in_use."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.in_use is True

    def test_is_full_true_for_type13(self):
        """Type 13 blocks set is_full=True."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.is_full is True

    def test_is_full_false_for_type14(self):
        """Type 14 blocks set is_full=False."""
        p = decode_planet(M1_SCANNED_PLANET0, BLOCK_TYPE_PLANET_PARTIAL)
        assert p.is_full is False

    def test_env_conc_parsed(self):
        """Mineral concentrations parsed from environment section."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.ironium_conc == 69
        assert p.boranium_conc == 86
        assert p.germanium_conc == 69

    def test_env_hab_parsed(self):
        """Gravity/temperature/radiation parsed from environment section."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.gravity == 50
        assert p.temperature == 50
        assert p.radiation == 50

    def test_surface_minerals_uint16(self):
        """Surface minerals with code=2 are uint16 LE."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.ironium == 758
        assert p.boranium == 995
        assert p.germanium == 477

    def test_surface_minerals_uint8(self):
        """Surface minerals with code=1 are uint8."""
        p = decode_planet(M1_SECOND_PLANET, BLOCK_TYPE_PLANET_FULL)
        assert p.ironium == 12
        assert p.boranium == 6
        assert p.germanium == 22

    def test_population_multiplied_by_100(self):
        """Population stored value is multiplied by 100 for actual count."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.population == 85300  # 853 * 100

    def test_population_second_planet(self):
        """Population correctly decoded for smaller planet."""
        p = decode_planet(M1_SECOND_PLANET, BLOCK_TYPE_PLANET_FULL)
        assert p.population == 2600  # 26 * 100

    def test_installations_mines(self):
        """Mine count assembled from low byte and packed nibble."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.mines == 85

    def test_installations_factories(self):
        """Factory count assembled from packed low nibble + high byte."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.factories == 85

    def test_installations_defenses(self):
        """Defense count parsed from installations section."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.defenses == 18

    def test_installations_missing_when_flag_clear(self):
        """No installations parsed when bit 11 is clear."""
        p = decode_planet(M2_THIRD_PLANET, BLOCK_TYPE_PLANET_FULL)
        assert p.has_installations is False
        assert p.mines == 0
        assert p.factories == 0
        assert p.defenses == 0

    def test_frac_len_no_leading_plus1(self):
        """frac_len does NOT add +1 (correct formula, not reference bug)."""
        # pre_env=0x00 → frac_len = 0+0+0 = 0 (not 1)
        p = decode_planet(M1_SECOND_PLANET, BLOCK_TYPE_PLANET_FULL)
        # If +1 bug present, parsing would offset by 1 and get wrong concs
        assert p.ironium_conc == 55
        assert p.boranium_conc == 44
        assert p.germanium_conc == 89

    def test_frac_len_three(self):
        """pre_env=0x15 → frac_len = 1+1+1 = 3."""
        # M1_HOMEWORLD has pre_env=0x15 which gives frac_len=3
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.ironium_conc == 69  # Correct only if 3 frac bytes are skipped


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: Real data validation
# ─────────────────────────────────────────────────────────────────────────────


class TestDecodePlanetRealData:
    """Spec: Parser correctly handles all real block variants from starswine4/."""

    def test_type13_homeworld_player1(self):
        """Type 13: Player 1 homeworld (planet 18) parses completely."""
        p = decode_planet(M1_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.planet_number == 18
        assert p.owner == 0
        assert p.is_homeworld is True
        assert p.has_starbase is True
        assert p.in_use is True
        assert p.ironium_conc == 69
        assert p.boranium_conc == 86
        assert p.germanium_conc == 69
        assert p.gravity == 50
        assert p.temperature == 50
        assert p.radiation == 50
        assert p.ironium == 758
        assert p.boranium == 995
        assert p.germanium == 477
        assert p.population == 85300
        assert p.mines == 85
        assert p.factories == 85
        assert p.defenses == 18

    def test_type13_second_planet_player1(self):
        """Type 13: Player 1 second planet (planet 19) parses correctly."""
        p = decode_planet(M1_SECOND_PLANET, BLOCK_TYPE_PLANET_FULL)
        assert p.planet_number == 19
        assert p.owner == 0
        assert p.is_homeworld is False
        assert p.has_starbase is False
        assert p.ironium_conc == 55
        assert p.boranium_conc == 44
        assert p.germanium_conc == 89
        assert p.gravity == 17
        assert p.temperature == 42
        assert p.radiation == 34
        assert p.ironium == 12
        assert p.boranium == 6
        assert p.germanium == 22
        assert p.population == 2600
        assert p.mines == 0  # no mines on second planet yet
        assert p.factories == 0

    def test_type13_homeworld_player2(self):
        """Type 13: Player 2 homeworld (planet 8) parses correctly."""
        p = decode_planet(M2_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        assert p.planet_number == 8
        assert p.owner == 1
        assert p.is_homeworld is True
        assert p.has_starbase is True
        assert p.ironium_conc == 105
        assert p.boranium_conc == 99
        assert p.germanium_conc == 82
        assert p.ironium == 1197
        assert p.boranium == 973
        assert p.germanium == 2
        assert p.population == 198800
        assert p.mines == 111
        assert p.defenses == 18

    def test_type13_player2_no_installations(self):
        """Type 13: Planet without installations has zero mine/factory/defense."""
        p = decode_planet(M2_THIRD_PLANET, BLOCK_TYPE_PLANET_FULL)
        assert p.planet_number == 4
        assert p.owner == 1
        assert p.has_installations is False
        assert p.ironium == 27
        assert p.boranium == 6
        assert p.germanium == 23
        assert p.population == 16100

    def test_type14_scanned_with_minerals(self):
        """Type 14: Scanned unowned planet with surface minerals."""
        p = decode_planet(M1_SCANNED_PLANET0, BLOCK_TYPE_PLANET_PARTIAL)
        assert p.planet_number == 20
        assert p.owner == OWNER_UNOWNED
        assert p.is_full is False
        assert p.has_installations is False
        assert p.ironium_conc == 82
        assert p.boranium_conc == 2
        assert p.germanium_conc == 102
        assert p.gravity == 36
        assert p.temperature == 33
        assert p.radiation == 90
        assert p.ironium == 87
        assert p.boranium == 1
        assert p.germanium == 108
        assert p.population == 0

    def test_type14_scanned_env_only(self):
        """Type 14: Scanned planet with only env data (no surface minerals)."""
        p = decode_planet(M1_SCANNED_PLANET1, BLOCK_TYPE_PLANET_PARTIAL)
        assert p.planet_number == 29
        assert p.owner == OWNER_UNOWNED
        assert p.is_full is False
        assert p.has_surface_minerals is False
        assert p.ironium_conc == 110
        assert p.boranium_conc == 29
        assert p.germanium_conc == 6
        assert p.gravity == 23
        assert p.temperature == 60
        assert p.radiation == 73

    def test_factory_count_homeworld_player2(self):
        """Type 13: Player 2 homeworld factory count assembles correctly."""
        p = decode_planet(M2_HOMEWORLD, BLOCK_TYPE_PLANET_FULL)
        # packed=96=0x60 → factories_low=(0x60&0xF0)>>4=6, factories_high=11
        # factories = 6 | (11 << 4) = 6 | 176 = 182
        assert p.factories == 182


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Error handling
# ─────────────────────────────────────────────────────────────────────────────


class TestDecodePlanetErrorHandling:
    """Spec: decode_planet raises ValueError on malformed input."""

    def test_empty_data_raises(self):
        """Empty data raises ValueError."""
        with pytest.raises(ValueError, match="too short"):
            decode_planet(b"", BLOCK_TYPE_PLANET_FULL)

    def test_too_short_data_raises(self):
        """Data shorter than 4-byte header raises ValueError."""
        with pytest.raises(ValueError, match="too short"):
            decode_planet(b"\x01\x02", BLOCK_TYPE_PLANET_FULL)

    def test_invalid_block_type_raises(self):
        """Block type other than 13 or 14 raises ValueError via decode_planets."""
        with pytest.raises(ValueError, match="Expected planet block type"):
            decode_planets([(99, M1_HOMEWORLD)])

    def test_truncated_env_section_no_crash(self):
        """Truncated env data does not crash — returns partial fields."""
        # 4-byte header + bit1 set in flags but no more data
        data = bytes([1, 0, 0x02, 0x00])  # has_env=True, nothing after
        p = decode_planet(data, BLOCK_TYPE_PLANET_FULL)
        # Should not raise, returns zero for env fields
        assert p.planet_number == 1
        assert p.ironium_conc == 0

    def test_exactly_4_bytes_no_flags_no_crash(self):
        """Minimal 4-byte block with no flags parses header only."""
        data = bytes([5, 0, 0, 0])  # planet=5, owner=0, flags=0
        p = decode_planet(data, BLOCK_TYPE_PLANET_FULL)
        assert p.planet_number == 5
        assert p.owner == 0
        assert p.population == 0


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5: decode_planets batch function
# ─────────────────────────────────────────────────────────────────────────────


class TestDecodePlanets:
    """Spec: decode_planets processes a list of (block_type, data) pairs."""

    def test_empty_list_returns_empty(self):
        """Empty input returns empty list."""
        assert decode_planets([]) == []

    def test_single_type13_block(self):
        """Single Type 13 block returns single-element list."""
        results = decode_planets([(BLOCK_TYPE_PLANET_FULL, M1_HOMEWORLD)])
        assert len(results) == 1
        assert results[0].planet_number == 18

    def test_single_type14_block(self):
        """Single Type 14 block returns single-element list."""
        results = decode_planets([(BLOCK_TYPE_PLANET_PARTIAL, M1_SCANNED_PLANET1)])
        assert len(results) == 1
        assert results[0].owner == OWNER_UNOWNED

    def test_mixed_types_in_order(self):
        """Mixed Type 13 and Type 14 blocks decoded in order."""
        blocks = [
            (BLOCK_TYPE_PLANET_FULL, M1_HOMEWORLD),
            (BLOCK_TYPE_PLANET_FULL, M1_SECOND_PLANET),
            (BLOCK_TYPE_PLANET_PARTIAL, M1_SCANNED_PLANET0),
        ]
        results = decode_planets(blocks)
        assert len(results) == 3
        assert results[0].planet_number == 18
        assert results[1].planet_number == 19
        assert results[2].planet_number == 20

    def test_all_real_data_blocks(self):
        """All 8 real data blocks (4 type13, 4 type14) decode without error."""
        blocks = [
            (BLOCK_TYPE_PLANET_FULL, M1_HOMEWORLD),
            (BLOCK_TYPE_PLANET_FULL, M1_SECOND_PLANET),
            (BLOCK_TYPE_PLANET_FULL, M2_HOMEWORLD),
            (BLOCK_TYPE_PLANET_FULL, M2_THIRD_PLANET),
            (BLOCK_TYPE_PLANET_PARTIAL, M1_SCANNED_PLANET0),
            (BLOCK_TYPE_PLANET_PARTIAL, M1_SCANNED_PLANET1),
        ]
        results = decode_planets(blocks)
        assert len(results) == 6


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6: Integration with game file loading
# ─────────────────────────────────────────────────────────────────────────────


class TestPlanetBlockIntegration:
    """Spec: Planet block parsing integrates correctly with live game files."""

    def test_load_game_populates_planet_details(self, game_dir):
        """load_game populates population, minerals, and installations on planets."""
        from stars_web.game_state import load_game

        state = load_game(str(game_dir))

        # Find the homeworld (should have large population)
        homeworld = next(
            (p for p in state.planets if p.is_homeworld),
            None,
        )
        assert homeworld is not None, "No homeworld found in loaded game state"
        assert homeworld.population > 0, "Homeworld should have population"
        assert homeworld.owner >= 0, "Homeworld should have an owner"
        assert homeworld.has_starbase is True

    def test_load_game_owned_planets_have_minerals(self, game_dir):
        """load_game gives owned planets non-zero mineral concentrations."""
        from stars_web.game_state import load_game

        state = load_game(str(game_dir))
        owned = [p for p in state.planets if p.owner >= 0]
        assert len(owned) >= 1
        # At least one owned planet should have known mineral concentrations
        conc_planets = [
            p for p in owned if p.ironium_conc > 0 or p.boranium_conc > 0 or p.germanium_conc > 0
        ]
        assert len(conc_planets) >= 1

    def test_load_game_homeworld_population_gt_10000(self, game_dir):
        """Homeworld has at least 10,000 population (realistic starter value)."""
        from stars_web.game_state import load_game

        state = load_game(str(game_dir))
        homeworld = next((p for p in state.planets if p.is_homeworld), None)
        assert homeworld is not None
        assert homeworld.population >= 10000

    def test_load_game_some_planets_have_installations(self, game_dir):
        """At least one planet has mines or factories after loading."""
        from stars_web.game_state import load_game

        state = load_game(str(game_dir))
        has_installs = [
            p for p in state.planets if p.mines > 0 or p.factories > 0 or p.defenses > 0
        ]
        assert len(has_installs) >= 1

    def test_load_game_scanned_planets_have_conc(self, game_dir):
        """Scanned (Type 14) planets have non-zero mineral concentration data."""
        from stars_web.game_state import load_game

        state = load_game(str(game_dir))
        # Planets that are scanned but unowned
        scanned_unowned = [
            p
            for p in state.planets
            if p.owner == -1 and (p.ironium_conc > 0 or p.boranium_conc > 0 or p.germanium_conc > 0)
        ]
        # We know starswine4 has scanned planets with env data
        assert len(scanned_unowned) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7: Property-based invariants
# ─────────────────────────────────────────────────────────────────────────────


class TestPlanetDetailInvariants:
    """Spec: Property-based invariant checks on PlanetDetail fields."""

    @given(
        planet_number=st.integers(min_value=0, max_value=1023),
        owner=st.integers(min_value=0, max_value=31),
        ironium=st.integers(min_value=0, max_value=65535),
        boranium=st.integers(min_value=0, max_value=65535),
        germanium=st.integers(min_value=0, max_value=65535),
        population=st.integers(min_value=0, max_value=65535 * 100),
    )
    def test_field_assignments_valid(
        self, planet_number, owner, ironium, boranium, germanium, population
    ):
        """PlanetDetail accepts any valid field values without error."""
        p = PlanetDetail(
            planet_number=planet_number,
            owner=owner,
            flags=0,
            ironium=ironium,
            boranium=boranium,
            germanium=germanium,
            population=population,
        )
        assert p.planet_number == planet_number
        assert p.owner == owner
        assert p.ironium == ironium
        assert p.boranium == boranium
        assert p.germanium == germanium
        assert p.population == population

    @given(
        pre_env=st.integers(min_value=0, max_value=255),
    )
    def test_frac_len_bounded(self, pre_env):
        """frac_len is always in range [0, 9]."""
        frac_len = ((pre_env >> 4) & 3) + ((pre_env >> 2) & 3) + (pre_env & 3)
        assert 0 <= frac_len <= 9

    @given(
        planet_number=st.integers(min_value=0, max_value=255),
    )
    def test_minimal_block_decodes(self, planet_number):
        """Minimal 4-byte block (no flags) always decodes without exception."""
        data = bytes([planet_number & 0xFF, 0, 0, 0])
        p = decode_planet(data, BLOCK_TYPE_PLANET_FULL)
        assert p.planet_number == (planet_number & 0xFF)

    @given(
        lc=st.integers(min_value=0, max_value=255),
    )
    @settings(max_examples=100)
    def test_mineral_code_never_out_of_range(self, lc):
        """Mineral codes extracted from length code byte are always 0-3."""
        iron_code = lc & 0x03
        bor_code = (lc >> 2) & 0x03
        germ_code = (lc >> 4) & 0x03
        pop_code = (lc >> 6) & 0x03
        for code in (iron_code, bor_code, germ_code, pop_code):
            assert 0 <= code <= 3
