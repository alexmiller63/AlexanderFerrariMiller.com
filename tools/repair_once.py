from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = """            for x, y, box in legal_candidate_positions(
                    longitude, w, h, reserved, displacement_scale):
"""
new = """            # Tight conjunctions get the finest existing label-displacement
            # refinement.  This applies only to the atomic conjunction solver;
            # ordinary DFS retains the caller's refinement scale.
            conjunction_displacement_scale = 0.25
            for x, y, box in legal_candidate_positions(
                    longitude, w, h, reserved, conjunction_displacement_scale):
"""
if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: expected exactly one conjunction candidate-pool call; found {text.count(old)}"
    )

path.write_text(text.replace(old, new, 1))
print("Conjunction candidate pools now use the finest 0.25 refinement scale; ordinary DFS unchanged.")
