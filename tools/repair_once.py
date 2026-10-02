#!/usr/bin/env python3
"""One-shot: make Venus forensic capture leader-graze events only."""

from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

old = '''                trace_venus = (
                    future_name == "Venus"
                    and first_mercury_signature == mercury_venus_first_signature[0]
                    and len(mercury_venus_first_candidates) < 12
                )
'''

new = '''                trace_venus = (
                    future_name == "Venus"
                    and first_mercury_signature == mercury_venus_first_signature[0]
                )
'''

if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: expected exactly one trace_venus block; found {text.count(old)}"
    )

text = text.replace(old, new, 1)

# The general Venus trace previously recorded early rejection types, which
# consumed all 12 slots before any leader-graze candidate was reached.
# Disable those diagnostic appends. They do not affect solver behavior.
blocks = [
'''                    if trace_venus:
                        mercury_venus_first_candidates.append(
                            f"box=({future_box.x:.1f},{future_box.y:.1f},{future_box.w:.1f},{future_box.h:.1f}) "
                            f"reject=overlap blockers={','.join(leader_names[i] if i < len(leader_names) else f'placed_{i}' for i in overlap_hits)}"
                        )
''',
'''                    if trace_venus:
                        mercury_venus_first_candidates.append(
                            f"box=({future_box.x:.1f},{future_box.y:.1f},{future_box.w:.1f},{future_box.h:.1f}) "
                            f"reject=existing-leader blockers={','.join(leader_names[j] if j < len(leader_names) else f'leader_{j}' for j in leader_hits)}"
                        )
''',
'''                    if trace_venus:
                        mercury_venus_first_candidates.append(
                            f"box=({future_box.x:.1f},{future_box.y:.1f},{future_box.w:.1f},{future_box.h:.1f}) reject=route"
                        )
''',
'''                    if trace_venus:
                        mercury_venus_first_candidates.append(
                            f"box=({future_box.x:.1f},{future_box.y:.1f},{future_box.w:.1f},{future_box.h:.1f}) reject=leader-rim"
                        )
''',
]

for block in blocks:
    if text.count(block) != 1:
        raise SystemExit(
            "Safety stop: expected exactly one non-graze Venus trace block"
        )
    text = text.replace(block, "", 1)

# Bound the detailed leader-graze capture itself to 12 events.
old_graze = '''                    if trace_venus:
                        min_dist, blocker_pair = minimum_leader_separation(path, paths)
'''

new_graze = '''                    if trace_venus and len(mercury_venus_first_candidates) < 12:
                        min_dist, blocker_pair = minimum_leader_separation(path, paths)
'''

if text.count(old_graze) != 1:
    raise SystemExit(
        f"Safety stop: expected exactly one Venus graze block; found {text.count(old_graze)}"
    )

text = text.replace(old_graze, new_graze, 1)

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
    "Venus forensic now captures 12 leader-graze events only; "
    "Repair Once is now OFF."
)