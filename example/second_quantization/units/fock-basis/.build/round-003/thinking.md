The user wants to generalize the fock-basis from specifically spin-½ fermions to any fermionic system. The key point is that the basis itself doesn't care about the physical meaning of the modes (spin-orbitals, orbital labels, etc.) — it just works with L modes and N particles. The spin-½ reference is just one example application.

Let me update the INTENT to reflect this generalization, while preserving everything else in the SPEC that isn't affected. The SPEC itself is already quite general (it talks about "spin-orbitals" but the actual mechanics are just L bits, N set). I should update the INTENT to say it's general fermionic systems, and perhaps tweak the SPEC wording slightly to not hardcode "spin-½" while keeping "spin-orbital" as a natural label for the modes (since that's still a common usage). Actually, let me re-read the input: "the fock-basis can be any-fermionic system, not necessarily spin-1/2, add this clearly."

So the change is primarily in INTENT — making clear this is not restricted to spin-½. The SPEC can keep using "spin-orbital" as the mode label since that's still a valid name for the L modes in many fermionic systems, but I should make the INTENT clear that it's general.

Let me update:
- INTENT: Remove the spin-½ specificity, state it's for any fermionic system with L modes and N particles.
- SPEC: The wording "spin-orbital" can stay as a mode label (it's a common generic term), but I'll adjust slightly to say "modes" or keep "spin-orbitals" as one example. Actually, the current SPEC uses "spin-orbital" throughout. Since the user says "not necessarily spin-1/2", I should generalize the language. Let me use "mode" as the generic term and note that in a spin-½ system these are spin-orbitals.

Actually, looking more carefully, the SPEC says "spin-orbital l" in several places. I'll change to "mode l" to be general, and note in INTENT that in a spin-½ system these would be spin-orbitals. This keeps the mechanics identical while generalizing the description.

Let me produce the updated plan.
