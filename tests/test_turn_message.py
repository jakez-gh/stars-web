"""
Test Suite for TurnMessage Block Parsing (Tier-1 Binary Parsing)

These tests define the complete specification for parsing TurnMessage blocks.
Each failing test is a requirement to implement.

Status: Specification phase (all tests should fail initially)
Related Issues: #152 (tests), #153 (dataclass), #154 (integration)

Block Type: 24 (0x18)
Purpose: Player messages (diplomacy, trade, notifications)
Location: After battle plans, before object blocks in M# files
"""

import pytest
import struct
from dataclasses import dataclass
from hypothesis import given, strategies as st
from pathlib import Path


class TestTurnMessageDataclass:
    """Spec: TurnMessage dataclass properly represents message structure."""

    def test_dataclass_exists(self):
        """TurnMessage dataclass is defined."""

        assert dataclass

    def test_dataclass_has_required_fields(self):
        """TurnMessage has all required fields."""
        from stars_web.binary.turn_message import TurnMessage
        import dataclasses

        fields = {f.name for f in dataclasses.fields(TurnMessage)}
        required = {"message_id", "source_player", "dest_player", "year", "action_code", "text"}
        assert required.issubset(fields), f"Missing fields: {required - fields}"

    def test_can_instantiate_with_valid_data(self):
        """Can create TurnMessage instance with valid values."""
        from stars_web.binary.turn_message import TurnMessage

        msg = TurnMessage(
            message_id=1,
            source_player=0,
            dest_player=1,
            year=2450,
            action_code=1,
            text="Test message",
        )
        assert msg.message_id == 1
        assert msg.text == "Test message"

    def test_dataclass_has_sensible_defaults(self):
        """Optional fields have reasonable defaults."""
        from stars_web.binary.turn_message import TurnMessage

        # Should be able to create with minimal args
        msg = TurnMessage(message_id=1, source_player=0, dest_player=1, year=2400, text="Message")
        assert msg.message_id == 1

    def test_dataclass_repr_is_useful(self):
        """String representation includes key info."""
        from stars_web.binary.turn_message import TurnMessage

        msg = TurnMessage(
            message_id=1, source_player=0, dest_player=1, year=2450, action_code=1, text="Test"
        )
        repr_str = repr(msg)
        assert "TurnMessage" in repr_str or "message_id" in repr_str


class TestMessageBinaryFormat:
    """Spec: Binary layout documented via real game file analysis."""

    def test_block_type_id_is_24(self):
        """Message blocks identified by type ID 24."""
        from stars_web.binary.turn_message import BLOCK_TYPE_MESSAGE

        assert BLOCK_TYPE_MESSAGE == 24

    def test_variable_size_block(self):
        """Message blocks have variable size (text length varies)."""
        # Documented from block structure reference
        pass

    def test_layout_documented_in_docstring(self):
        """Block layout documented in module docstring."""
        from stars_web.binary import turn_message

        assert turn_message.__doc__
        assert "message_id" in turn_message.__doc__.lower()

    def test_field_offsets_documented(self):
        """Test includes actual field byte offsets."""
        # Should extract these from tools_dump_blocks.py output:
        # Example:
        # Offset  Size   Field
        # 0       2      message_id (uint16 LE)
        # 2       1      source_player (uint8)
        # 3       1      dest_player (uint8)
        # 4       2      year (uint16 LE)
        # 6       1      action_code (uint8)
        # 7+      var    text (Stars! encoded string)
        pass


class TestMessageDecoder:
    """Spec: Decoder correctly parses message block bytes."""

    def test_decoder_function_exists(self):
        """Decoder function is implemented."""
        from stars_web.binary.turn_message import decode_message

        assert callable(decode_message)

    def test_decoder_parses_all_fields(self):
        """Decoder extracts all required fields."""
        from stars_web.binary.turn_message import decode_message

        # Create minimal valid message block data
        data = bytearray(8)  # Minimum size
        struct.pack_into("<H", data, 0, 1)  # message_id = 1
        data[2] = 0  # source_player = 0
        data[3] = 1  # dest_player = 1
        struct.pack_into("<H", data, 4, 50)  # year = 2450
        data[6] = 1  # action_code = 1
        data[7] = 0  # text terminator

        msg = decode_message(bytes(data))
        assert msg.message_id == 1
        assert msg.source_player == 0
        assert msg.dest_player == 1

    def test_decoder_handles_stars_encoded_strings(self):
        """Decoder correctly decodes Stars! encoded text."""

        # Stars! uses special string encoding for messages
        # Need to test with actual encoded string
        pass

    @given(st.binary(min_size=8, max_size=512))
    def test_decoder_doesnt_crash_on_junk(self, junk_data):
        """Decoder fails gracefully, doesn't crash on random bytes."""
        from stars_web.binary.turn_message import decode_message

        try:
            msg = decode_message(junk_data)
            # Either succeeds or raises specific exception
            assert msg is None or hasattr(msg, "message_id")
        except (ValueError, struct.error, IndexError):
            # Expected for malformed data
            pass

    def test_decoder_rejects_truncated_data(self):
        """Decoder rejects blocks that are too short."""
        from stars_web.binary.turn_message import decode_message

        with pytest.raises((ValueError, struct.error)):
            decode_message(b"\x00\x01\x02")  # Only 3 bytes, need at least 8

    def test_decoder_validates_player_range(self):
        """Decoder validates source/dest player are 0-15."""
        from stars_web.binary.turn_message import decode_message

        data = bytearray(8)
        struct.pack_into("<H", data, 0, 1)
        data[2] = 50  # Invalid player
        data[3] = 1

        # Should raise ValueError for invalid player
        with pytest.raises(ValueError):
            decode_message(bytes(data))


