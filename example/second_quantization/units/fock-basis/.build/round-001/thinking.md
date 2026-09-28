The user wants me to create a plan for a Julia unit called "fock-basis" that deals with occupation-number (Fock) states for a fermionic system, stored as bitstrings.

Let me think about what this unit needs:

1. **Purpose**: Enumerate Fock basis states for a fixed number of fermion orbitals N, with optional fixed numbers of spin-up (N↑) and spin-down (N↓) electrons. Provide fast state↔index lookup.

2. **Key design decisions**:
   - States are stored as bitstrings (integers where each bit represents occupation of an orbital)
   - Fixed N (number of orbitals)
   - Optionally fixed N↑ and N↓ (particle numbers)
   - Need enumeration of all basis states
   - Need fast lookup: state → index and index → state

3. **Representation**:
   - A Fock state can be represented as an integer where bit i (0-indexed) indicates occupation of orbital i
   - If we have N orbitals total, and we separate spin-up and spin-down, we need to think about how to encode this
   - Actually, re-reading: "fixed N (and fixed N↑, N↓)" — this suggests N is the total number of orbitals, and N↑, N↓ are the numbers of spin-up and spin-down electrons.
   
   Wait, let me reconsider. In fermionic physics, typically you have N orbitals (modes). If we're dealing with spin, we might have N spatial orbitals × 2 spin = 2N modes, or we might have N↑ spin-up orbitals and N↓ spin-down orbitals.

   Actually, the most natural interpretation: We have a system with some number of orbitals. The states are bitstrings of length N where each bit is 0 or 1 (Pauli principle). If we fix the particle number, we only enumerate states with exactly that many 1-bits.

   Let me think about this more carefully. "Occupation-number states for a small fermionic system, stored as bitstrings." This is the standard Fock basis. Each orbital can be occupied (1) or unoccupied (0).

   "Enumerate the basis for fixed N (and fixed N↑, N↓)" — N is the number of orbitals, N↑ and N↓ are the numbers of spin-up and spin-down particles. This suggests we might have separate sectors.

   Actually, I think the simplest and most useful interpretation is:
   - We have N total modes (orbitals)
   - A Fock state is a bitstring of length N (each bit 0 or 1)
   - We can enumerate all states, or restrict to states with exactly N↑ + N↓ particles (or N↑ spin-up in first half and N↓ spin-down in second half)

   Hmm, but "N↑" and "N↓" suggest spin. Let me think about this differently.

   Perhaps the model is: We have N↑ spin-up orbitals and N↓ spin-down orbitals (so total N = N↑ + N↓ modes? No, that doesn't make sense either).

   Actually, I think the most natural reading is:
   - N = total number of single-particle orbitals (modes)
   - N↑ = number of spin-up electrons (fixed)
   - N↓ = number of spin-down electrons (fixed)
   - The state space is all bitstrings of length N with exactly N↑ + N↓ bits set to 1

   But wait, if we want to fix both N↑ and N↓ separately, we need a way to distinguish which orbitals are spin-up vs spin-down. 

   Let me reconsider. In a typical tight-binding or Hubbard model setup:
   - You have N spatial sites
   - At each site, you can have a spin-up electron and/or a spin-down electron
   - So there are 2N modes total
   - A Fock state is a bitstring of length 2N
   - N↑ is the number of spin-up electrons (bits in positions 1..N)
   - N↓ is the number of spin-down electrons (bits in positions N+1..2N)

   This is the most standard setup for a "small fermionic system" with spin.

   So:
   - N = number of spatial sites (each has up and down modes)
   - Total modes = 2N
   - A state is a 2N-bit integer
   - Bits 0..N-1: spin-up occupation at sites 0..N-1
   - Bits N..2N-1: spin-down occupation at sites 0..N-1
   - We enumerate all states with exactly N↑ ones in the first N bits and exactly N↓ ones in the last N bits

   Actually wait, re-reading: "fixed N (and fixed N↑, N↓)". The parenthetical suggests N↑ and N↓ are optional parameters. If not specified, we enumerate all 2^N states. If specified, we restrict.

   Hmm, but if N is the total number of modes and N↑+N↓ is the particle number, then we'd enumerate C(N, N↑+N↓) states. But then N↑ and N↓ separately don't make sense unless we have a spin structure.

   I think the cleanest interpretation that makes N↑ and N↓ meaningful is:
   - N = number of spatial orbitals
   - Total modes = 2N (N spin-up + N spin-down)
   - State = integer with 2N bits
   - N↑ = number of occupied spin-up modes (fixed)
   - N↓ = number of occupied spin-down modes (fixed)
   - Enumerate all such states

   This gives C(N, N↑) × C(N, N↓) total states.

   For the "fast state ↔ index lookup":
   - state_to_index(state) → Integer: given a valid Fock state, return its index in the enumeration
   - index_to_state(idx) → Integer: given an index, return the Fock state

   The ordering of states needs to be well-defined. A natural ordering is lexicographic on the bitstring (treating it as a number), or we could use a combinatorial number system.

   For the combinatorial approach:
   - Spin-up part: enumerate C(N, N↑) combinations of N↑ ones among N bits
   - Spin-down part: enumerate C(N, N↓) combinations of N↓ ones among N bits
   - Total index = index_up * C(N, N↓) + index_down

   The index within each spin sector can be computed using the combinadic (combinatorial number system).

   Let me define this precisely:

   **Representation**:
   - A Fock state is a UInt (or Int) with 2N bits set
   - Bits 0 through N-1: spin-up occupation (bit i = 1 means orbital i is occupied by spin-up)
   - Bits N through 2N-1: spin-down occupation (bit N+i = 1 means orbital i is occupied by spin-down)

   **Interface**:
   - `FockBasis(N::Int, Nup::Int, Ndown::Int)` — constructor
   - Or maybe a struct `FockBasis` that holds N, Nup, Ndown, and the lookup tables
   - `num_states(fb::FockBasis) → Int`
   - `state_at(fb::FockBasis, idx::Int) → UInt` — 1-indexed (Julia convention)
   - `index_of(fb::FockBasis, state::UInt) → Int` — 1-indexed
   - Maybe `states(fb::FockBasis) → Vector{UInt}` — enumerate all states

   Actually, for Julia, 1-based indexing is the norm.

   Let me think about what's most useful for the consumers (fermion-ops and op-matrix):
   - They need to iterate over all basis states
   - They need to apply operators (which flip bits) and look up the resulting state's index
   - They need to build matrices indexed by the basis

   So the key operations are:
   - Construct the basis
   - Get the number of states
   - Get state at index (for building operators)
   - Get index of a state (after applying an operator that flips bits)
   - Maybe: iterate over all states

   Let me finalize the design:

   **FockBasis struct**:
   - `N::Int` — number of spatial orbitals
   - `Nup::Int` — number of spin-up electrons
   - `Ndown::Int` — number of spin-down electrons
   - Internal: precomputed lookup table (Dict or array) mapping state→index, and array of states

   **Public functions**:
   - `FockBasis(N, Nup, Ndown)` — constructor, builds the basis
   - `nstates(fb::FockBasis) → Int`
   - `state_at(fb::FockBasis, i::Int) → UInt` — i is 1-based
   - `index_of(fb::FockBasis, s::UInt) → Int` — returns 1-based index, or throws if not in basis
   - `all_states(fb::FockBasis) → Vector{UInt}`

   **Ordering**: I'll use a specific order. Let's say:
   - The spin-up part is ordered by the combinadic (lexicographic on positions of 1s)
   - The spin-down part similarly
   - Overall: index = up_index * C(N, Ndown) + down_index + 1 (1-based)
   - Within each sector, combinations are ordered lexicographically by the sorted list of occupied orbital indices

   Wait, let me think about what ordering is most natural and easy to verify.

   For a set of positions (orbitals) where N↑ bits are 1 among N positions:
   - Order them lexicographically by the tuple of 1-indices of the occupied orbitals
   - E.g., N=4, N↑=2: (1,2), (1,3), (1,4), (2,3), (2,4), (3,4)
   - This is the standard "combinations in lex order"

   For the full state, the index is:
   - idx = (up_rank * C(N, Ndown)) + down_rank + 1

   Where up_rank and down_rank are 0-based ranks within their respective combination sets.

   Let me verify with a small example:
   - N=2, Nup=1, Ndown=1
   - Spin-up combinations (1 out of 2): {1}, {2} → ranks 0, 1
   - Spin-down combinations (1 out of 2): {1}, {2} → ranks 0, 1
   - Total states: 4
   - State 0: up={1}, down={1} → bits: up=01, down=01 → 0b0101 = 5
   - State 1: up={1}, down={2} → bits: up=01, down=10 → 0b1001 = 9
   - State 2: up={2}, down={1} → bits: up=10, down=01 → 0b0110 = 6
   - State 3: up={2}, down={2} → bits: up=10, down=10 → 0b1010 = 10

   Wait, I need to be careful about bit ordering. Let me define:
   - Bit i (0-indexed) corresponds to orbital i+1 (1-indexed)
   - Spin-up occupies bits 0..N-1
   - Spin-down occupies bits N..2N-1

   So for N=2:
   - Orbital 1 spin-up: bit 0
   - Orbital 2 spin-up: bit 1
   - Orbital 1 spin-down: bit 2
   - Orbital 2 spin-down: bit 3

   State up={1}, down={1}: bit0=1, bit2=1 → 0b0101 = 5
   State up={1}, down={2}: bit0=1, bit3=1 → 0b1001 = 9
   State up={2}, down={1}: bit1=1, bit2=1 → 0b0110 = 6
   State up={2}, down={2}: bit1=1, bit3=1 → 0b1010 = 10

   So the basis in order: [5, 9, 6, 10]

   This is a clean, verifiable example.

   Now, for the combinadic / rank:
   - To compute the rank of a combination (i1 < i2 < ... < ik) among C(n, k) combinations in lex order:
     - rank = C(i1-1, k-1) + C(i2-1, k-2) + ... + C(ik-1, 0)
   
   Wait, that's one formulation. Let me be more careful.

   The standard combinadic: given a combination (c1 < c2 < ... < ck) where 1 ≤ ci ≤ n:
   - rank = C(c1-1, k-1) + C(c2-1, k-2) + ... + C(ck-1, 0)

   For n=2, k=1:
   - (1): rank = C(0, 0) = 0
   - (2): rank = C(1, 0) = 1
   
   For n=2, k=2:
   - (1,2): rank = C(0,1) + C(1,0) = 0 + 1 = 1
   
   Hmm wait, that gives rank 1 for the only combination of 2 choose 2. That's not 0-based. Let me reconsider.

   Actually the standard combinadic formula gives the 0-based rank:
   - rank(c1, c2, ..., ck) = C(c1-1, k-1) + C(c2-1, k-2) + ... + C(ck-1, 0)

   For n=4, k=2, combinations in lex order: (1,2), (1,3), (1,4), (2,3), (2,4), (3,4)
   - (1,2): C(0,1) + C(1,0) = 0 + 1 = 1... that should be 0.

   Hmm, I'm getting confused. Let me look at this differently.

   Actually, the correct formula for the rank (0-based) of combination (c1 < c2 < ... < ck) in the lex-ordered list of all C(n,k) combinations is:

   rank = sum_{j=1}^{k} C(cj - 1, j)  ... no, that's not right either.

   Let me just think about it as: the number of combinations that come before (c1, c2, ..., ck) in lex order.

   A combination (d1, d2, ..., dk) comes before (c1, c2, ..., ck) if at the first position j where they differ, dj < cj.

   So: rank = sum over all valid "prefix" choices that are less.

   Actually, the standard formula is:
   rank(c1, c2, ..., ck) = Σ_{j=1}^{k} Σ_{i=1}^{cj-1} [i > c_{j-1}] C(n - i, k - j)

   Where c_0 = 0. This counts all combinations with the first j-1 elements matching and the j-th element less than cj.

   This is getting complicated. For the SPEC, I don't need to give the formula, I just need to pin the ordering with examples. Let me just say "lexicographic order on the tuple of 1-based orbital indices of occupied states" and give examples.

   Actually, for the SPEC, the key thing is that the ordering is deterministic and pinned by examples. The implementation can use any algorithm to compute it. Let me just define the order clearly and give a small example.

   Let me simplify. I'll define:
   - Within each spin sector, states are ordered lexicographically by the sorted tuple of 1-indexed occupied orbital positions.
   - The overall state is ordered by: primarily by spin-up rank, secondarily by spin-down rank. (i.e., spin-up is the "outer" loop)

   Let me now write the plan.

   For the Interface section, I'll use Julia syntax:

   ```julia
   struct FockBasis
       N::Int
       Nup::Int
       Ndown::Int
       # internal fields...
   end

   FockBasis(N::Int, Nup::Int, Ndown::Int)  # constructor
   nstates(fb::FockBasis)::Int
   state_at(fb::FockBasis, i::Int)::UInt
   index_of(fb::FockBasis, s::UInt)::Int
   all_states(fb::FockBasis)::Vector{UInt}
   ```

   For Julia, I should use `UInt` for the state representation.

   Edge cases:
   - Nup or Ndown = 0: valid, means no particles of that spin
   - Nup > N or Ndown > N: invalid, should throw
   - N = 0: probably invalid (or trivial with 1 state)
   - index_of for a state not in the basis: throw ArgumentError or return -1? I'll say throw.
   - state_at with i out of range: throw BoundsError (Julia convention)

   Let me also think about whether we need a way to extract the spin-up and spin-down parts of a state. For the consumers (fermion-ops), they'll likely need to manipulate bits. I'll add:
   - `spin_up(fb::FockBasis, s::UInt)::UInt` — extract lower N bits
   - `spin_down(fb::FockBasis, s::UInt)::UInt` — extract upper N bits (shifted right by N)

   Actually, the consumers can do this themselves with bit shifts. Let me not over-engineer. I'll keep the interface minimal.

   Wait, but the consumers need to apply fermionic operators (creation/annihilation) which flip specific bits. They'll need:
   - To check if a specific orbital is occupied: `s & (1 << i) != 0`
   - To flip a bit: `s ⊻ (1 << i)`
   - To look up the resulting state's index

   So the critical interface is just `index_of` and the ability to do bit manipulation (which is inherent to representing states as UInt).

   I think the interface is:
   - Constructor
   - nstates
   - state_at (useful for iteration, debugging)
   - index_of (the critical fast lookup)
   - all_states (convenience)

   Let me finalize and write the plan.

   One more thought: should Nup and Ndown be optional (defaulting to "don't fix particle number")? The human said "fixed N (and fixed N↑, N↓)" with the parenthetical suggesting they're optional. But if we don't fix particle number, N↑ and N↓ don't apply, and we'd just enumerate all 2^(2N) states. That's a very different structure.

   I think for this unit, the primary use case is fixed particle number (since it's used by fermion-ops and op-matrix which build matrices in a sector). I'll require Nup and Ndown as mandatory parameters. If the user wants all states, they can set Nup=N, Ndown=N (or whatever). Actually no, that forces specific particle numbers.

   Hmm, let me re-read: "Enumerate the basis for fixed N (and fixed N↑, N↓), with fast state ↔ index lookup."

   I think the "(and fixed N↑, N↓)" is describing the typical use case but the unit should support it. I'll make Nup and Ndown required parameters. This is the simplest and most useful design.

   Actually, I realize I should reconsider the structure. What if N is not the number of spatial sites but the total number of modes? Then N↑ and N↓ are just the numbers of particles in each "half" of the modes.

   But that's less natural. I'll stick with: N = number of spatial orbitals, total modes = 2N, N↑ = particles in spin-up sector, N↓ = particles in spin-down sector.

   Let me write the final plan now.
