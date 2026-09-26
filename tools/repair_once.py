from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''            if path is None:
                rejected_route += 1
                stats["route"] += 1
                continue

            # A new leader must not cross any label already placed by DFS.
'''

new = '''            if path is None:
                rejected_route += 1
                stats["route"] += 1
                continue

            # route() deliberately aims at the label center.  Rendering later
            # clips only that final segment to the label boundary.  Candidate
            # viability must therefore judge the same renderable geometry:
            # earlier leader segments may never enter or graze their own label.
            # The final segment is exempt because its center endpoint is the
            # intentional clipping target.
            if any(
                segment_hits_box(path[i], path[i + 1], box, 0)
                for i in range(max(0, len(path) - 2))
            ):
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_graze"] += 1
                continue

            # A new leader must not cross any label already placed by DFS.
'''

if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: expected route-success admission point once; found {text.count(old)}"
    )

path.write_text(text.replace(old, new, 1))
print("Own-label leader crossings are now rejected before DFS admission.")