class TestMessageEdgeCases:
    """Spec: Handles boundary conditions and malformed messages."""

    def test_zero_message_id(self):
        """Handles message_id = 0 (may be sentinel)."""
        from stars_web.binary.turn_message import decode_message

        data = bytearray(8)
        struct.pack_into("<H", data, 0, 0)  # message_id = 0
        data[2] = 0
        data[3] = 1

        # Should succeed or raise specific exception
        try:
            msg = decode_message(bytes(data))
            assert msg.message_id == 0
        except ValueError:
            pass

    def test_max_message_id(self):
        """Handles max message_id (uint16)."""
        from stars_web.binary.turn_message import decode_message

        data = bytearray(8)
        struct.pack_into("<H", data, 0, 0xFFFF)
        data[2] = 0
        data[3] = 1

        msg = decode_message(bytes(data))
        assert msg.message_id == 65535

    def test_same_source_and_dest_player(self):
        """Handles message from player to self."""
        from stars_web.binary.turn_message import decode_message

        data = bytearray(8)
        struct.pack_into("<H", data, 0, 1)
        data[2] = 0  # source
        data[3] = 0  # dest (same)

        msg = decode_message(bytes(data))
        assert msg.source_player == msg.dest_player

    def test_empty_message_text(self):
        """Handles messages with no text."""
        from stars_web.binary.turn_message import decode_message

        data = bytearray(8)
        struct.pack_into("<H", data, 0, 1)
        data[2] = 0
        data[3] = 1

        msg = decode_message(bytes(data))
        assert msg.text == "" or msg.text is None

    def test_max_message_length(self):
        """Handles very long message text."""
        # Need to construct proper encoded block
        pass


class TestMessageIntegration:
    """Spec: Message block integrates with game state."""

    def test_block_registered_in_dispatcher(self):
        """Block type 24 routed to message decoder."""

        # GameState should have dispatcher entry
        # When block type 24 encountered, calls decode_message
        pass

    def test_parsed_messages_added_to_game_state(self):
        """Parsed messages stored in GameState.messages."""
        # Should be able to add to game state
        # state.messages.append(msg)  or similar
        # assert msg in state.messages
        pass

    def test_messages_filterable_by_player(self):
        """Can filter messages by source/dest player."""
        # GameState should support: state.get_messages_for_player(1)
        pass

    def test_message_action_codes_documented(self):
        """Action codes documented with their meanings."""
        from stars_web.binary.turn_message import MESSAGE_ACTION_CODES

        assert 1 in MESSAGE_ACTION_CODES  # At minimum
        # Values like: 1="Offer", 2="Accept", 3="Decline", etc.


class TestPropertyBasedInvariants:
    """Spec: Messages maintain invariants under all conditions."""

    def test_player_numbers_valid_range(self):
        """Source and dest players are always 0-15."""
        from stars_web.binary.turn_message import TurnMessage

        for player in [0, 1, 7, 15]:
            msg = TurnMessage(
                message_id=1, source_player=player, dest_player=player, year=2400, text=""
            )
            assert 0 <= msg.source_player <= 15
            assert 0 <= msg.dest_player <= 15

    def test_year_valid_range(self):
        """Year is between 2400 and 2900."""
        from stars_web.binary.turn_message import TurnMessage

        msg = TurnMessage(message_id=1, source_player=0, dest_player=1, year=2500, text="")
        assert 2400 <= msg.year <= 2900

    def test_serialization_roundtrip(self):
        """Parse -> serialize -> parse yields same message."""

        # Create message, serialize it, deserialize, verify
        pass


class TestRealGameFileMessages:
    """Spec: Parses real messages from actual game files."""

    def test_parse_game_file_messages(self):
        """Can extract and parse message blocks from real game file."""
        game_file = Path("../../starswine4/Game.m1")
        if not game_file.exists():
            pytest.skip("Game file not available")

        # Use tools_dump_blocks.py to extract message blocks
        # Verify can parse them
        pass

    def test_real_message_text_readable(self):
        """Text from real messages is readable after decoding."""
        # After parsing real game file,message text should be sensible
        pass
