=== INTENT ===
`fock-basis` provides the occupation-number (Fock) basis for a small spin-½ fermionic system with N spatial orbitals. Each basis state is encoded as a single `UInt` whose 2N bits record which orbitals are occupied by spin-up and spin-down electrons. Given fixed particle numbers N↑ and N↓, the unit enumerates all valid configurations and offers O(1) bidirectional lookup between a state and its index in the enumeration. The primary consumers are `fermion-ops` (which must map an operator-applied state back to an index) and `op-matrix` (which builds dense matrices in a fixed sector).

=== SPEC ===
## Representation

A Fock state is a `UInt` with exactly 2N meaningful bits (N = number of spatial orbitals):

- Bits 0 … N−1 encode spin-up occupation. Bit *i* is 1 iff orbital *i+1* (1-indexed) is occupied by a spin-up electron.
- Bits N … 2N−1 encode spin-down occupation. Bit N+*i* is 1 iff orbital *i+1* is occupied by a spin-down electron.
- Bits ≥ 2N are always 0.

The basis is the set of all such `UInt` values with exactly Nup bits set in the spin-up half and exactly Ndown bits set in the spin-down half. The size of the basis is C(N, Nup) × C(N, Ndown).

The `FockBasis` struct holds the parameters N, Nup, Ndown and a precomputed lookup structure enabling O(1) state→index and O(1) index→state.

## Interface

```julia
struct FockBasis
    N::Int
    Nup::Int
    Ndown::Int
    # (internal fields: lookup table, states array, etc.)
end

FockBasis(N::Int, Nup::Int, Ndown::Int)  # constructor; builds the basis

nstates(fb::FockBasis)::Int
state_at(fb::FockBasis, i::Int)::UInt
index_of(fb::FockBasis, s::UInt)::Int
all_states(fb::FockBasis)::Vector{UInt}
```

## Semantics

**Constructor `FockBasis(N, Nup, Ndown)`**

- Precondition: `N ≥ 1`, `0 ≤ Nup ≤ N`, `0 ≤ Ndown ≤ N`. Violation throws `ArgumentError`.
- Builds the full enumeration and internal lookup in deterministic order (see below).

**Ordering**

Within each spin sector, the C(N, k) states are ordered lexicographically by the sorted tuple of 1-indexed occupied-orbital positions. Example: N=3, k=2 gives the order (1,2), (1,3), (2,3).

The overall basis index (0-based internally) is:

  base_index = up_rank × C(N, Ndown) + down_rank

where `up_rank` and `down_rank` are the 0-based lexicographic ranks within their respective sectors.

The public `index_of` and `state_at` use **1-based** indices (Julia convention): `public_index = base_index + 1`.

**`nstates(fb)`**

Returns C(N, Nup) × C(N, Ndown).

**`state_at(fb, i)`**

- `i` must satisfy `1 ≤ i ≤ nstates(fb)`. Out-of-range throws `BoundsError`.
- Returns the `UInt` state at 1-based position `i`.

**`index_of(fb, s)`**

- `s` must be a valid member of the basis (correct Nup, Ndown, and no bits ≥ 2N set). If not, throws `ArgumentError`.
- Returns the 1-based `Int` index of `s` in the enumeration.

**`all_states(fb)`**

Returns a `Vector{UInt}` of length `nstates(fb)` containing all states in enumeration order (element *i* equals `state_at(fb, i)`).

## Pinned examples

