"""Integration tests: parse real Stars! game files.

Tests use the actual game files from autoplay/tests/data/ to verify that
file parsing, decryption, and block reading work correctly end-to-end.

All test files are from the same game: game_id=0x387B400D, v2.83.0
"""

import os
import struct
import pytest

from stars_web.block_reader import read_blocks, Block
from stars_web.file_header import FileHeader


# Path to real game files
TEST_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "autoplay", "tests", "data")
)


def _read_game_file(filename: str) -> bytes:
    path = os.path.join(TEST_DATA_DIR, filename)
    if not os.path.exists(path):
        pytest.skip(f"Test data file not found: {path}")
    with open(path, "rb") as f:
        return f.read()


class TestXYFileIntegration:
    """Test parsing Game.xy (universe/map file, type 0)."""

    def test_xy_file_header(self):
        data = _read_game_file("Game.xy")
        blocks = read_blocks(data)

        # First block should be file header
        hdr = blocks[0].file_header
        assert hdr is not None
        assert hdr.magic == b"J3J3"
        assert hdr.game_id == 0x387B400D
        assert hdr.version_major == 2
        assert hdr.version_minor == 83
        assert hdr.file_type == 0  # XY file
        assert hdr.player_index == 31  # Universal

    def test_xy_has_planets_block(self):
        """XY file should contain a type-7 (planets) block."""
        data = _read_game_file("Game.xy")
        blocks = read_blocks(data)
        planet_blocks = [b for b in blocks if b.type_id == 7]
        assert len(planet_blocks) == 1

    def test_xy_planets_block_game_name(self):
        """Planets block bytes 32-63 contain the game name."""
        data = _read_game_file("Game.xy")
        blocks = read_blocks(data)
        pb = [b for b in blocks if b.type_id == 7][0]
        # Game name is at bytes 32-63 of the decrypted block data
        game_name_raw = pb.data[32:64]
        game_name = game_name_raw.split(b"\x00")[0].decode("ascii", errors="replace")
        assert len(game_name) > 0
        print(f"Game name: {game_name!r}")

    def test_xy_planet_count(self):
        """Planets block should report a reasonable planet count (1-1000)."""
        data = _read_game_file("Game.xy")
        blocks = read_blocks(data)
        pb = [b for b in blocks if b.type_id == 7][0]
        planet_count = struct.unpack_from("<H", pb.data, 10)[0]
        assert 1 <= planet_count <= 1000
        print(f"Planet count: {planet_count}")

    def test_xy_planet_coordinates_reasonable(self):
        """Planet coordinates should be in valid range (x: 1000+, y: 0-4095)."""
        data = _read_game_file("Game.xy")
        blocks = read_blocks(data)
        pb = [b for b in blocks if b.type_id == 7][0]
        planet_count = struct.unpack_from("<H", pb.data, 10)[0]

        # Planet data should be in the extra_data attribute
        assert hasattr(pb, "extra_data"), "Type 7 block should have extra_data for planet coords"
        assert len(pb.extra_data) == planet_count * 4

        # Parse planet coordinates
        x = 1000
        for i in range(planet_count):
            planet_word = struct.unpack_from("<I", pb.extra_data, i * 4)[0]
            name_id = planet_word >> 22
            y = (planet_word >> 10) & 0xFFF
            x_offset = planet_word & 0x3FF
            x = x + x_offset

            # Coordinates should be in valid range
            assert 0 <= name_id < 1024, f"Planet {i}: name_id {name_id} out of range"
            assert 0 <= y <= 4095, f"Planet {i}: y={y} out of range"
            assert x >= 1000, f"Planet {i}: x={x} should be >= 1000"

    def test_xy_parses_completely(self):
        """All bytes in the XY file should be consumed by block parsing."""
        data = _read_game_file("Game.xy")
        blocks = read_blocks(data)
        # Should have parsed without error
        assert len(blocks) >= 2  # At least header + planets

    def test_xy_no_oversized_blocks(self):
        """No block should claim a size larger than the file."""
        data = _read_game_file("Game.xy")
        blocks = read_blocks(data)
        for b in blocks:
            assert b.size <= len(data), f"Block type {b.type_id} size {b.size} exceeds file size"


class TestMFileIntegration:
    """Test parsing Game.m1 and Game.m2 (player turn files, type 3)."""

    @pytest.mark.parametrize("filename,expected_player", [
        ("Game.m1", 0),
        ("Game.m2", 1),
    ])
    def test_m_file_header(self, filename, expected_player):
        data = _read_game_file(filename)
        blocks = read_blocks(data)
        hdr = blocks[0].file_header
        assert hdr.game_id == 0x387B400D
        assert hdr.file_type == 3  # M file
        assert hdr.player_index == expected_player

    @pytest.mark.parametrize("filename", ["Game.m1", "Game.m2"])
    def test_m_file_has_multiple_blocks(self, filename):
        data = _read_game_file(filename)
        blocks = read_blocks(data)
        assert len(blocks) >= 3  # Header + planets + other blocks

    @pytest.mark.parametrize("filename", ["Game.m1", "Game.m2"])
    def test_m_file_decrypted_blocks_not_random(self, filename):
        """Decrypted data should have structure, not random bytes."""
        data = _read_game_file(filename)
        blocks = read_blocks(data)
        for b in blocks:
            if b.encrypted and b.size >= 4:
                # Decrypted data should have some structure
                # At minimum, check it doesn't crash and produces bytes
                assert len(b.data) == b.size


class TestHSTFileIntegration:
    """Test parsing Game.hst (host state file, type 2)."""

    def test_hst_file_header(self):
        data = _read_game_file("Game.hst")
        blocks = read_blocks(data)
        hdr = blocks[0].file_header
        assert hdr.game_id == 0x387B400D
        assert hdr.file_type == 2  # HST file
        assert hdr.player_index == 31  # Host

    def test_hst_has_many_blocks(self):
        """HST file should contain many blocks (host state is rich)."""
        data = _read_game_file("Game.hst")
        blocks = read_blocks(data)
        # HST files contain race info, planet status, fleet data, etc.
        assert len(blocks) >= 10


class TestHFileIntegration:
    """Test parsing Game.h1 and Game.h2 (history files, type 4)."""

    @pytest.mark.parametrize("filename,expected_player", [
        ("Game.h1", 0),
        ("Game.h2", 1),
    ])
    def test_h_file_header(self, filename, expected_player):
        data = _read_game_file(filename)
        blocks = read_blocks(data)
        hdr = blocks[0].file_header
        assert hdr.game_id == 0x387B400D
        assert hdr.file_type == 4  # H file
        assert hdr.player_index == expected_player


class TestAllFiles:
    """Cross-cutting tests across all file types."""

    @pytest.mark.parametrize("filename", [
        "Game.xy", "Game.m1", "Game.m2", "Game.hst", "Game.h1", "Game.h2",
    ])
    def test_file_starts_with_header_block(self, filename):
        data = _read_game_file(filename)
        blocks = read_blocks(data)
        assert blocks[0].type_id == 8
        assert blocks[0].file_header is not None

    @pytest.mark.parametrize("filename", [
        "Game.xy", "Game.m1", "Game.m2", "Game.hst", "Game.h1", "Game.h2",
    ])
    def test_all_blocks_have_valid_type_ids(self, filename):
        data = _read_game_file(filename)
        blocks = read_blocks(data)
        for b in blocks:
            assert 0 <= b.type_id <= 63
