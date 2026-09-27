from pathlib import Path
import re
import subprocess

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

p = Path("tools/planet_finder_geometry.py")
s = p.read_text()

start = s.index("    def route_clear_of_target(path) -> bool:\n")
end = s.index("\n    anchor_theta =", start)
replacement = '''    def target_landing(source, target):
        dx = target.x - source[0]
        dy = target.y - source[1]
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            return None
        t_enter, t_exit = 0.0, 1.0
        for p0, q0 in (
            (-dx, source[0] - target.left),
            ( dx, target.right - source[0]),
            (-dy, source[1] - target.top),
            ( dy, target.bottom - source[1]),
        ):
            if abs(p0) < 1e-12:
                if q0 < 0:
                    return None
                continue
            r = q0 / p0
            if p0 < 0:
                t_enter = max(t_enter, r)
            else:
                t_exit = min(t_exit, r)
            if t_enter > t_exit:
                return None
        if t_exit < 0.0 or t_enter > 1.0:
            return None
        return source[0] + t_enter * dx, source[1] + t_enter * dy

    def route_clear_of_target(path) -> bool:
        if target_box is None:
            return True
        if len(path) < 2:
            return False
        for i in range(len(path) - 2):
            if segment_hits_box(path[i], path[i + 1], target_box, IMMUTABLE_LEADER_CLEARANCE):
                return False
        return not segment_hits_box(path[-2], path[-1], target_box, -0.5)

    direct_endpoint = target_landing(anchor, target_box) if target_box is not None else center
    if direct_endpoint is not None and segment_clear(anchor, direct_endpoint, skip_start_escape=True):
        candidate = [anchor, direct_endpoint]
        if route_clear_of_target(candidate):
            return candidate
        if diagnostic is not None:
            diagnostic["target_approach"] = diagnostic.get("target_approach", 0) + 1
    elif diagnostic is not None:
        diagnostic["direct_blocked"] = diagnostic.get("direct_blocked", 0) + 1
'''
s = s[:start] + replacement + s[end:]

old = '''            if not segment_clear(elbow2, center):
                if diagnostic is not None:
                    diagnostic["final_blocked"] = diagnostic.get("final_blocked", 0) + 1
                continue
            candidate = [anchor, elbow1, elbow2, center]
'''
new = '''            final_endpoint = target_landing(elbow2, target_box) if target_box is not None else center
            if final_endpoint is None or not segment_clear(elbow2, final_endpoint):
                if diagnostic is not None:
                    diagnostic["final_blocked"] = diagnostic.get("final_blocked", 0) + 1
                continue
            candidate = [anchor, elbow1, elbow2, final_endpoint]
'''
if s.count(old) != 1:
    raise SystemExit(f"Safety stop: final segment block count={s.count(old)}")
s = s.replace(old, new, 1)
p.write_text(s)

me = Path(__file__)
me.write_text(me.read_text().replace("ENABLED = True", "ENABLED = False", 1))
subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", str(p), str(me)], check=True)
subprocess.run(["git", "commit", "-m", "Land conjunction leaders on label boundary"], check=True)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)
print("Exact label-boundary landing installed; target interior stays protected; ordinary DFS and 0.25 refinement unchanged; switch OFF.")
