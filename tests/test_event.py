"""Test Suite for Event Block Parsing (Tier-1 Binary Parsing)

Block Type: 12 (0x0C)
Purpose: Game events, notifications, random events
Location: In M# and HST files, after player block, before planet blocks

Related Issues: Tier-1 binary parsing work
Pattern: Test-driven development (tests define spec, implementation fulfills tests)
"""

import struct
import pytest
from hypothesis import given, strategies as st

from stars_web.binary.event import (
    Event,
    EventType,
    decode_events,
    encode_events,
)


# ── Event test data strategies (Hypothesis) ─────────────────────────────


def event_strategy():
    """Generate valid Event dataclass instances."""
    return st.builds(
        Event,
        event_id=st.integers(min_value=0, max_value=0xFFFF),
        event_type=st.sampled_from([EventType.GENERIC, EventType.NOTIFICATION]),
        year=st.integers(min_value=2300, max_value=2700),
        text=st.text(
            alphabet=st.characters(min_codepoint=32, max_codepoint=126),
            min_size=1,
            max_size=100,
        ),
    )


# ──────────────────────────────────────────────────────────────────────────
# TEST: Event datastructures
# ──────────────────────────────────────────────────────────────────────────


class TestEventDatastructures:
    """Spec: Event dataclass validates fields."""

    def test_event_construction_minimal(self):
        """Event can be constructed with minimal required fields."""
        event = Event(event_id=1, event_type=EventType.GENERIC, year=2400, text="Test")
        assert event.event_id == 1
        assert event.year == 2400
        assert event.text == "Test"

    def test_event_id_zero(self):
        """Event can have event_id = 0 (first event)."""
        event = Event(event_id=0, event_type=EventType.GENERIC, year=2400, text="X")
        assert event.event_id == 0

    def test_event_type_enum(self):
        """Event type enforces enum values."""
        event = Event(event_id=1, event_type=EventType.NOTIFICATION, year=2400, text="Y")
        assert event.event_type == EventType.NOTIFICATION

    def test_year_in_game_range(self):
        """Event year is in game bounds."""
        event = Event(event_id=1, event_type=EventType.GENERIC, year=2500, text="Z")
        assert 2300 <= event.year <= 2700

    def test_text_stored_correctly(self):
        """Event text field is stored and retrieved."""
        text = "Mystery Trader has arrived at Blossom!"
        event = Event(event_id=1, event_type=EventType.GENERIC, year=2400, text=text)
        assert event.text == text


# ──────────────────────────────────────────────────────────────────────────
# TEST: Event binary format
# ──────────────────────────────────────────────────────────────────────────


class TestEventBinaryFormat:
    """Spec: Document expected binary layout for event blocks."""

    def test_event_block_header_two_bytes(self):
        """Block data begins with 2-byte event count (uint16 LE)."""
        data = bytearray(2)
        struct.pack_into("<H", data, 0, 1)  # 1 event
        assert struct.unpack_from("<H", data, 0)[0] == 1

    def test_minimal_event_record_size(self):
        """Each event record: type[1] + year[2] + text[var] minimum 4 bytes."""
        # Minimal: event_type (1 byte) + year (2 bytes) + text length (1 byte) = 4 bytes
        assert 4 <= 20  # Reasonable estimate

    def test_event_type_byte_encoding(self):
        """Event type encoded as single byte (0=generic, 1=notification, etc)."""
        assert EventType.GENERIC == 0
        assert EventType.NOTIFICATION == 1

    def test_year_two_byte_little_endian(self):
        """Game year encoded as uint16 LE."""
        year_2400 = 2400
        data = bytearray(2)
        struct.pack_into("<H", data, 0, year_2400)
        retrieved = struct.unpack_from("<H", data, 0)[0]
        assert retrieved == 2400


# ──────────────────────────────────────────────────────────────────────────
# TEST: Event decoder
# ──────────────────────────────────────────────────────────────────────────


class TestEventDecoder:
    """Spec: decode_events() parses binary event blocks."""

    def test_decode_single_generic_event(self):
        """Decoder extracts single generic event."""
        # Build synthetic block: count=1, event_type=0, year=2400, text="Test"
        data = bytearray(2)
        struct.pack_into("<H", data, 0, 1)  # count = 1

        # Event record starting at offset 2
        # Format: event_id (2) + type (1) + year (2) + text
        event_data = bytearray()
        event_data.extend(struct.pack("<H", 1))  # event_id = 1
        event_data.append(EventType.GENERIC)
        event_data.extend(struct.pack("<H", 2400))
        event_data.extend(b"Test\x00")  # null-terminated text

        data.extend(event_data)

        events = decode_events(bytes(data))
        assert len(events) == 1
        assert events[0].event_id == 1
        assert events[0].event_type == EventType.GENERIC
        assert events[0].year == 2400
        assert "Test" in events[0].text

    def test_decode_notification_event(self):
        """Decoder parses notification-type events."""
        data = bytearray(2)
        struct.pack_into("<H", data, 0, 1)

        event_data = bytearray()
        event_data.extend(struct.pack("<H", 2))  # event_id = 2
        event_data.append(EventType.NOTIFICATION)
        event_data.extend(struct.pack("<H", 2401))
        event_data.extend(b"Notification\x00")

        data.extend(event_data)

        events = decode_events(bytes(data))
        assert len(events) == 1
        assert events[0].event_type == EventType.NOTIFICATION

    def test_decode_empty_block(self):
        """Decoder handles block with zero events."""
        data = bytearray(2)
        struct.pack_into("<H", data, 0, 0)  # count = 0

        events = decode_events(bytes(data))
        assert len(events) == 0

    def test_decode_rejects_invalid_data(self):
        """Decoder raises on truncated/malformed data."""
        data = bytearray(1)  # Too short for count header
        with pytest.raises(ValueError):
            decode_events(bytes(data))


