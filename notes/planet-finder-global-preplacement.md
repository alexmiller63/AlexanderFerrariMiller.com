# Planet Finder: global preplacement implementation plan

## Objective
Plan feasible label and leader placements for **all 11 chart bodies** before committing any final placement. This is a generator-level change, never a week-specific patch.

## Existing behavior to preserve
- The existing geometry, hard collision constraints, candidate generation, and independent final validation remain authoritative.
- All Greek, Mixed, and English layouts must pass independently.
- Keep previously successful published weeks untouched until replacements pass regression checks.
- Keep one hard wall-clock deadline per mode; no unbounded retries.

## Implementation stages
1. Build candidate domains for every body using the existing geometry filters, with conservative label envelopes sized for the widest notation.
2. Construct a compatibility graph: each pair of candidates is compatible only if label boxes, rim clearance, and routed leader paths meet existing constraints.
3. Apply forward checking: after any tentative reservation, remove incompatible candidates from every unassigned body's domain. Backtrack immediately if any domain becomes empty.
4. Choose the next body using minimum remaining values (MRV), breaking ties by conflict degree, then canonical order. Handle conjunctions and alignments as coupled constraints, without excluding their members from the global feasibility check.
5. Solve for a complete feasible assignment. Use that assignment as a warm start for each notation mode, then permit independent refinement and beautification only if final validation passes.
6. Emit structured diagnostics per week/mode: initial candidate counts, domain reductions, blockers, node count, elapsed time, and final validation result.

## Acceptance tests
- Start with failed weeks 20, 24, 27, 29, 36, 38, 40, 47, 49, and 51.
- Test Greek, Mixed, English for each week.
- Run all available 2026 weeks as regression checks, including known successful weeks.
- Verify deterministic repeat runs and no changes to canonical ephemeris positions.
- Never publish a layout that fails existing independent validation.

## Rollout
Implement behind an opt-in switch; benchmark against the current solver; only make it default after passing the complete regression suite. No automatic rerun of paid workflows during development.
