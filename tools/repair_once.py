from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()
old = '''                if leader_hits_zodiac_rim(path_candidate) or leaders_too_close(
                        path_candidate, leaders + list(chosen_paths.values())):
                    chosen.pop(name, None)
                    continue
'''
new = '''                # Conjunction siblings intentionally originate at nearly the
                # same lambda, so their leaders may be close near the anchors.
                # Keep the ordinary clearance rule against leaders outside this
                # atomic conjunction, while sibling leader/label collisions are
                # checked explicitly above and below.
                if leader_hits_zodiac_rim(path_candidate) or leaders_too_close(
                        path_candidate, leaders):
                    chosen.pop(name, None)
                    continue
'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: expected conjunction leader check exactly once; found {text.count(old)}")
path.write_text(text.replace(old, new, 1))
print("Conjunction atomic solver now exempts sibling leader proximity only; external leader checks preserved.")