```julia
# N=2, Nup=1, Ndown=1  →  C(2,1)*C(2,1) = 4 states
fb = FockBasis(2, 1, 1)

nstates(fb) == 4

# Spin-up ranks: {1}→0, {2}→1
# Spin-down ranks: {1}→0, {2}→1
# base_index = up_rank * 2 + down_rank

# i=1: up={1}, down={1}  →  bit0=1, bit2=1  →  0b0101 == 5
state_at(fb, 1) == 5u0

# i=2: up={1}, down={2}  →  bit0=1, bit3=1  →  0b1001 == 9
state_at(fb, 2) == 9u0

# i=3: up={2}, down={1}  →  bit1=1, bit2=1  →  0b0110 == 6
state_at(fb, 3) == 6u0

# i=4: up={2}, down={2}  →  bit1=1, bit3=1  →  0b1010 == 10
state_at(fb, 4) == 10u0

# Round-trip
index_of(fb, 5u0)  == 1
index_of(fb, 9u0)  == 2
index_of(fb, 6u0)  == 3
index_of(fb, 10u0) == 4

# Invalid state (Nup=0, should be Nup=1)
# state 0b0010 = 2 has 0 up-bits, 1 down-bit → not in basis
# @test_throws ArgumentError index_of(fb, 2u0)

# N=3, Nup=2, Ndown=1 → C(3,2)*C(3,1) = 3*3 = 9
fb3 = FockBasis(3, 2, 1)
nstates(fb3) == 9

# i=1: up={1,2}, down={1} → bit0=1,bit1=1,bit3=1 → 0b01011 == 11
state_at(fb3, 1) == 11u0

# i=2: up={1,2}, down={2} → bit0=1,bit1=1,bit4=1 → 0b101011 == 43
state_at(fb3, 2) == 43u0

# i=4: up={1,3}, down={1} → bit0=1,bit2=1,bit3=1 → 0b011011 == 27
state_at(fb3, 4) == 27u0
```

## Invariants

- For every valid `fb` and every `i` in `1:nstates(fb)`:
  `index_of(fb, state_at(fb, i)) == i`
- For every valid `fb` and every `s` in `all_states(fb)`:
  `count_ones(s & ((1 << N) - 1)) == Nup`  (spin-up popcount)
  `count_ones((s >> N) & ((1 << N) - 1)) == Ndown`  (spin-down popcount)
- `all_states(fb)` has length `nstates(fb)` and is a permutation of the set of all valid states.
- `FockBasis(N, 0, 0)` has exactly 1 state: `state_at(fb, 1) == 0u0`.
- For `N ≥ 1`: `nstates(FockBasis(N, 0, 0)) == 1`.
- Bit-level: for any state `s` in the basis, `s >> (2N) == 0` (no extraneous bits).

## Out of scope

- Multi-species or higher-spin fermions.
- Variable-particle-number (Grand canonical) sectors.
- Second-quantized operator algebra (handled by `fermion-ops`).
- Matrix construction and storage (handled by `op-matrix`).
- Parallel / distributed enumeration.
- States with more than one particle per orbital (bosons or multi-occupancy).

=== CHOICES ===
- **N interpreted as spatial orbitals (total modes = 2N):** The human input mentions N↑ and N↓, which only make sense with a spin structure. I chose N = number of spatial sites, so the state has 2N bits (N up + N down). An alternative would be N = total modes with no spin split, but then N↑/N↓ are ambiguous.
- **Spin-up occupies the lower N bits, spin-down the upper N bits:** This makes extraction via `s & mask` and `s >> N` natural and matches the convention of writing up-orbitals first.
- **Lexicographic order on sorted 1-indexed occupied-orbital tuples, spin-up as outer index:** This gives a deterministic, easily verifiable ordering. An alternative (numerical order on the full UInt) would mix spins and be harder to reason about for the consumers.
- **1-based public indices (Julia convention):** `state_at` and `index_of` use 1-based indexing, consistent with Julia's array conventions and the downstream `op-matrix` consumer.
- **`index_of` throws `ArgumentError` for invalid states rather than returning a sentinel:** Avoids silent errors; the consumer gets an immediate signal that a bug occurred (e.g., operator applied to wrong sector).
- **Nup and Ndown are mandatory (no default):** The unit is designed for fixed-sector use. Enumerating all 2^(2N) states is a different (and much larger) problem; requiring explicit values keeps the interface honest.

=== QUESTIONS ===
none
