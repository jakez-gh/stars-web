"""Stars! custom string encoding/decoding.

Stars! uses a nibble-based text encoding to compress common characters.

Encoding rules (from starsapi Util.java, raptor 2014):
  nibbles 0-A: 1-nibble, index into " aehilnorst"
  nibble B+x:  2-nibble, index into "ABCDEFGHIJKLMNOP"
  nibble C+x:  2-nibble, index into "QRSTUVWXYZ012345"
  nibble D+x:  2-nibble, index into "6789bcdfgjkmpquv"
  nibble E+x:  2-nibble, index into "wxyz+-,!.?:;'*%$"
  nibble F+xy: 3-nibble, raw ASCII with swapped nibbles

The first byte of an encoded string is the byte count of the
encoded data that follows.
"""

# Lookup tables for nibble decoding
_ONE_NIBBLE = " aehilnorst"  # nibbles 0x0 through 0xA
_TWO_NIBBLE = {
    0xB: "ABCDEFGHIJKLMNOP",
    0xC: "QRSTUVWXYZ012345",
    0xD: "6789bcdfgjkmpquv",
    0xE: "wxyz+-,!.?:;'*%$",
}


def decode_stars_string(data: bytes, offset: int = 0) -> tuple[str, int]:
    """Decode a Stars!-encoded string from a byte buffer.

    Args:
        data: Raw byte buffer containing the encoded string.
        offset: Starting position of the length byte.

    Returns:
        Tuple of (decoded_text, bytes_consumed) where bytes_consumed
        includes the length byte.
    """
    byte_size = data[offset]
    encoded = data[offset + 1 : offset + 1 + byte_size]

    # Convert bytes to nibble stream (hex digits)
    nibbles: list[int] = []
    for b in encoded:
        nibbles.append((b >> 4) & 0x0F)
        nibbles.append(b & 0x0F)

    result: list[str] = []
    i = 0
    nibble_count = byte_size * 2  # total nibbles available

    while i < nibble_count:
        n = nibbles[i]

        if n <= 0xA:
            # 1-nibble character
            result.append(_ONE_NIBBLE[n])
            i += 1

        elif n == 0xF:
            # 3-nibble raw ASCII: F + lo_nibble + hi_nibble
            if i + 2 >= nibble_count:
                break  # not enough nibbles left (padding)
            lo = nibbles[i + 1]
            hi = nibbles[i + 2]
            char_code = (hi << 4) | lo
            result.append(chr(char_code))
            i += 3

        elif n in _TWO_NIBBLE:
            # 2-nibble encoded character
            if i + 1 >= nibble_count:
                break
            idx = nibbles[i + 1]
            result.append(_TWO_NIBBLE[n][idx])
            i += 2

        else:
            # Unknown nibble — skip
            i += 1

    return "".join(result), 1 + byte_size
