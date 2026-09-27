#!/usr/bin/env python3
"""One-shot diagnostic: distinguish internal conjunction rejection from downstream barriers."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

p = Path("tools/planet_finder_search_core.py")
s = p.read_text()

old = '''        def assign(depth):
            if depth == len(group_items):
                # A complete conjunction is one atomic outer-search candidate.
'''
new = '''        blob_candidates = 0
        downstream_rejections = 0

        def assign(depth):
            nonlocal blob_candidates, downstream_rejections
            if depth == len(group_items):
                blob_candidates += 1
                diagnostic_print(
                    f"Planet Finder {mode}: CONJUNCTION BLOB INTERNALLY VALID "
                    f"group={group_index + 1} candidate={blob_candidates} "
                    f"bodies={' > '.join(ordered_names)}",
                    flush=True,
                )
                # A complete conjunction is one atomic outer-search candidate.
'''
if s.count(old) != 1:
    raise SystemExit(f"Safety stop: expected conjunction assign marker once; found {s.count(old)}")
s = s.replace(old, new, 1)

old = '''                if downstream():
                    diagnostic_print(
                        f"Planet Finder {mode}: CONJUNCTION BLOB COMPATIBLE "
                        f"group={group_index + 1} bodies={' > '.join(ordered_names)}",
                        flush=True,
                    )
                    return True
                del placed[placed_mark:]
'''
new = '''                if downstream():
                    diagnostic_print(
                        f"Planet Finder {mode}: CONJUNCTION BLOB COMPATIBLE "
                        f"group={group_index + 1} candidate={blob_candidates} "
                        f"bodies={' > '.join(ordered_names)}",
                        flush=True,
                    )
                    return True
                downstream_rejections += 1
                diagnostic_print(
                    f"Planet Finder {mode}: CONJUNCTION BLOB DOWNSTREAM BARRIER "
                    f"group={group_index + 1} candidate={blob_candidates} "
                    f"downstream_rejections={downstream_rejections} "
                    f"bodies={' > '.join(ordered_names)}; restoring whole blob",
                    flush=True,
                )
                del placed[placed_mark:]
'''
if s.count(old) != 1:
    raise SystemExit(f"Safety stop: expected downstream marker once; found {s.count(old)}")
s = s.replace(old, new, 1)

old = '''                f"rejections={diagnostic_rejections} "
                f"route_detail={route_summary} "
'''
new = '''                f"internally_valid_blobs={blob_candidates} "
                f"downstream_rejections={downstream_rejections} "
                f"barrier={'internal' if blob_candidates == 0 else 'downstream'} "
                f"rejections={diagnostic_rejections} "
                f"route_detail={route_summary} "
'''
if s.count(old) != 1:
    raise SystemExit(f"Safety stop: expected conjunction failure summary once; found {s.count(old)}")
s = s.replace(old, new, 1)

p.write_text(s)
me = Path(__file__)
me.write_text(me.read_text().replace("ENABLED = True", "ENABLED = False", 1))
print("Installed conjunction barrier diagnostics; Repair Once is now OFF.")
