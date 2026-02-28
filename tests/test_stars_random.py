"""Tests for the Stars! PRNG (L'Ecuyer Combined LCG).

Reference: stars-4x/starsapi-python by raptor.
The Stars! PRNG uses a combined linear congruential generator with two seeds.
"""

import pytest

from stars_web.stars_random import StarsRandom


class TestStarsRandomInit:
    """Test PRNG initialization."""

    def test_seeds_stored(self):
        rng = StarsRandom(seed1=3, seed2=5, init_rounds=0)
        assert rng.seed_a == 3
        assert rng.seed_b == 5

    def test_zero_init_rounds_no_advance(self):
        """With 0 init rounds, seeds should remain unchanged."""
        rng = StarsRandom(seed1=7, seed2=11, init_rounds=0)
        assert rng.seed_a == 7
        assert rng.seed_b == 11


class TestStarsRandomNextRandom:
    """Test the L'Ecuyer combined LCG algorithm.

    Algorithm per Stars! decompilation:
        seedApartA = (seedA % 53668) * 40014
        seedApartB = (seedA // 53668) * 12211
        newSeedA = seedApartA - seedApartB
        if newSeedA < 0: newSeedA += 0x7fffffab

        seedBpartA = (seedB % 52774) * 40692
        seedBpartB = (seedB // 52774) * 3791
        newSeedB = seedBpartA - seedBpartB
        if newSeedB < 0: newSeedB += 0x7fffff07

        result = seedA - seedB
        if seedA < seedB: result += 2^32
    """

    def test_first_random_with_small_seeds(self):
        """Verify first random output with seeds 3 and 5."""
        rng = StarsRandom(seed1=3, seed2=5, init_rounds=0)

        # Manual calculation:
        # seedA=3: partA = (3 % 53668) * 40014 = 3 * 40014 = 120042
        #          partB = (3 // 53668) * 12211 = 0 * 12211 = 0
        #          newSeedA = 120042
        # seedB=5: partA = (5 % 52774) * 40692 = 5 * 40692 = 203460
        #          partB = (5 // 52774) * 3791 = 0 * 3791 = 0
        #          newSeedB = 203460
        # result = 120042 - 203460 = -83418, since seedA < seedB: + 2^32
        # result = 4294883878
        result = rng.next_random()
        assert result == 4294883878

    def test_seeds_updated_after_call(self):
        """Seeds should be updated after calling next_random."""
        rng = StarsRandom(seed1=3, seed2=5, init_rounds=0)
        rng.next_random()
        assert rng.seed_a == 120042
        assert rng.seed_b == 203460

    def test_second_random_deterministic(self):
        """Second call should use updated seeds."""
        rng = StarsRandom(seed1=3, seed2=5, init_rounds=0)
        rng.next_random()
        second = rng.next_random()

        # Verified against reference implementation output
        assert second == 2966616635

    def test_init_rounds_advance_state(self):
        """Init rounds should advance the PRNG state."""
        rng_no_rounds = StarsRandom(seed1=3, seed2=5, init_rounds=0)
        rng_with_rounds = StarsRandom(seed1=3, seed2=5, init_rounds=2)

        # After 2 init rounds, the seeds should match calling next_random twice
        rng_no_rounds.next_random()
        rng_no_rounds.next_random()

        assert rng_with_rounds.seed_a == rng_no_rounds.seed_a
        assert rng_with_rounds.seed_b == rng_no_rounds.seed_b

    def test_negative_seed_a_correction(self):
        """When newSeedA is negative, should add 0x7fffffab."""
        # seed=53668: partA = (53668 % 53668) * 40014 = 0
        #             partB = (53668 // 53668) * 12211 = 12211
        #             newSeedA = -12211, corrected: -12211 + 0x7fffffab = 2147471352
        rng = StarsRandom(seed1=53668, seed2=5, init_rounds=0)
        rng.next_random()
        assert rng.seed_a == 2147471352

    def test_result_always_unsigned_32bit(self):
        """Result should always fit in unsigned 32-bit range."""
        rng = StarsRandom(seed1=3, seed2=5, init_rounds=0)
        for _ in range(100):
            result = rng.next_random()
            assert 0 <= result < 2**32
