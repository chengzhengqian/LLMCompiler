=== INTENT ===
`fock-basis` provides the occupation-number (Fock) basis for a small spin-½ fermionic system described by L spin-orbitals (l = 1, …, L). Each spin-orbital already encodes both spatial and spin character, so no separate spin-up/spin-down bookkeeping is needed. A basis state is a single `UInt` whose L bits record which spin-orbitals are occupied. Given a fixed total particle number N, the unit enumerates all C(L, N) valid configurations and offers O(1) bidirectional lookup between a state and its index in the enumeration. The full Hilbert space is 2^L dimensional; this unit restricts to the N-particle sector. The primary consumers are `fermion-ops` (which must map an operator-applied state back to an index) and `op-matrix` (which builds dense matrices in a fixed sector).

=== SPEC ===
## Representation

A Fock state is a `UInt` with exactly L meaningful bits (L = number of spin-orbitals):

- Bit (l−1) is 1 iff spin-orbital l (1-indexed, l = 1…L) is occupied.
- Bits ≥ L are always 0.

The basis is the set of all such `UInt` values with exactly N bits set among the L low bits. The size of the basis is C(L, N).

The `FockBasis` struct holds the parameters L, N and a precomputed lookup structure enabling O(1) state→index and O(1) index→state.

## Interface

```julia
struct FockBasis
    L::Int
    N::Int
    # (internal fields: lookup table, states array, etc.)
end

FockBasis(L::Int, N::Int)                  # constructor; builds the basis
nstates(fb::FockBasis)::Int
state_at(fb::FockBasis, i::Int)::UInt
index_of(fb::FockBasis, s::UInt)::Int
all_states(fb::FockBasis)::Vector{UInt}
```

## Semantics

**Constructor `FockBasis(L, N)`**

- Precondition: `L ≥ 1`, `0 ≤ N ≤ L`. Violation throws `ArgumentError`.
- Builds the full enumeration and internal lookup in deterministic order (see below).

**Ordering**

The C(L, N) states are ordered lexicographically by the sorted tuple of 1-indexed occupied spin-orbital positions. Example: L=4, N=2 gives the order (1,2), (1,3), (1,4), (2,3), (2,4), (3,4).

The internal 0-based index is the 0-based lexicographic rank of the state's occupied-position tuple among all C(L, N) combinations.

The public `index_of` and `state_at` use **1-based** indices (Julia convention): `public_index = internal_rank + 1`.

**`nstates(fb)`**

Returns C(L, N).

**`state_at(fb, i)`**

- `i` must satisfy `1 ≤ i ≤ nstates(fb)`. Out-of-range throws `BoundsError`.
- Returns the `UInt` state at 1-based position `i`.

**`index_of(fb, s)`**

- `s` must be a valid member of the basis: exactly N bits set among bits 0…L−1, and bits ≥ L all zero. If not, throws `ArgumentError`.
- Returns the 1-based `Int` index of `s` in the enumeration.

**`all_states(fb)`**

Returns a `Vector{UInt}` of length `nstates(fb)` containing all states in enumeration order (element *i* equals `state_at(fb, i)`).

## Pinned examples

```julia
# L=4, N=2 → C(4,2) = 6 states
fb = FockBasis(4, 2)
nstates(fb) == 6

# i=1: {1,2} → bits 0,1 → 0b0011 == 3
state_at(fb, 1) == 3u0

# i=2: {1,3} → bits 0,2 → 0b0101 == 5
state_at(fb, 2) == 5u0

# i=3: {1,4} → bits 0,3 → 0b1001 == 9
state_at(fb, 3) == 9u0

# i=4: {2,3} → bits 1,2 → 0b0110 == 6
state_at(fb, 4) == 6u0

# i=5: {2,4} → bits 1,3 → 0b1010 == 10
state_at(fb, 5) == 10u0

# i=6: {3,4} → bits 2,3 → 0b1100 == 12
state_at(fb, 6) == 12u0

# Round-trip
index_of(fb, 3u0)  == 1
index_of(fb, 5u0)  == 2
index_of(fb, 9u0)  == 3
index_of(fb, 6u0)  == 4
index_of(fb, 10u0) == 5
index_of(fb, 12u0) == 6

# Invalid state: 0b0001 = 1 has only 1 bit set, not N=2
# @test_throws ArgumentError index_of(fb, 1u0)

# L=3, N=1 → C(3,1) = 3 states
fb2 = FockBasis(3, 1)
nstates(fb2) == 3
state_at(fb2, 1) == 1u0   # {1} → bit 0
state_at(fb2, 2) == 2u0   # {2} → bit 1
state_at(fb2, 3) == 4u0   # {3} → bit 2

# L=3, N=3 → C(3,3) = 1 state
fb3 = FockBasis(3, 3)
nstates(fb3) == 1
state_at(fb3, 1) == 7u0   # {1,2,3} → bits 0,1,2

# L=4, N=0 → C(4,0) = 1 state
fb4 = FockBasis(4, 0)
nstates(fb4) == 1
state_at(fb4, 1) == 0u0
```

## Invariants

- For every valid `fb` and every `i` in `1:nstates(fb)`:
  `index_of(fb, state_at(fb, i)) == i`
- For every valid `fb` and every `s` in `all_states(fb)`:
  `count_ones(s & ((1u << L) - 1u)) == N`
- `all_states(fb)` has length `nstates(fb)` and is a permutation of the set of all valid states.
- `FockBasis(L, 0)` has exactly 1 state: `state_at(fb, 1) == 0u0`.
- `FockBasis(L, L)` has exactly 1 state: `state_at(fb, 1) == (1u << L) - 1u`.
- Bit-level: for any state `s` in the basis, `s >> L == 0` (no extraneous bits).

## Out of scope

- Multi-species or higher-spin fermions.
- Variable-particle-number (Grand canonical) sectors.
- Second-quantized operator algebra (handled by `fermion-ops`).
- Matrix construction and storage (handled by `op-matrix`).
- Parallel / distributed enumeration.
- States with more than one particle per spin-orbital (bosons or multi-occupancy).
- Spin-resolved particle counts (N↑, N↓); spin is absorbed into the spin-orbital label.

=== CHOICES ===
- Renamed the orbital-count parameter from `N` to `L` to match the user's notation "L spin-orbital" and avoid confusion with the particle count `N`.
- Removed `Nup` and `Ndown` parameters; the basis is now indexed only by total particle number `N` across `L` spin-orbitals.
- Simplified the bit encoding to a single contiguous block of L bits (bit l−1 ↔ spin-orbital l) rather than two separate halves.
- Simplified the ordering to a single lexicographic rank over C(L, N) combinations (no composite up_rank/down_rank formula).

=== QUESTIONS ===
- The user said "The Hilbert space is 2^L dimension." Does the unit still restrict to a **fixed** particle number N (so the basis has C(L, N) states), or should it enumerate the **full** 2^L-dimensional Hilbert space (all occupations, all particle numbers)? The current plan (and the original) assume fixed-N sectors; the 2^L phrasing may simply be describing the total space in which the Fock states live. I have kept the fixed-N interpretation.
