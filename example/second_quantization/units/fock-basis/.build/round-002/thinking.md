The user wants to change the Fock basis to use L spin-orbitals instead of N spatial orbitals with separate spin-up/spin-down sectors. This is a fundamental change:

- Instead of N spatial orbitals with N↑ and N↓ particles (where spin is tracked separately), we now have L spin-orbitals (l=1,...,L) where each spin-orbital is a distinct entity. The Hilbert space is 2^L dimensional (each spin-orbital is either occupied or not).
- The "spin-up/spin-down" distinction is hidden in the single index l. So there's no longer a separate Nup/Ndown in the interface.
- The basis is still for fixed particle number (total N particles across L spin-orbitals), since the original intent mentions "fixed particle numbers" and the basis is the subset of states with exactly N occupied spin-orbitals.

Wait, let me re-read: "the details of spin-up or spin-down is hide in a single index, l=1,...,L. The Hilbert space is 2^L dimension."

This means:
- We have L spin-orbitals (not N spatial orbitals)
- Each spin-orbital l (1-indexed) is represented by bit (l-1) in the UInt
- The full Hilbert space is 2^L dimensional
- But the basis we enumerate is still the fixed-particle-number sector: states with exactly N occupied spin-orbitals out of L

So the interface changes:
- Instead of `FockBasis(N, Nup, Ndown)`, it becomes `FockBasis(L, N)` where L is the number of spin-orbitals and N is the total particle number.
- The bit encoding is simpler: bit (l-1) is 1 iff spin-orbital l is occupied.
- No more separate spin-up/spin-down halves.
- The basis size is C(L, N).
- Ordering: lexicographic by the sorted tuple of 1-indexed occupied spin-orbital positions.

Let me think about what changes:
- Representation: A Fock state is a UInt with L meaningful bits. Bit (l-1) is 1 iff spin-orbital l is occupied. No spin splitting.
- Interface: `FockBasis(L::Int, N::Int)` instead of `FockBasis(N::Int, Nup::Int, Ndown::Int)`
- nstates = C(L, N)
- Ordering: lexicographic by sorted tuple of occupied positions (1-indexed)
- base_index = rank (0-based lexicographic rank within C(L, N) combinations)
- public_index = base_index + 1

Let me construct pinned examples:
- L=4, N=2: C(4,2) = 6 states
  - {1,2} → bits 0,1 set → 0b0011 = 3
  - {1,3} → bits 0,2 set → 0b0101 = 5
  - {1,4} → bits 0,3 set → 0b1001 = 9
  - {2,3} → bits 1,2 set → 0b0110 = 6
  - {2,4} → bits 1,3 set → 0b1010 = 10
  - {3,4} → bits 2,3 set → 0b1100 = 12

- L=3, N=1: C(3,1) = 3 states
  - {1} → bit 0 → 1
  - {2} → bit 1 → 2
  - {3} → bit 2 → 4

- L=3, N=3: C(3,3) = 1 state
  - {1,2,3} → bits 0,1,2 → 0b111 = 7

- L=4, N=0: C(4,0) = 1 state
  - {} → 0

Let me verify the lexicographic ordering for L=4, N=2:
The combinations of 2 from {1,2,3,4} in lex order:
(1,2), (1,3), (1,4), (2,3), (2,4), (3,4)

Yes, that matches what I have above.

Now let me write the updated plan.

The INTENT should reflect that spin is now hidden in the spin-orbital index. The unit still serves `fermion-ops` and `op-matrix`.

Let me be careful about the interface:
```julia
struct FockBasis
    L::Int
    N::Int
    # internal fields
end

FockBasis(L::Int, N::Int)
nstates(fb::FockBasis)::Int
state_at(fb::FockBasis, i::Int)::UInt
index_of(fb::FockBasis, s::UInt)::Int
all_states(fb::FockBasis)::Vector{UInt}
```

Preconditions: L ≥ 1, 0 ≤ N ≤ L.

Let me finalize everything.
