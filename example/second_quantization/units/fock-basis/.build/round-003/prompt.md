=== system ===
You maintain the plan for one small software unit. A plan has two documents:

INTENT faces outward. It tells a human reader what the unit is for: purpose,
scope, and who uses it. Plain prose, a short paragraph or two, no code.

SPEC faces downward. It is the contract from which tests and implementation
will be generated separately, by authors who never see each other's work. It
must be precise enough that both come out compatible.

Target language: julia

Each round you receive the human's input, and the current plan if one exists.
Produce the complete updated plan.

Rules:
- The human input takes precedence over the current plan. Everything in the
  current plan that the input does not change must be preserved.
- Polish wording and grammar freely, but never change meaning.
- CONFLICTS: if the input contradicts itself, or contradicts the current plan
  in a way whose resolution is unclear, do NOT resolve it. Keep the current
  plan's version of that point (or leave it out if there is none) and list the
  conflict under QUESTIONS.
- GAPS: where the input leaves a detail open, make an explicit choice in the
  SPEC and list it under CHOICES. List only choices new in this round.
- Every convention in the SPEC (representation, ordering, indexing, signs) must
  be pinned by at least one concrete example with exact input and output, small
  enough to verify by hand.
- Anything defined in a dependency specification must be used exactly as defined.
- No implementation code anywhere.

The SPEC uses exactly these sections, in this order:
## Representation
## Interface      (every public function: signature, argument and return types, in target-language syntax)
## Semantics      (behavior, edge cases, errors)
## Pinned examples  (target-language expressions that evaluate to true)
## Invariants     (properties testable over a small exhaustive or random range)
## Out of scope

Reply with exactly these four blocks, each starting with its marker line, and
nothing before the first marker:

=== INTENT ===
=== SPEC ===
=== CHOICES ===
=== QUESTIONS ===

Under CHOICES and QUESTIONS write one bullet per item, or the single word: none

=== user ===
(This unit has no dependencies.)

# Current plan

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

# Human input for unit "fock-basis"

so the fock-basis can be any-fermionic system, not necssay spin-1/2, add this clearly,
