from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''            # route() deliberately aims at the label center.  Rendering later
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
'''

new = '''            # Judge the geometry that will actually be rendered. route()
            # terminates at the label center, but the renderer clips that last
            # segment to the first label-boundary intersection.  No earlier
            # segment may enter or graze the label, and the clipped final
            # approach may touch the label only at its terminating boundary
            # point.  W01 Mixed Saturn exposed a dogleg whose previous segment
            # passed through the label before the nominal final approach.
            def own_label_edge(source):
                dx = source[0] - box.x
                dy = source[1] - box.y
                if abs(dx) < 1e-12 and abs(dy) < 1e-12:
                    return box.x, box.y
                scale = min(
                    box.w / (2.0 * abs(dx)) if abs(dx) >= 1e-12 else float("inf"),
                    box.h / (2.0 * abs(dy)) if abs(dy) >= 1e-12 else float("inf"),
                )
                return box.x + dx * scale, box.y + dy * scale

            rendered_path = [*path[:-1], own_label_edge(path[-2])]
            own_label_bad = any(
                segment_hits_box(rendered_path[i], rendered_path[i + 1], box, 0.5)
                for i in range(max(0, len(rendered_path) - 2))
            )
            # The final rendered segment is allowed to terminate on the true
            # boundary, but it must not penetrate the label interior before
            # that endpoint.  A slightly shrunken box makes that distinction
            # explicit instead of exempting the whole final segment.
            if len(rendered_path) >= 2 and segment_hits_box(
                rendered_path[-2], rendered_path[-1], box, -0.5
            ):
                own_label_bad = True

            if own_label_bad:
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_graze"] += 1
                continue
'''

if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: expected own-label viability block once; found {text.count(old)}"
    )

path.write_text(text.replace(old, new, 1))
print("Rendered own-label leader geometry is now enforced before DFS admission.")
