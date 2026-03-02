"""Tests for game state loader.

Verifies parsed game data against known values cross-referenced between
the Stars! fat client screenshots (turn 2, year 2402) and the actual
game data files (turn 1, year 2401).

Turn-2 screenshot values (for reference):
- Blossom: pop 28800, mines 10, factories 15, Iron 770, Bor 566, Germ 421
- Long Range Scout #2 at (1261, 1263)

Turn-1 data file values (tested here):
- Blossom: pop 26800, mines 10, factories 12, Iron 763, Bor 557, Germ 426
- Game: "Shooting Fish in a Barrel", Tiny, Normal density, 2 players, 32 planets
- Year 2401 (turn 1)
"""

import os
import pytest

from stars_web.game_state import (
    load_game,
    GameState,
    GameSettings,
)

TEST_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "autoplay", "tests", "data")
)


def _skip_if_no_data():
    if not os.path.exists(os.path.join(TEST_DATA_DIR, "Game.xy")):
        pytest.skip("Test data files not found")


class TestGameSettings:
    """Verify game settings match fat client Page 1 of 3 screenshot."""

    def test_game_name(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.settings.game_name == "Shooting Fish in a Barrel"

    def test_universe_size_tiny(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.settings.universe_size == 0
        assert state.settings.universe_size_label == "Tiny"

    def test_density_normal(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.settings.density == 1
        assert state.settings.density_label == "Normal"

    def test_player_count(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.settings.player_count == 2

    def test_planet_count(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.settings.planet_count == 32

    def test_starting_distance_moderate(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.settings.starting_distance == 1
        assert state.settings.starting_distance_label == "Moderate"

    def test_no_beginner_max_minerals(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.settings.beginner_max_minerals is False

    def test_no_slow_tech(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.settings.slow_tech is False

    def test_no_random_events_off(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.settings.no_random_events is False

    def test_no_galaxy_clumping(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.settings.galaxy_clumping is False


class TestFileHeader:
    """Verify file-level metadata."""

    def test_game_id(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.game_id == 0x387B400D

    def test_year_2401(self):
        """Data files are turn 1 (year 2401). Screenshots show turn 2."""
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.year == 2401
        assert state.turn == 1

    def test_version(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.version.startswith("2.83")

    def test_player_index(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert state.player_index == 0  # Player 1 is index 0


class TestPlanetPositions:
    """Verify all 32 planet positions and names from the star map."""

    def test_32_planets(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert len(state.planets) == 32

    def test_blossom_name_and_position(self):
        """Blossom is at (1254, 1200) per fat client screenshot."""
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        blossom = next(p for p in state.planets if p.name == "Blossom")
        assert blossom.x == 1254
        assert blossom.y == 1200

    def test_all_planet_names_are_valid(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        for planet in state.planets:
            assert planet.name != ""
            assert not planet.name.startswith("Unknown")

    def test_planet_x_coords_in_range(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        for planet in state.planets:
            assert 1000 <= planet.x <= 2000, f"{planet.name}: x={planet.x}"

    def test_planet_y_coords_in_range(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        for planet in state.planets:
            assert 0 <= planet.y <= 4095, f"{planet.name}: y={planet.y}"


class TestBlossomPlanetState:
    """Verify Blossom's detailed state from parsed game data.

    Turn-1 values (from hex dump of type-13 block, 37 bytes):
    - Population: 26,800 (raw=268, ×100)
    - Mines: 10, Factories: 12, Defenses: 10
    - Surface minerals: Ironium 763, Boranium 557, Germanium 426
    - Min concentrations: Ironium 71, Boranium 89, Germanium 71
    - Has Starbase, Is Homeworld

    Turn-2 screenshot values differ due to growth/mining/building.
    """

    def test_blossom_owner(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        blossom = next(p for p in state.planets if p.name == "Blossom")
        assert blossom.owner == 0  # Player 1 owns it

    def test_blossom_population(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        blossom = next(p for p in state.planets if p.name == "Blossom")
        assert blossom.population == 26800

    def test_blossom_mines(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        blossom = next(p for p in state.planets if p.name == "Blossom")
        assert blossom.mines == 10

    def test_blossom_factories(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        blossom = next(p for p in state.planets if p.name == "Blossom")
        assert blossom.factories == 12

    def test_blossom_ironium(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        blossom = next(p for p in state.planets if p.name == "Blossom")
        assert blossom.ironium == 763

    def test_blossom_boranium(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        blossom = next(p for p in state.planets if p.name == "Blossom")
        assert blossom.boranium == 557

    def test_blossom_germanium(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        blossom = next(p for p in state.planets if p.name == "Blossom")
        assert blossom.germanium == 426

    def test_blossom_has_starbase(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        blossom = next(p for p in state.planets if p.name == "Blossom")
        assert blossom.has_starbase is True

    def test_blossom_is_homeworld(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        blossom = next(p for p in state.planets if p.name == "Blossom")
        assert blossom.is_homeworld is True

    def test_blossom_defenses(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        blossom = next(p for p in state.planets if p.name == "Blossom")
        assert blossom.defenses == 10

    def test_blossom_mineral_concentrations(self):
        """Min Conc from hex dump: iron=71, bor=89, germ=71."""
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        blossom = next(p for p in state.planets if p.name == "Blossom")
        assert blossom.has_environment_info is True
        assert blossom.ironium_conc == 71
        assert blossom.boranium_conc == 89
        assert blossom.germanium_conc == 71


class TestFleets:
    """Verify fleet data from fat client screenshot.

    Long Range Scout #2 visible at (1261, 1263).
    Multiple fleets visible in orbit & in transit.
    """

    def test_has_fleets(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert len(state.fleets) > 0

    def test_fleets_owned_by_player(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        for fleet in state.fleets:
            assert fleet.owner == 0  # All visible fleets belong to player 1

    def test_scout_at_expected_position(self):
        """Fleet 1 (Long Range Scout #2) is in transit during turn 1.

        Turn-1 position: (1241, 1233).
        Turn-2 position per screenshot: (1261, 1263).
        """
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        scout = next((f for f in state.fleets if f.x == 1241 and f.y == 1233), None)
        assert scout is not None, (
            f"No fleet at (1241, 1233). Fleets: "
            f"{[(f.fleet_id, f.x, f.y) for f in state.fleets]}"
        )

    def test_fleets_have_valid_positions(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        for fleet in state.fleets:
            assert 500 <= fleet.x <= 3000, f"Fleet {fleet.fleet_id}: x={fleet.x}"
            assert 500 <= fleet.y <= 3000, f"Fleet {fleet.fleet_id}: y={fleet.y}"

    def test_each_fleet_has_ships(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        for fleet in state.fleets:
            assert fleet.ship_count >= 1, f"Fleet {fleet.fleet_id}: no ships"


class TestLoadGameAPI:
    """Verify the load_game API contract."""

    def test_auto_detect_player(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR)
        assert state.player_index == 0

    def test_load_player_2(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=2)
        assert state.player_index == 1

    def test_missing_directory_raises(self):
        with pytest.raises(FileNotFoundError):
            load_game("/nonexistent/path")

    def test_state_has_all_fields(self):
        _skip_if_no_data()
        state = load_game(TEST_DATA_DIR, player=1)
        assert isinstance(state, GameState)
        assert isinstance(state.settings, GameSettings)
        assert isinstance(state.planets, list)
        assert isinstance(state.fleets, list)
        assert state.game_id != 0
        assert state.year >= 2400
