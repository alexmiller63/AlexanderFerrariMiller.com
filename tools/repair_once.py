from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''            rendered_path = [*path[:-1], own_label_edge(path[-2])]
            own_label_bad = any(
                segment_hits_box(rendered_path[i], rendered_path[i + 1], box, 0.5)
                for i in range(max(0, len(rendered_path) - 2))
            )
'''

new = '''            rendered_path = [*path[:-1], own_label_edge(path[-2])]

            # A routed leader must make monotonic progress toward its rendered
            # label endpoint.  Reject overshoot/backtracking doglegs where an
            # intermediate waypoint gets closer to the endpoint and a later
            # waypoint moves away again.  W01 Mixed Saturn measured as
            # (306.0,672.4) -> (350.0,516.8) -> label edge near (362.1,523.1):
            # the route overshoots above the label and reverses on approach.
            endpoint = rendered_path[-1]
            distances = [
                math.hypot(point[0] - endpoint[0], point[1] - endpoint[1])
                for point in rendered_path
            ]
            route_backtracks = any(
                distances[i + 1] > distances[i] + 1e-6
                for i in range(len(distances) - 1)
            )

            own_label_bad = route_backtracks or any(
                segment_hits_box(rendered_path[i], rendered_path[i + 1], box, 0.5)
                for i in range(max(0, len(rendered_path) - 2))
            )
'''

if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: expected rendered-path viability block once; found {text.count(old)}"
    )

path.write_text(text.replace(old, new, 1))
print("Leader overshoot/backtracking is now rejected before DFS admission.")
