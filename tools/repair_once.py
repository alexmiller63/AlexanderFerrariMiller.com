from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

needle = '''        for (depth, name), s in sorted(diagnostic_stats.items()):
            immutable_names = {
'''
replacement = '''        longitude_by_name = {
            item[1][1]: item[1][2]
            for item in order
        }
        for (depth, name), s in sorted(diagnostic_stats.items()):
            immutable_names = {
'''

if text.count(needle) != 1:
    raise SystemExit(
        f"Safety stop: expected terminal body loop once; found {text.count(needle)}"
    )
text = text.replace(needle, replacement, 1)

needle = '''                f"Planet Finder {mode}: TERMINAL BODY depth={depth}/{len(order)} body={name} "
                f"status={'evaluated' if s.get('started') else ('blocked-' + s['blocked'] if s.get('blocked') else 'not-evaluated')} "
'''
replacement = '''                f"Planet Finder {mode}: TERMINAL BODY depth={depth}/{len(order)} body={name} "
                f"lambda={longitude_by_name[name]:.3f}deg "
                f"status={'evaluated' if s.get('started') else ('blocked-' + s['blocked'] if s.get('blocked') else 'not-evaluated')} "
'''

if text.count(needle) != 1:
    raise SystemExit(
        f"Safety stop: expected TERMINAL BODY format once; found {text.count(needle)}"
    )
text = text.replace(needle, replacement, 1)

path.write_text(text)
print("Added ecliptic longitude to every TERMINAL BODY diagnostic.")
