"""Tests for the Stars! file block reader.

The block reader parses a complete Stars! file into blocks:
1. Reads 2-byte block header (type_id[6 bits] | size[10 bits])
2. Reads block data (size bytes)
3. File header block (type_id=8) is unencrypted, initializes decryptor
4. All other blocks are decrypted using the PRNG XOR cipher
5. Type 0 is a footer/EOF block (also unencrypted)

Special: PlanetsBlock (type_id=7) has extra data appended (4 bytes per planet).
"""

import struct

from stars_web.block_reader import read_blocks


def _make_block(type_id: int, data: bytes) -> bytes:
    """Construct a raw block: 2-byte header + data."""
    size = len(data)
    assert size <= 0x3FF, "Block data too large"
    assert type_id <= 0x3F, "Type ID too large"
    header = (type_id << 10) | size
    return struct.pack("<H", header) + data


def _make_file_header_block(
    game_id=0x387B400D,
    turn=0,
    player_index=0,
    salt=0,
    file_type=0,
    flags=0,
):
    """Make a complete file header block (type 8) with block header."""
    from tests.test_file_header import _make_header_bytes

    header_data = _make_header_bytes(
        game_id=game_id,
        turn=turn,
        player_index=player_index,
        salt=salt,
        file_type=file_type,
        flags=flags,
    )
    return _make_block(8, header_data)


class TestBlockHeader:
    """Test 2-byte block header parsing."""

    def test_type_id_extraction(self):
        """type_id = upper 6 bits of 16-bit header."""
        data = _make_file_header_block()
        blocks = read_blocks(data)
        assert blocks[0].type_id == 8

    def test_size_extraction(self):
        """size = lower 10 bits of 16-bit header."""
        data = _make_file_header_block()
        blocks = read_blocks(data)
        assert blocks[0].size == 16


class TestReadBlocks:
    """Test reading a complete file into blocks."""

    def test_single_header_block(self):
        """A file with just a header block."""
        raw = _make_file_header_block()
        blocks = read_blocks(raw)
        assert len(blocks) == 1
        assert blocks[0].type_id == 8

    def test_header_block_not_encrypted(self):
        """The file header block data should not be encrypted."""
        raw = _make_file_header_block(game_id=0x387B400D)
        blocks = read_blocks(raw)
        # Should contain J3J3 magic
        assert blocks[0].data[:4] == b"J3J3"

    def test_header_parsed_as_file_header(self):
        """The header block should have a parsed file_header attribute."""
        raw = _make_file_header_block(game_id=0x12345678, turn=42)
        blocks = read_blocks(raw)
        assert blocks[0].file_header is not None
        assert blocks[0].file_header.game_id == 0x12345678
        assert blocks[0].file_header.turn == 42

    def test_multiple_blocks(self):
        """File with header + encrypted blocks."""
        # Make a file: header block + a small encrypted block
        header_block = _make_file_header_block(salt=0, game_id=0, turn=0, player_index=0)

        # A type-6 block with 4 bytes of "encrypted" data
        # (we need to encrypt it properly for decryption to work)
        from stars_web.decryptor import Decryptor

        dec = Decryptor()
        dec.init_decryption(salt=0, game_id=0, turn=0, player_index=0, shareware=False)

        plaintext = b"\x01\x02\x03\x04"
        # Encrypt: XOR with the next PRNG value
        xor_val = dec.random.next_random()
        plain_int = int.from_bytes(plaintext, "little")
        enc_int = plain_int ^ xor_val
        encrypted = enc_int.to_bytes(4, "little")

        data_block = _make_block(6, encrypted)
        raw = header_block + data_block

        blocks = read_blocks(raw)
        assert len(blocks) == 2
        assert blocks[1].type_id == 6
        assert blocks[1].data == plaintext

    def test_footer_block_not_encrypted(self):
        """Type 0 blocks (footer) should not be decrypted."""
        header_block = _make_file_header_block()
        footer = _make_block(0, b"\xFF\xFF")
        raw = header_block + footer
        blocks = read_blocks(raw)
        assert len(blocks) == 2
        assert blocks[1].type_id == 0
        assert blocks[1].data == b"\xFF\xFF"

    def test_block_data_attribute(self):
        """Each block should have type_id, size, and data attributes."""
        raw = _make_file_header_block()
        blocks = read_blocks(raw)
        block = blocks[0]
        assert hasattr(block, "type_id")
        assert hasattr(block, "size")
        assert hasattr(block, "data")

    def test_empty_file_returns_empty(self):
        """An empty file should return no blocks."""
        blocks = read_blocks(b"")
        assert blocks == []
