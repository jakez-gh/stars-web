"""Tests for Stars! string decoding and ship design parsing."""

import struct
import pytest

from stars_web.stars_string import decode_stars_string
from stars_web.game_state import ShipDesign, parse_design_block
from stars_web.block_reader import Block


# ── Stars! string decoding ──────────────────────────────────────────


class TestDecodeStarsString:
    """Stars! uses a custom nibble-based text encoding.

    Encoding rules (from starsapi Util.java):
      nibbles 0-A: 1-nibble lookup in " aehilnorst"
      nibble B+x:  2-nibble lookup in "ABCDEFGHIJKLMNOP"
      nibble C+x:  2-nibble lookup in "QRSTUVWXYZ012345"
      nibble D+x:  2-nibble lookup in "6789bcdfgjkmpquv"
      nibble E+x:  2-nibble lookup in "wxyz+-,!.?:;'*%$"
      nibble F+xy: 3-nibble raw ASCII (swapped nibbles → char)
    First byte = byte count of encoded data.
    """

    def test_single_char_one_nibble(self):
        """Space is nibble 0, 'a' is nibble 1, etc."""
        # "a" encodes as nibble 1 → hex "1F" (padded with F)
        # byte_size = 1, data = 0x1F
        raw = bytes([1, 0x1F])
        text, consumed = decode_stars_string(raw, 0)
        assert text == "a"
        assert consumed == 2

    def test_two_char_one_nibble_each(self):
        """'a' + 'e' = nibbles 1,2 → hex "12", byte_size=1."""
        raw = bytes([1, 0x12])
        text, consumed = decode_stars_string(raw, 0)
        assert text == "ae"
        assert consumed == 2

    def test_all_single_nibble_chars(self):
        """All 11 one-nibble characters: ' aehilnorst'."""
        # " aehilnorst" → nibbles 0,1,2,3,4,5,6,7,8,9,A
        # 11 nibbles → "01 23 45 67 89 AF" = 6 bytes
        raw = bytes([6, 0x01, 0x23, 0x45, 0x67, 0x89, 0xAF])
        text, consumed = decode_stars_string(raw, 0)
        assert text == " aehilnorst"
        assert consumed == 7

    def test_two_nibble_uppercase(self):
        """'S' is nibbleB+2 → "B2", 'c' is nibbleD+4 → "D4"."""
        # "Scout" → S=B2, c=D4, o=8, u=D9, t=A
        # nibbles: B2 D4 8 D9 A → "B2D48D9AF" (9 nibbles, padded)
        # bytes: 5, B2 D4 8D 9A F? → need to compute exactly
        # Let's test with a known example from the game data

    def test_decode_at_offset(self):
        """Can decode from an arbitrary offset in the data."""
        prefix = bytes([0xFF, 0xFF, 0xFF])  # 3 junk bytes
        # "a" = nibble 1, padded → 0x1F
        encoded = bytes([1, 0x1F])
        raw = prefix + encoded
        text, consumed = decode_stars_string(raw, 3)
        assert text == "a"
        assert consumed == 2

    def test_three_nibble_ascii(self):
        """F+xy encodes raw ASCII with swapped nibbles."""
        # '#' is ASCII 0x23 → swapped nibbles → F32
        # nibbles: F32 → need to pad: "F32F" = 2 bytes
        raw = bytes([2, 0xF3, 0x2F])
        text, consumed = decode_stars_string(raw, 0)
        assert text == "#"
        assert consumed == 3


# ── Ship design block parsing ───────────────────────────────────────


class TestShipDesignDataclass:
    """ShipDesign should hold all fields from a design block."""

    def test_ship_design_fields(self):
        design = ShipDesign(
            design_number=0,
            is_starbase=False,
            hull_id=4,
            hull_name="Scout",
            name="Long Range Scout",
            armor=20,
            mass=0,
            slot_count=3,
            slots=[],
            is_full_design=True,
            turn_designed=0,
            total_built=1,
            total_remaining=1,
        )
        assert design.hull_name == "Scout"
        assert not design.is_starbase
        assert design.design_number == 0


