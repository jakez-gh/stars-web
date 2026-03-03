"""Tests for Stars! player/race data parsing (block type 6)."""

import pytest

from stars_web.game_state import (
    parse_player_block,
    PRT_NAMES,
    BLOCK_TYPE_PLAYER,
)
from stars_web.block_reader import Block


# ── PRT names ───────────────────────────────────────────────────────


class TestPrtNames:
    """Primary Racial Trait IDs should map to known abbreviations."""

    def test_he_is_0(self):
        assert PRT_NAMES[0] == "Hyper-Expansion"

    def test_joat_is_9(self):
        assert PRT_NAMES[9] == "Jack of All Trades"

    def test_ar_is_8(self):
        assert PRT_NAMES[8] == "Alternate Reality"

    def test_all_ten_prts_exist(self):
        assert len(PRT_NAMES) == 10


# ── Parse player blocks ────────────────────────────────────────────


class TestParsePlayerBlock:
    """Parse player/race blocks (type 6)."""

    def _encode_name(self, name):
        """Encode a test name using Stars! nibble encoding.

        Uses F-prefix (3-nibble raw ASCII) for each character for simplicity.
        """
        nibbles = []
        for ch in name:
            code = ord(ch)
            lo = code & 0x0F
            hi = (code >> 4) & 0x0F
            nibbles.extend([0xF, lo, hi])
        # Pad to even number of nibbles
        if len(nibbles) % 2:
            nibbles.append(0xF)
        byte_count = len(nibbles) // 2
        encoded = bytearray([byte_count])
        for i in range(0, len(nibbles), 2):
            encoded.append((nibbles[i] << 4) | nibbles[i + 1])
        return bytes(encoded)

    def _make_player_block(
        self,
        player_number=0,
        ship_designs=6,
        planets=5,
        fleets=6,
        starbase_designs=1,
        logo=1,
        full_data=True,
        prt=9,
        tech_levels=None,
        relations=None,
        name_singular="Human",
        name_plural="Humans",
    ):
        """Build a synthetic player block."""
        if tech_levels is None:
            tech_levels = [3, 3, 3, 3, 3, 3]
        if relations is None:
            relations = []

        data = bytearray()
        data.append(player_number)
        data.append(ship_designs)
        data.append(planets & 0xFF)
        data.append((planets >> 8) & 0x03)
        data.append(fleets & 0xFF)
        data.append(((starbase_designs & 0x0F) << 4) | ((fleets >> 8) & 0x03))
        flag_byte = (logo << 3) | 0x03
        if full_data:
            flag_byte |= 0x04
        data.append(flag_byte)
        data.append(1)  # byte7

        if full_data:
            # fullDataBytes: 0x68 = 104 bytes
            fb = bytearray(0x68)
            fb[18] = tech_levels[0]  # energy
            fb[19] = tech_levels[1]  # weapons
            fb[20] = tech_levels[2]  # propulsion
            fb[21] = tech_levels[3]  # construction
            fb[22] = tech_levels[4]  # electronics
            fb[23] = tech_levels[5]  # biotech
            fb[68] = prt
            data.extend(fb)
            # playerRelations
            data.append(len(relations))
            data.extend(relations)

        data.extend(self._encode_name(name_singular))
        data.extend(self._encode_name(name_plural))

        return Block(type_id=BLOCK_TYPE_PLAYER, size=len(data), data=bytes(data))

    def test_basic_player_block(self):
        block = self._make_player_block()
        player = parse_player_block(block)
        assert player is not None
        assert player.player_number == 0
        assert player.name_singular == "Human"
        assert player.name_plural == "Humans"

    def test_prt(self):
        block = self._make_player_block(prt=9)
        player = parse_player_block(block)
        assert player.prt == 9
        assert player.prt_name == "Jack of All Trades"

    def test_tech_levels(self):
        block = self._make_player_block(tech_levels=[5, 4, 3, 2, 1, 6])
        player = parse_player_block(block)
        assert player.tech_energy == 5
        assert player.tech_weapons == 4
        assert player.tech_propulsion == 3
        assert player.tech_construction == 2
        assert player.tech_electronics == 1
        assert player.tech_biotech == 6

    def test_fleet_and_planet_counts(self):
        block = self._make_player_block(planets=42, fleets=10, ship_designs=8)
        player = parse_player_block(block)
        assert player.planets == 42
        assert player.fleets == 10
        assert player.ship_designs == 8

    def test_relations(self):
        block = self._make_player_block(relations=[0, 2])
        player = parse_player_block(block)
        assert player.relations == [0, 2]

    def test_no_full_data(self):
        """Non-full data blocks (other players) have no tech/PRT."""
        block = self._make_player_block(full_data=False, player_number=1)
        player = parse_player_block(block)
        assert player.player_number == 1
        assert player.name_singular == "Human"
        assert player.prt == -1  # Unknown
        assert player.tech_energy == 0

    def test_wrong_block_type_returns_none(self):
        block = Block(type_id=13, size=10, data=b"\x00" * 10)
        assert parse_player_block(block) is None


# ── Integration: parse players from real game file ──────────────────


class TestParsePlayersFromFile:
    """Parse player blocks from real Stars! game files."""

    @pytest.fixture
    def m1_players(self):
        import os
        from stars_web.block_reader import read_blocks

        path = os.path.join("docs", "images", "original_fat_client_screenshots", "Game.m1")
        if not os.path.exists(path):
            pytest.skip("Game.m1 not found")
        data = open(path, "rb").read()
        blocks = read_blocks(data)
        return [parse_player_block(b) for b in blocks if b.type_id == BLOCK_TYPE_PLAYER]

    def test_at_least_one_player(self, m1_players):
        players = [p for p in m1_players if p is not None]
        assert len(players) >= 1

    def test_player_zero_is_humanoid(self, m1_players):
        players = [p for p in m1_players if p is not None]
        p0 = [p for p in players if p.player_number == 0]
        assert len(p0) == 1
        assert p0[0].name_singular == "Humanoid"
        assert p0[0].name_plural == "Humanoids"

    def test_player_zero_is_joat(self, m1_players):
        players = [p for p in m1_players if p is not None]
        p0 = [p for p in players if p.player_number == 0]
        assert p0[0].prt == 9
        assert p0[0].prt_name == "Jack of All Trades"

    def test_player_zero_tech_levels(self, m1_players):
        players = [p for p in m1_players if p is not None]
        p0 = [p for p in players if p.player_number == 0]
        assert p0[0].tech_energy == 3
        assert p0[0].tech_weapons == 3

    def test_all_players_have_names(self, m1_players):
        players = [p for p in m1_players if p is not None]
        for p in players:
            assert len(p.name_singular) > 0
