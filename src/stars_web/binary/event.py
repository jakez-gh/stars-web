"""Event block parsing for Stars! game files.

Block Type: 12 (0x0C)
Purpose: Game events (random events, notifications, system messages)
Location: After player block, before planet blocks in M# and HST files

Field Layout (variable-length):
  Bytes 0-1: Event count (uint16 LE)
  Bytes 2+: Event data (varies by type)

Event Types:
  0 = Generic event
  1 = Notification

Each event starts with type byte, then type-specific fields.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import List


BLOCK_TYPE_EVENT = 12


class EventType(IntEnum):
    """Event type identifiers."""

    GENERIC = 0
    NOTIFICATION = 1


@dataclass
class Event:
    """Represents a single game event.

    Events are notifications to the player about game occurrences:
    - Random events (planet events, mystery trader, etc)
    - Combat results
    - Diplomacy notifications
    - System messages

    Fields:
      event_id: Unique identifier for this event
      event_type: Type code (0=generic, 1=notification)
      year: Game year when event occurred (2300-2700)
      text: Event description (Stars! or ASCII encoded)
    """

    event_id: int
    event_type: int
    year: int
    text: str

    def __post_init__(self):
        """Validate event fields."""
        if not 0 <= self.event_id <= 0xFFFF:
            raise ValueError(f"event_id must be 0-65535, got {self.event_id}")
        if self.event_type not in (EventType.GENERIC, EventType.NOTIFICATION):
            raise ValueError(f"Invalid event_type: {self.event_type}")
        if not 2300 <= self.year <= 2700:
            raise ValueError(f"year must be 2300-2700, got {self.year}")
        if not self.text:
            raise ValueError("text cannot be empty")


def decode_events(data: bytes) -> List[Event]:
    """Parse events from binary block data.

    Binary format:
      Offset 0-1: Event count (uint16 LE)
      Offset 2+: Event records (variable-length)

    Each event record:
      Bytes 0-1: Event ID (uint16 LE)
      Byte 2: Type code (0=generic, 1=notification)
      Bytes 3-4: Game year (uint16 LE)
      Bytes 5+: Text (null-terminated string)

    Args:
        data: Raw event block data (bytes)

    Returns:
        List of parsed Event objects

    Returns an empty list (rather than raising) if the data format is
    unrecognized or the count field implies more records than available bytes.
    Unknown event types are normalized to GENERIC to preserve data flow.

    Raises:
        ValueError: Only if data is shorter than the 2-byte count header.
    """
    if not data or len(data) < 2:
        raise ValueError(f"Event block data too short: {len(data)} bytes")

    events = []
    count = struct.unpack_from("<H", data, 0)[0]

    # Sanity check: if count implies more data than available, the format
    # has not been fully reverse-engineered yet. Return empty list safely.
    # Each event is at minimum 6 bytes (2 id + 1 type + 2 year + 1 text+null).
    if count > len(data) // 6:
        return events

    offset = 2
    for _ in range(count):
        if offset >= len(data):
            break

        try:
            # Read event ID
            if offset + 2 > len(data):
                break
            event_id = struct.unpack_from("<H", data, offset)[0]
            offset += 2

            # Read event type
            if offset >= len(data):
                break
            event_type = data[offset]
            offset += 1

            # Accept any event type (Stars! has many event codes)
            # Known: GENERIC=0, NOTIFICATION=1; others are undocumented

            # Read year
            if offset + 2 > len(data):
                break
            year = struct.unpack_from("<H", data, offset)[0]
            offset += 2

            # Clamp year to valid game range for Event dataclass validation
            year = max(2300, min(2700, year))

            # Read text (null-terminated)
            text_end = data.find(b"\x00", offset)
            if text_end == -1:
                # No null terminator found, read to end
                text = data[offset:].decode("latin-1", errors="ignore")
                offset = len(data)
            else:
                text = data[offset:text_end].decode("latin-1", errors="ignore")
                offset = text_end + 1

            # Normalize event_type to known enum values; store raw type for
            # unknown codes so we don't lose information
            normalized_type = event_type if event_type in (
                EventType.GENERIC, EventType.NOTIFICATION
            ) else EventType.GENERIC

            # Only create Event if text is non-empty (dataclass requires it)
            if text:
                event = Event(
                    event_id=event_id,
                    event_type=normalized_type,
                    year=year,
                    text=text,
                )
                events.append(event)

        except (ValueError, struct.error):
            # If parsing fails at any point, stop and return what we have
            break

    return events


def encode_events(events: List[Event]) -> bytes:
    """Serialize events back to binary block data.

    Args:
        events: List of Event objects to encode

    Returns:
        Raw block data (bytes)
    """
    data = bytearray(2)
    struct.pack_into("<H", data, 0, len(events))

    for event in events:
        # Event ID (uint16 LE)
        data.extend(struct.pack("<H", event.event_id))

        # Type byte
        data.append(event.event_type)

        # Year (uint16 LE)
        data.extend(struct.pack("<H", event.year))

        # Text (null-terminated)
        text_bytes = event.text.encode("latin-1", errors="ignore")
        data.extend(text_bytes)
        data.append(0x00)  # null terminator

    return bytes(data)


__all__ = [
    "BLOCK_TYPE_EVENT",
    "EventType",
    "Event",
    "decode_events",
    "encode_events",
]
