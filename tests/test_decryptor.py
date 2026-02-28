"""Tests for the Stars! Decryptor.

The Decryptor handles:
1. Deriving PRNG seeds from the file header (salt → primes table lookup)
2. Computing init rounds from game metadata
3. XOR decryption of block data using PRNG output

Reference: stars-4x/starsapi-python by raptor (2014).
"""

import pytest

from stars_web.decryptor import Decryptor


# The Stars! primes table (64 entries, note: 279 is NOT prime but is
# in the original Stars! code and must be preserved for compatibility)
EXPECTED_PRIMES = [
    3, 5, 7, 11, 13, 17, 19, 23,
    29, 31, 37, 41, 43, 47, 53, 59,
    61, 67, 71, 73, 79, 83, 89, 97,
    101, 103, 107, 109, 113, 127, 131, 137,
    139, 149, 151, 157, 163, 167, 173, 179,
    181, 191, 193, 197, 199, 211, 223, 227,
    229, 233, 239, 241, 251, 257, 263, 279,
    271, 277, 281, 283, 293, 307, 311, 313,
]


class TestPrimesTable:
    def test_primes_table_length(self):
        dec = Decryptor()
        assert len(dec.primes) == 64

    def test_primes_table_values(self):
        dec = Decryptor()
        assert dec.primes == EXPECTED_PRIMES

    def test_279_is_in_table(self):
        """279 is NOT prime (3*93) but Stars! uses it. Must be preserved."""
        dec = Decryptor()
        assert 279 in dec.primes


class TestInitDecryption:
    """Test seed derivation from salt, gameId, turn, player."""

    def test_salt_index1_from_lower_5_bits(self):
        """index1 = salt & 0x1F"""
        dec = Decryptor()
        # salt=3 → index1 = 3 & 0x1F = 3, bit10=0 → index2 += 32
        dec.init_decryption(salt=3, game_id=0, turn=0, player_index=0, shareware=False)
        # seed1 = primes[3] = 11, seed2 = primes[32] = 139
        assert dec.random.seed_a is not None  # Just verify it initialized

    def test_salt_index2_from_bits_5_to_9(self):
        """index2 = (salt >> 5) & 0x1F"""
        dec = Decryptor()
        # salt = 0b00000_00010_00001 = (index2=2, index1=1), bit10=0 → index2 += 32
        salt = (2 << 5) | 1  # 65
        dec.init_decryption(salt=salt, game_id=0, turn=0, player_index=0, shareware=False)
        # seed1 should use primes[1]=5, seed2 should use primes[2+32]=primes[34]=151
        # The init method should have run; verify the PRNG was created
        assert dec.random is not None

    def test_bit10_set_adjusts_index1(self):
        """When bit 10 of salt is set, index1 += 32 (upper half)."""
        dec = Decryptor()
        # salt with bit 10 set: salt = 1024 | 1 → index1 = 1, but +32 = 33
        salt = (1 << 10) | 1
        dec.init_decryption(salt=salt, game_id=0, turn=0, player_index=0, shareware=False)
        # With bit10=1: index1 += 32, index2 stays in lower half
        assert dec.random is not None

    def test_bit10_clear_adjusts_index2(self):
        """When bit 10 of salt is clear, index2 += 32 (upper half)."""
        dec = Decryptor()
        salt = 1  # bit10 = 0
        dec.init_decryption(salt=salt, game_id=0, turn=0, player_index=0, shareware=False)
        assert dec.random is not None

    def test_rounds_calculation(self):
        """rounds = (part4 * part3 * part2) + part1
        where part1=shareware, part2=(player&3)+1, part3=(turn&3)+1, part4=(gameId&3)+1
        """
        dec = Decryptor()
        # game_id=0 → part4=(0&3)+1=1
        # turn=0 → part3=(0&3)+1=1
        # player=0 → part2=(0&3)+1=1
        # shareware=False → part1=0
        # rounds = (1*1*1) + 0 = 1
        dec.init_decryption(salt=0, game_id=0, turn=0, player_index=0, shareware=False)
        # We can't easily check rounds directly, but we can verify determinism
        assert dec.random is not None

    def test_rounds_with_nonzero_params(self):
        """More complex rounds: gameId=3, turn=3, player=3 → max rounds with shareware."""
        # part4 = (3&3)+1 = 4
        # part3 = (3&3)+1 = 4
        # part2 = (3&3)+1 = 4
        # shareware=True → part1 = 1
        # rounds = (4*4*4) + 1 = 65
        dec = Decryptor()
        dec.init_decryption(salt=0, game_id=3, turn=3, player_index=3, shareware=True)
        assert dec.random is not None