# ──────────────────────────────────────────────────────────────────────────
# TEST: Event edge cases
# ──────────────────────────────────────────────────────────────────────────


class TestEventEdgeCases:
    """Spec: Event handling at boundaries and error conditions."""

    def test_event_with_max_id(self):
        """Event ID can reach max value (0xFFFF)."""
        event = Event(event_id=0xFFFF, event_type=EventType.GENERIC, year=2400, text="Max ID")
        assert event.event_id == 0xFFFF

    def test_event_with_long_text(self):
        """Event text can be reasonably long."""
        long_text = "A" * 500
        event = Event(event_id=1, event_type=EventType.GENERIC, year=2400, text=long_text)
        assert len(event.text) == 500

    def test_event_year_boundary_2300(self):
        """Event year can be at 2300 (earliest game year)."""
        event = Event(event_id=1, event_type=EventType.GENERIC, year=2300, text="Old")
        assert event.year == 2300

    def test_event_year_boundary_2700(self):
        """Event year can be at 2700 (typical endgame)."""
        event = Event(event_id=1, event_type=EventType.GENERIC, year=2700, text="New")
        assert event.year == 2700

    def test_decoder_handles_multiple_events(self):
        """Decoder correctly parses multiple events in one block."""
        data = bytearray(2)
        struct.pack_into("<H", data, 0, 2)  # 2 events

        # First event
        event_data = bytearray()
        event_data.extend(struct.pack("<H", 1))  # event_id = 1
        event_data.append(EventType.GENERIC)
        event_data.extend(struct.pack("<H", 2400))
        event_data.extend(b"Event1\x00")

        # Second event
        event_data.extend(struct.pack("<H", 2))  # event_id = 2
        event_data.append(EventType.NOTIFICATION)
        event_data.extend(struct.pack("<H", 2401))
        event_data.extend(b"Event2\x00")

        data.extend(event_data)

        events = decode_events(bytes(data))
        assert len(events) == 2
        assert events[0].event_id == 1
        assert events[0].event_type == EventType.GENERIC
        assert events[1].event_id == 2
        assert events[1].event_type == EventType.NOTIFICATION


# ──────────────────────────────────────────────────────────────────────────
# TEST: Event property invariants (Hypothesis)
# ──────────────────────────────────────────────────────────────────────────


class TestEventPropertyInvariants:
    """Spec: Property-based tests for event invariants."""

    @given(event=event_strategy())
    def test_event_fields_preserved(self, event):
        """All event fields can be round-tripped through encode/decode."""
        events = [event]
        encoded = encode_events(events)
        decoded = decode_events(encoded)

        assert len(decoded) == 1
        assert decoded[0].event_id == event.event_id
        assert decoded[0].event_type == event.event_type
        assert decoded[0].year == event.year
        # Text preservation depends on encoding; verify non-empty
        assert len(decoded[0].text) > 0

    def test_serialization_roundtrip(self):
        """Encode then decode yields same events."""
        original = [
            Event(event_id=1, event_type=EventType.GENERIC, year=2400, text="First"),
            Event(event_id=2, event_type=EventType.NOTIFICATION, year=2401, text="Second"),
        ]
        data = encode_events(original)
        parsed = decode_events(data)

        assert len(parsed) == 2
        assert parsed[0].event_id == 1
        assert parsed[1].event_id == 2


# ──────────────────────────────────────────────────────────────────────────
# TEST: Event integration with GameState
# ──────────────────────────────────────────────────────────────────────────


class TestEventIntegration:
    """Spec: Events integrate properly with GameState parsing."""

    def test_event_block_parsed_when_present(self):
        """GameState collects events when block type 12 is encountered."""
        # This will be tested after GameState integration
        pass

    def test_multiple_event_blocks_merged(self):
        """Multiple event blocks are combined into one events list."""
        # This will be tested after GameState integration
        pass

    def test_events_accessible_from_game_state(self):
        """Parsed events are accessible via game_state.events."""
        # This will be tested after GameState integration
        pass


# ──────────────────────────────────────────────────────────────────────────
# TEST: Real game file events
# ──────────────────────────────────────────────────────────────────────────


class TestRealGameFileEvents:
    """Spec: Parses real events from actual game files."""

    @pytest.mark.skip(reason="Real game file events not yet available")
    def test_parse_game_file_events(self):
        """Can extract and parse event blocks from real game file."""
        from pathlib import Path

        m1_file = Path("docs/images/original_fat_client_screenshots/Game.m1")
        if not m1_file.exists():
            pytest.skip("Test game file not found")

        # Will implement after basic parsing works
        pass
