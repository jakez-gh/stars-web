"""Tests for the Stars! file header parser.

The file header block (type_id=8) is the first block in every Stars! file.
It is 16 bytes of unencrypted data containing the magic number, game ID,
version, turn number, player info/salt, file type, and flags.

Verified layout (from real game files):
  bytes 0-3:   magic "J3J3"
  bytes 4-7:   game_id (uint32 LE)
  bytes 8-9:   version (packed: major[4]|minor[7]|increment[5])
  bytes 10-11: turn (uint16 LE)
  bytes 12-13: player_data (packed: salt[11 upper]|player[5 lower])
  byte 14:     file_type (0=xy, 1=x#, 2=hst, 3=m#, 4=h#, 5=r#)
  byte 15:     flags
"""

import struct
import pytest

from stars_web.file_header import FileHeader


def _make_header_bytes(
    magic=b"J3J3",
    game_id=0x387B400D,
    version_major=2,
    version_minor=83,
    version_inc=0,
    turn=0,
    player_index=0,
    salt=0,
    file_type=0,
    flags=0,
):
    """Helper to construct a 16-byte file header."""
    version = (version_major << 12) | (version_minor << 5) | version_inc
    player_data = (salt << 5) | (player_index & 0x1F)
    return (
        magic
        + struct.pack("<I", game_id)
        + struct.pack("<H", version)
        + struct.pack("<H", turn)
        + struct.pack("<H", player_data)
        + struct.pack("<B", file_type)
        + struct.pack("<B", flags)
    )


class TestFileHeaderParsing:
    def test_magic(self):
        data = _make_header_bytes()
        hdr = FileHeader(data)
        assert hdr.magic == b"J3J3"

    def test_game_id(self):
        data = _make_header_bytes(game_id=0x387B400D)
        hdr = FileHeader(data)
        assert hdr.game_id == 0x387B400D

    def test_version(self):
        data = _make_header_bytes(version_major=2, version_minor=83, version_inc=0)
        hdr = FileHeader(data)
        assert hdr.version_major == 2
        assert hdr.version_minor == 83
        assert hdr.version_increment == 0

    def test_turn(self):
        data = _make_header_bytes(turn=42)
        hdr = FileHeader(data)
        assert hdr.turn == 42

    def test_year(self):
        """Year = 2400 + turn."""
        data = _make_header_bytes(turn=100)
        hdr = FileHeader(data)
        assert hdr.year == 2500

    def test_player_index(self):
        data = _make_header_bytes(player_index=5)
        hdr = FileHeader(data)
        assert hdr.player_index == 5

    def test_salt(self):
        data = _make_header_bytes(salt=1103)
        hdr = FileHeader(data)
        assert hdr.salt == 1103

    def test_file_type_xy(self):
        data = _make_header_bytes(file_type=0)
        hdr = FileHeader(data)
        assert hdr.file_type == 0

    def test_file_type_hst(self):
        data = _make_header_bytes(file_type=2)
        hdr = FileHeader(data)
        assert hdr.file_type == 2

    def test_flags_raw(self):
        data = _make_header_bytes(flags=0b00010100)
        hdr = FileHeader(data)
        assert hdr.flags == 0b00010100

    def test_flag_submitted(self):
        data = _make_header_bytes(flags=0b00000001)
        hdr = FileHeader(data)
        assert hdr.turn_submitted is True

    def test_flag_host_using(self):
        data = _make_header_bytes(flags=0b00000010)
        hdr = FileHeader(data)
        assert hdr.host_using is True

    def test_flag_multiple_turns(self):
        data = _make_header_bytes(flags=0b00000100)
        hdr = FileHeader(data)
        assert hdr.multiple_turns is True

    def test_flag_game_over(self):
        data = _make_header_bytes(flags=0b00001000)
        hdr = FileHeader(data)
        assert hdr.game_over is True

    def test_flag_shareware(self):
        data = _make_header_bytes(flags=0b00010000)
        hdr = FileHeader(data)
        assert hdr.shareware is True

    def test_invalid_magic_raises(self):
        data = _make_header_bytes(magic=b"XXXX")
        with pytest.raises(ValueError, match="magic"):
            FileHeader(data)

    def test_too_short_raises(self):
        with pytest.raises(ValueError):
            FileHeader(b"\x00" * 10)


class TestFileHeaderWithRealGameValues:
    """Test parsing with values from actual starswine4 game files.

    All test files share: game_id=0x387B400D, version 2.83.0
    """

    def test_xy_file_header(self):
        """XY file: player=31 (host/universal), type=0"""
        data = _make_header_bytes(
            game_id=0x387B400D,
            version_major=2,
            version_minor=83,
            version_inc=0,
            turn=0,
            player_index=31,
            salt=1103,
            file_type=0,
            flags=0,
        )
        hdr = FileHeader(data)
        assert hdr.game_id == 0x387B400D
        assert hdr.player_index == 31
        assert hdr.file_type == 0
        assert hdr.salt == 1103

    def test_m1_file_header(self):
        """M1 file: player=0, type=3"""
        data = _make_header_bytes(
            game_id=0x387B400D,
            version_major=2,
            version_minor=83,
            version_inc=0,
            turn=0,
            player_index=0,
            file_type=3,
            flags=0,
        )
        hdr = FileHeader(data)
        assert hdr.player_index == 0
        assert hdr.file_type == 3

    def test_hst_file_header(self):
        """HST file: player=31 (host), type=2"""
        data = _make_header_bytes(
            game_id=0x387B400D,
            version_major=2,
            version_minor=83,
            version_inc=0,
            turn=0,
            player_index=31,
            file_type=2,
            flags=0,
        )
        hdr = FileHeader(data)
        assert hdr.player_index == 31
        assert hdr.file_type == 2