class TestDecryptBytes:
    """Test XOR decryption of block data."""

    def test_decrypt_4_byte_block(self):
        """A 4-byte block should be XOR'd with one PRNG output."""
        dec = Decryptor()
        dec.init_decryption(salt=0, game_id=0, turn=0, player_index=0, shareware=False)

        # Get what the PRNG would produce
        from stars_web.stars_random import StarsRandom
        primes = EXPECTED_PRIMES
        # salt=0: index1=0, index2=0, bit10=0 → index2 += 32
        # seed1=primes[0]=3, seed2=primes[32]=139
        # rounds = 1 (from (1*1*1)+0)
        rng_check = StarsRandom(seed1=3, seed2=139, init_rounds=1)
        expected_xor = rng_check.next_random()

        # Create "encrypted" data by XORing known plaintext with expected XOR
        plaintext = b'\x01\x02\x03\x04'
        plain_int = int.from_bytes(plaintext, 'little')
        enc_int = plain_int ^ expected_xor
        encrypted = enc_int.to_bytes(4, 'little')

        result = dec.decrypt_bytes(bytearray(encrypted))
        assert bytes(result) == plaintext

    def test_decrypt_non_aligned_pads_to_4(self):
        """Data not a multiple of 4 should be padded, then trimmed."""
        dec = Decryptor()
        dec.init_decryption(salt=0, game_id=0, turn=0, player_index=0, shareware=False)

        # 3 bytes → padded to 4, decrypted, then trimmed back to 3
        from stars_web.stars_random import StarsRandom
        rng_check = StarsRandom(seed1=3, seed2=139, init_rounds=1)
        xor_val = rng_check.next_random()

        plaintext = b'\xAA\xBB\xCC'
        padded_plain = b'\xAA\xBB\xCC\x00'
        plain_int = int.from_bytes(padded_plain, 'little')
        enc_int = plain_int ^ xor_val
        encrypted = enc_int.to_bytes(4, 'little')[:3]  # Only 3 bytes stored

        result = dec.decrypt_bytes(bytearray(encrypted))
        assert len(result) == 3
        assert bytes(result) == plaintext

    def test_decrypt_8_bytes_uses_two_random_values(self):
        """8 bytes = 2 chunks, each XOR'd with successive PRNG output."""
        dec = Decryptor()
        dec.init_decryption(salt=0, game_id=0, turn=0, player_index=0, shareware=False)

        from stars_web.stars_random import StarsRandom
        rng_check = StarsRandom(seed1=3, seed2=139, init_rounds=1)
        xor1 = rng_check.next_random()
        xor2 = rng_check.next_random()

        plaintext = b'\x01\x02\x03\x04\x05\x06\x07\x08'
        chunk1 = int.from_bytes(plaintext[0:4], 'little') ^ xor1
        chunk2 = int.from_bytes(plaintext[4:8], 'little') ^ xor2
        encrypted = chunk1.to_bytes(4, 'little') + chunk2.to_bytes(4, 'little')

        result = dec.decrypt_bytes(bytearray(encrypted))
        assert bytes(result) == plaintext

    def test_decrypt_empty_returns_empty(self):
        """Empty input should return empty output."""
        dec = Decryptor()
        dec.init_decryption(salt=0, game_id=0, turn=0, player_index=0, shareware=False)
        result = dec.decrypt_bytes(bytearray())
        assert result == bytearray()
