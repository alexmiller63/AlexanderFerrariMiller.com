#!/usr/bin/env python3
"""One-shot: add Sun/Venus leader fan-out forensic diagnostics only."""

from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

old = '''                    if trace_venus:
                        min_dist, blocker_pair = minimum_leader_separation(path, paths)
                        blocker = "-"
                        if blocker_pair is not None:
                            j = blocker_pair[0]
                            blocker = leader_names[j] if j < len(leader_names) else f"leader_{j}"
                        mercury_venus_first_candidates.append(
                            f"box=({future_box.x:.1f},{future_box.y:.1f},{future_box.w:.1f},{future_box.h:.1f}) "
                            f"reject=leader-graze blocker={blocker} distance={min_dist:.3f}"
                        )
'''

new = '''                    if trace_venus:
                        min_dist, blocker_pair = minimum_leader_separation(path, paths)
                        blocker = "-"
                        segment_pair = "-/-"
                        anchor_sep = float("nan")
                        proposed_path = tuple(
                            (round(px, 1), round(py, 1)) for px, py in path
                        )
                        existing_path = ()
                        if blocker_pair is not None:
                            j = blocker_pair[0]
                            blocker = (
                                leader_names[j]
                                if j < len(leader_names)
                                else f"leader_{j}"
                            )
                            segment_pair = f"{blocker_pair[1]}/{blocker_pair[2]}"
                            if j < len(paths):
                                other = paths[j]
                                anchor_sep = math.hypot(
                                    path[0][0] - other[0][0],
                                    path[0][1] - other[0][1],
                                )
                                existing_path = tuple(
                                    (round(px, 1), round(py, 1))
                                    for px, py in other
                                )
                        mercury_venus_first_candidates.append(
                            f"box=({future_box.x:.1f},{future_box.y:.1f},"
                            f"{future_box.w:.1f},{future_box.h:.1f}) "
                            f"reject=leader-graze blocker={blocker} "
                            f"distance={min_dist:.3f} "
                            f"clearance={LEADER_TO_LEADER_CLEARANCE:.3f} "
                            f"segments={segment_pair} "
                            f"anchor-separation={anchor_sep:.3f} "
                            f"close-anchors="
                            f"{anchor_sep < LEADER_TO_LEADER_CLEARANCE} "
                            f"venus-path={proposed_path} "
                            f"blocker-path={existing_path}"
                        )
'''

if text.count(old) != 1:
    raise SystemExit(
        "Safety stop: expected exactly one Venus leader-graze "
        f"diagnostic block; found {text.count(old)}"
    )

text = text.replace(old, new, 1)
P.write_text(text, encoding="utf-8")

# Self-disable after successful repair.
me = Path(__file__)
source = me.read_text(encoding="utf-8")

enabled_assignment = "\nENABLED = " + "True\n"
disabled_assignment = "\nENABLED = False\n"

if source.count(enabled_assignment) != 1:
    raise SystemExit(
        "Safety stop: ENABLED assignment not uniquely identifiable"
    )

source = source.replace(
    enabled_assignment,
    disabled_assignment,
    1,
)

me.write_text(source, encoding="utf-8")

print(
    "Added bounded Sun/Venus fan-out diagnostics; "
    "Repair Once is now OFF."
)