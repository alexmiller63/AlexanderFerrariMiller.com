from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search.py")
text = path.read_text()

needle = '''    indexed = lambda_sorted[seam_after + 1:] + lambda_sorted[:seam_after + 1]

    if target_solutions is None:
'''
replacement = '''    indexed = lambda_sorted[seam_after + 1:] + lambda_sorted[:seam_after + 1]

    # Diagnostic: report the closest pair on the circular ecliptic.  This is
    # observational only; it does not change search order or placement policy.
    closest_pair = None
    for i, left in enumerate(lambda_sorted):
        right = lambda_sorted[(i + 1) % len(lambda_sorted)]
        left_name = left[1][1]
        right_name = right[1][1]
        left_lambda = left[1][2] % 360.0
        right_lambda = right[1][2] % 360.0
        separation = (right_lambda - left_lambda) % 360.0
        if closest_pair is None or separation < closest_pair[0]:
            closest_pair = (separation, left_name, right_name, left_lambda, right_lambda)
    if closest_pair is not None:
        separation, left_name, right_name, left_lambda, right_lambda = closest_pair
        diagnostic_print(
            f"Planet Finder {mode}: CLOSEST ECLIPTIC PAIR "
            f"{left_name} lambda={left_lambda:.3f} deg; "
            f"{right_name} lambda={right_lambda:.3f} deg; "
            f"separation={separation:.3f} deg",
            flush=True,
        )

    if target_solutions is None:
'''

if text.count(needle) != 1:
    raise SystemExit(f"Safety stop: expected lambda-order insertion point once; found {text.count(needle)}")

text = text.replace(needle, replacement, 1)
path.write_text(text)
print("Installed closest-pair ecliptic angular-separation diagnostic.")
