# Star Almanack Notes — Finders

## 2026-09-27 — Planet Finder architecture cleanup and search redesign

### Obsolete anchor-glyph geometry

Planet Finder no longer renders a body glyph at the astronomical anchor. The visible glyph belongs only in the displaced label at the end of the leader. Therefore anchor-glyph separation geometry must not participate in search.

The previous code still carried obsolete machinery from the earlier design:

- `CONJUNCTION_GLYPH_RADIUS_STEP = 48.0`
- `conjunction_glyph_radii(...)`
- invisible conjunction `glyph_radius = 22.0`
- synthetic `glyph_centers`
- overlap checks between those invisible glyph circles
- radial staggering of leader anchors to separate invisible glyphs
- generator and renderer plumbing for `glyph_radii`

This stale geometry produced illegal conjunction anchors. For a two-body conjunction at base radius `RI - 5 = 425`, symmetric ±24 px staggering produced radii 401 and 449. The inner zodiac rim is at `RI = 430`, while leader geometry must remain inside `RI - LEADER_RIM_CLEARANCE = 428`. Thus the 449 px anchor was outside the legal leader region before routing began. It also landed almost exactly in the inward protected extent of some zodiac-label obstacles, notably Cancer.

The correct invariant is:

- every astronomical leader anchor stays at exact ecliptic longitude λ;
- every astronomical leader anchor uses one fixed radius, `RI - 5`;
- conjunction handling separates labels/leaders, not invisible anchor glyphs;
- no anchor-glyph collision rule exists because no anchor glyph exists.

Repair Once installed this architectural cleanup on 2026-09-27. Afterward, the previous deterministic `no atomic conjunction layout` failures disappeared. The test suite changed from immediate geometric conjunction rejection to wall-clock exhaustion, demonstrating that the stale anchor geometry had been masking a deeper search-cost problem.

### One authoritative leader path

Search and rendering had also duplicated leader-endpoint geometry.

The router computed a path toward the label, while rendering independently recomputed first contact with the target label rectangle and backed the SVG line off by 2 px. This meant search validated one geometric path and the renderer later substituted another.

The corrected contract is:

- routing computes the final drawable endpoint once;
- the endpoint is the first label-boundary intersection backed off by 2 px so the round SVG cap cannot paint into the label;
- search validates that exact drawable path;
- rendering draws the returned path verbatim and does not reclip or recalculate it.

### What the post-cleanup timeout uncovered

After the anchor-glyph cleanup, Planet Finder unit tests ran for 439.31 s and finished with 38 passed / 8 failed. The failures were wall-clock timeouts, not atomic-conjunction impossibility. The W02 Greek cases exhausted their 15 s limit, and one unrelated Mixed five-body case exhausted 60 s.

This means the solver is now reaching legitimate search space that was previously hidden behind erroneous early rejection.

The architectural review found that the main cost is repeated equivalent search rather than intrinsically expensive geometry.

### The current refinement sequence is largely redundant

The controller currently treats these as separate placement-refinement phases:

- 2.0 label lengths
- 1.5 label lengths
- 1.0 label length
- 0.5 label lengths
- 0.25 label lengths

However, `candidate_positions()` always appends the permanent quarter-step grid:

- `quarter_step = LABEL_LENGTH * 0.25 = 26.25 px`
- quarter-step shifts span -8 through +8

Therefore the nominal phase offsets are already members of that same lattice:

- 2.0 = 210.0 px = 8 × 26.25
- 1.5 = 157.5 px = 6 × 26.25
- 1.0 = 105.0 px = 4 × 26.25
- 0.5 = 52.5 px = 2 × 26.25
- 0.25 = 26.25 px = 1 × 26.25

Within one call duplicate positions are suppressed, but between controller phases the solver clears ordering history and resets body candidate budgets. The result is several reordered searches over substantially the same geometric candidate set.

The 2.0 → 1.5 → 1.0 → 0.5 → 0.25 restart sequence should therefore be retired as a controller mechanism.

### Replacement: one canonical candidate lattice

Use one ordered candidate stream instead of repeated refinement restarts.

Tangential displacement shells should be generated once in increasing geometric cost:

- 0.00
- ±0.25
- ±0.50
- ±0.75
- ±1.00
- ±1.25
- ±1.50
- ±1.75
- ±2.00

These values are label-length scales, not degrees.

Preferred radii should likewise be offered before progressively less-preferred radii. The solver then naturally tries nearby, visually desirable positions first and continues outward only when needed.

The desired invariant is:

> A distinct candidate position is generated once for a body/search state, not regenerated because the controller changed a nominal refinement phase.

This allows the controller to remove:

- `refinement_scales = (2.0, 1.5, 1.0, 0.5, 0.25)`
- the `REFINE` state
- refinement-driven clearing of `attempted_orders`
- refinement-driven reset of all body candidate budgets
- repeated searches whose only difference is `displacement_scale`

Squeaky-wheel body promotion should remain. It solves a separate problem: ordering constrained bodies earlier.

### Additional redundant routing work

The architecture review also identified several route-recomputation multipliers.

#### Forward checking repeats work that DFS immediately repeats

At each DFS prefix, `forward_check()` generates future-body candidates and calls `route()` to find an individually viable witness. It creates a fresh prefix cache for that witness search. If the body is then reached by ordinary DFS, `viable_candidates()` generates and routes those candidates again.

Conceptually:

1. forward check asks whether Mars can fit;
2. it generates Mars candidates and calculates Mars routes;
3. recursion reaches Mars;
4. DFS generates Mars candidates and calculates Mars routes again.

Forward-check route work should either be cached by DFS geometry state or its witness candidate should be reusable when that body becomes the next actual DFS node.

#### Alignment planning recalculates already-valid routes

The alignment planner's recursive assignment repeatedly calls `planned_paths(chosen)`. Each call reroutes every body already in `chosen`.

Thus adding C after A and B recalculates A and B even though their own anchors and target labels have not changed. Deeper recursion recalculates those same routes again, and the completed assignment recalculates them once more.

The alignment planner should be incremental:

- retain already validated paths in the recursive state;
- calculate only the newly added body's route;
- invalidate/recompute an existing path only when a newly introduced obstacle can actually affect it.

#### Conjunction routing has the same smaller duplication

Conjunction candidate pools are bounded, but candidate pairings still call `route()` repeatedly without retaining reusable anchor-side route work across equivalent parent states. Once the larger controller and alignment duplication are fixed, conjunction-specific caching can be applied similarly.

### Recommended next implementation order

1. Replace multi-phase refinement with one canonical ordered displacement lattice.
2. Keep squeaky-wheel promotion, but make candidate budgets count distinct viable geometric candidates rather than candidates within a refinement restart.
3. Reuse forward-check witness work or cache it by prefix geometry.
4. Make alignment routing incremental instead of rebuilding every chosen path at each recursion level.
5. Then optimize conjunction routing if profiling still shows it matters.

Do not respond to these timeouts by merely increasing clocks. The post-cleanup failures indicate repeated equivalent work; the correct repair is to remove redundant search and routing computation.
