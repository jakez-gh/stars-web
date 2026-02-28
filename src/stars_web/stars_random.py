"""Stars! PRNG implementation (L'Ecuyer Combined Linear Congruential Generator).

The Stars! game uses this PRNG for XOR encryption of game file blocks.
Reverse-engineered from the Stars! binary; reference implementation from
stars-4x/starsapi-python by raptor (2014).

The algorithm is a combined LCG with two independent generators:
- Generator A: multiplier=40014, modulus=2147483563 (0x7fffffab)
- Generator B: multiplier=40692, modulus=2147483399 (0x7fffff07)
"""


class StarsRandom:
    """Stars! pseudo-random number generator.

    Uses L'Ecuyer's combined linear congruential method with two seeds.
    Output is an unsigned 32-bit integer.
    """

    def __init__(self, seed1: int, seed2: int, init_rounds: int = 0):
        self.seed_a = seed1
        self.seed_b = seed2

        # Advance state for init_rounds
        for _ in range(init_rounds):
            self.next_random()

    def next_random(self) -> int:
        """Generate the next pseudo-random number (unsigned 32-bit).

        Updates both seeds using their respective LCG parameters,
        then combines them via subtraction.
        """
        # Generator A: a=40014, m=2147483563, q=53668, r=12211
        part_a1 = (self.seed_a % 53668) * 40014
        part_a2 = (self.seed_a // 53668) * 12211
        new_seed_a = part_a1 - part_a2
        if new_seed_a < 0:
            new_seed_a += 0x7FFFFFAB  # 2147483563

        # Generator B: a=40692, m=2147483399, q=52774, r=3791
        part_b1 = (self.seed_b % 52774) * 40692
        part_b2 = (self.seed_b // 52774) * 3791
        new_seed_b = part_b1 - part_b2
        if new_seed_b < 0:
            new_seed_b += 0x7FFFFF07  # 2147483399

        self.seed_a = new_seed_a
        self.seed_b = new_seed_b

        # Combine generators
        result = self.seed_a - self.seed_b
        if self.seed_a < self.seed_b:
            result += 0x100000000  # 2^32

        return result
