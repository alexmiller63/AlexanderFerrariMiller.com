from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search.py")
text = path.read_text()

old = '''    canonical_index = {name: i for i, name in enumerate(CANONICAL)}
    indexed = list(enumerate(bodies))
    indexed.sort(key=lambda item: canonical_index[item[1][1]])
'''

new = '''    canonical_index = {name: i for i, name in enumerate(CANONICAL)}
    indexed = list(enumerate(bodies))
    indexed.sort(key=lambda item: canonical_index[item[1][1]])
'''

anchor = '''    if {name for _, (_, name, _) in indexed} != set(CANONICAL):
        raise RuntimeError("Planet Finder body set does not match the canonical Solar-System objects")

'''

addition = '''    # First search order follows the bodies around the ecliptic.  Because
    # longitude is circular, place the linearization seam in the largest empty
    # angular gap so close neighbors across 0/360 degrees remain adjacent.
    lambda_sorted = sorted(indexed, key=lambda item: item[1][2] % 360.0)
    gaps = []
    for i, item in enumerate(lambda_sorted):
        current_lambda = item[1][2] % 360.0
        next_lambda = lambda_sorted[(i + 1) % len(lambda_sorted)][1][2] % 360.0
        gap = (next_lambda - current_lambda) % 360.0
        gaps.append(gap)
    seam_after = max(range(len(gaps)), key=gaps.__getitem__)
    indexed = lambda_sorted[seam_after + 1:] + lambda_sorted[:seam_after + 1]

'''

if text.count(old) != 1:
    raise SystemExit(f"Safety stop: expected canonical initialization once; found {text.count(old)}")
if text.count(anchor) != 1:
    raise SystemExit(f"Safety stop: expected body-set validation anchor once; found {text.count(anchor)}")

text = text.replace(anchor, anchor + addition, 1)
path.write_text(text)
print("Set first Planet Finder order to circular lambda order with seam in largest angular gap.")