class TestParseDesignBlock:
    """Parse ship/starbase design blocks (type 26)."""

    def _make_full_design_block(
        self,
        design_number=0,
        hull_id=4,
        pic=17,
        armor=20,
        slot_count=1,
        slots=None,
        name_bytes=b"\x04\xC2\xD5\x7D\xEA",  # "Scout" Stars!-encoded
        is_starbase=False,
        turn_designed=0,
        total_built=1,
        total_remaining=1,
    ):
        """Helper: build a synthetic full design block."""
        byte0 = 0x07  # full design
        byte1 = 0x01 | (design_number << 2)
        if is_starbase:
            byte1 |= 0x40
        data = bytearray()
        data.append(byte0)
        data.append(byte1)
        data.append(hull_id)
        data.append(pic)
        data.extend(struct.pack("<H", armor))
        data.append(slot_count)
        data.extend(struct.pack("<H", turn_designed))
        data.extend(struct.pack("<I", total_built))
        data.extend(struct.pack("<I", total_remaining))
        if slots is None:
            slots = [(1, 3, 1)]  # engine slot: cat=1, item=3, count=1
        for cat, item_id, count in slots:
            data.extend(struct.pack("<H", cat))
            data.append(item_id)
            data.append(count)
        data.extend(name_bytes)
        return Block(type_id=26, size=len(data), data=bytes(data))

    def test_parse_full_scout_design(self):
        block = self._make_full_design_block(
            design_number=0,
            hull_id=4,
            armor=20,
            slot_count=1,
            slots=[(1, 3, 1)],
            name_bytes=b"\x04\xC2\xD5\x7D\xEA",  # "Scout" Stars!-encoded
        )
        design = parse_design_block(block)
        assert design.design_number == 0
        assert design.hull_id == 4
        assert design.hull_name == "Scout"
        assert design.name == "Scout"
        assert design.armor == 20
        assert design.is_full_design is True
        assert design.is_starbase is False
        assert design.slot_count == 1
        assert len(design.slots) == 1
        assert design.slots[0] == (1, 3, 1)

    def test_parse_starbase_design(self):
        block = self._make_full_design_block(
            design_number=0,
            hull_id=34,
            is_starbase=True,
            armor=500,
            slot_count=2,
            slots=[(16, 0, 8), (4, 0, 8)],
            name_bytes=b"\x05\xC2\xA1\x8D\x41\x92",  # "Starbase" Stars!-encoded
        )
        design = parse_design_block(block)
        assert design.is_starbase is True
        assert design.hull_id == 34
        assert design.hull_name == "Space Station"
        assert design.design_number == 0
        assert design.armor == 500

    def test_parse_partial_design(self):
        """Partial designs have mass instead of full slot data."""
        byte0 = 0x03  # partial
        byte1 = 0x01 | (2 << 2)  # design_number=2
        data = bytearray()
        data.append(byte0)
        data.append(byte1)
        data.append(4)  # hull_id = Scout
        data.append(17)  # pic
        data.extend(struct.pack("<H", 25))  # mass
        data.extend(b"\x04\xC2\xD5\x7D\xEA")  # "Scout" Stars!-encoded
        block = Block(type_id=26, size=len(data), data=bytes(data))
        design = parse_design_block(block)
        assert design.design_number == 2
        assert design.is_full_design is False
        assert design.mass == 25
        assert design.slot_count == 0
        assert design.slots == []

    def test_design_number_encoding(self):
        """Design number is in bits 2-5 of byte 1."""
        for num in range(16):
            block = self._make_full_design_block(design_number=num)
            design = parse_design_block(block)
            assert design.design_number == num

    def test_wrong_block_type_returns_none(self):
        block = Block(type_id=13, size=10, data=b"\x00" * 10)
        assert parse_design_block(block) is None


# ── Integration: parse designs from real game file ──────────────────


class TestParseDesignsFromFile:
    """Parse design blocks from real Stars! game files."""

    DATA_DIR = "docs/images/original_fat_client_screenshots"

    @pytest.fixture
    def m1_designs(self):
        import os

        path = os.path.join(self.DATA_DIR, "Game.m1")
        if not os.path.exists(path):
            pytest.skip("Game.m1 not found")
        from stars_web.block_reader import read_blocks

        data = open(path, "rb").read()
        blocks = read_blocks(data)
        return [parse_design_block(b) for b in blocks if b.type_id == 26]

    def test_seven_designs_found(self, m1_designs):
        designs = [d for d in m1_designs if d is not None]
        assert len(designs) == 7

    def test_design_numbers_sequential(self, m1_designs):
        designs = [d for d in m1_designs if d is not None]
        ship_designs = [d for d in designs if not d.is_starbase]
        assert sorted(d.design_number for d in ship_designs) == [0, 1, 2, 3, 4, 5]

    def test_one_starbase_design(self, m1_designs):
        designs = [d for d in m1_designs if d is not None]
        starbases = [d for d in designs if d.is_starbase]
        assert len(starbases) == 1
        assert starbases[0].hull_id == 34

    def test_all_designs_have_names(self, m1_designs):
        designs = [d for d in m1_designs if d is not None]
        for d in designs:
            assert len(d.name) > 0, f"Design #{d.design_number} has empty name"

    def test_all_designs_are_full(self, m1_designs):
        """Player's own designs should be full (not partial)."""
        designs = [d for d in m1_designs if d is not None]
        for d in designs:
            assert d.is_full_design, f"Design #{d.design_number} is partial"

    def test_all_designs_have_slots(self, m1_designs):
        designs = [d for d in m1_designs if d is not None]
        for d in designs:
            assert d.slot_count > 0
            assert len(d.slots) == d.slot_count
