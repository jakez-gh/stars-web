"""Stars! file block decryptor.

Derives PRNG seeds from file header metadata (salt, game_id, turn, player)
and performs XOR decryption of block data.

Reference: stars-4x/starsapi-python by raptor (2014).
The Stars! primes table entry at index 55 is 279 (not prime) — this is
intentional and matches the original Stars! binary.
"""

from stars_web.stars_random import StarsRandom


class Decryptor:
    """Decrypts Stars! file blocks using the game's PRNG-based XOR cipher."""

    # First 64 primes starting from 3 (with 279 instead of 269 at index 55).
    # This table is from the original Stars! binary and must be preserved exactly.
    primes = [
        3,
        5,
        7,
        11,
        13,
        17,
        19,
        23,
        29,
        31,
        37,
        41,
        43,
        47,
        53,
        59,
        61,
        67,
        71,
        73,
        79,
        83,
        89,
        97,
        101,
        103,
        107,
        109,
        113,
        127,
        131,
        137,
        139,
        149,
        151,
        157,
        163,
        167,
        173,
        179,
        181,
        191,
        193,
        197,
        199,
        211,
        223,
        227,
        229,
        233,
        239,
        241,
        251,
        257,
        263,
        279,
        271,
        277,
        281,
        283,
        293,
        307,
        311,
        313,
    ]

    def __init__(self):
        self.random: StarsRandom | None = None

    def init_decryption(
        self,
        salt: int,
        game_id: int,
        turn: int,
        player_index: int,
        shareware: bool,
    ) -> None:
        """Initialize the PRNG from file header parameters.

        The salt field (11 bits) is split to select two primes as seeds:
        - Bits 0-4 → index1 (lower 5 bits)
        - Bits 5-9 → index2 (middle 5 bits)
        - Bit 10   → if set, index1 += 32; else index2 += 32

        Init rounds = (part4 * part3 * part2) + part1
        where:
            part1 = 1 if shareware else 0
            part2 = (player_index & 3) + 1
            part3 = (turn & 3) + 1
            part4 = (game_id & 3) + 1
        """
        index1 = salt & 0x1F
        index2 = (salt >> 5) & 0x1F

        if (salt >> 10) == 1:
            index1 += 32
        else:
            index2 += 32

        part1 = 1 if shareware else 0
        part2 = (player_index & 0x3) + 1
        part3 = (turn & 0x3) + 1
        part4 = (game_id & 0x3) + 1

        rounds = (part4 * part3 * part2) + part1

        seed1 = self.primes[index1]
        seed2 = self.primes[index2]

        self.random = StarsRandom(seed1, seed2, rounds)

    def decrypt_bytes(self, data: bytearray) -> bytearray:
        """Decrypt a block of data using XOR with PRNG output.

        Data is padded to a 4-byte boundary, XOR'd in 4-byte chunks
        (little-endian), then trimmed back to original length.
        """
        if not data:
            return bytearray()

        size = len(data)
        padded_size = (size + 3) & ~3
        padding = padded_size - size

        # Pad with zeros
        for _ in range(padding):
            data.append(0x00)

        decrypted = bytearray()

        # Process 4 bytes at a time
        for i in range(0, padded_size, 4):
            chunk = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16) | (data[i + 3] << 24)

            decrypted_chunk = chunk ^ self.random.next_random()

            decrypted.append(decrypted_chunk & 0xFF)
            decrypted.append((decrypted_chunk >> 8) & 0xFF)
            decrypted.append((decrypted_chunk >> 16) & 0xFF)
            decrypted.append((decrypted_chunk >> 24) & 0xFF)

        # Remove padding from both input (restore) and output
        for _ in range(padding):
            data.pop()
            decrypted.pop()

        return decrypted
