from pathlib import Path

ENABLED = True

if not ENABLED:
print(“Repair Once is OFF; nothing to do.”)
raise SystemExit(0)

path = Path(“tools/planet_finder_search.py”)
text = path.read_text()

needle = ‘’’                for i, event in enumerate(refinement_history, 1):
‘’’

insert = ‘’’                if closest_pair is not None:
separation, left_name, right_name, left_lambda, right_lambda = closest_pair
diagnostic_print(
f”Planet Finder {mode}: TERMINAL CLOSEST ECLIPTIC PAIR “
f”{left_name} lambda={left_lambda:.3f} deg; “
f”{right_name} lambda={right_lambda:.3f} deg; “
f”separation={separation:.3f} deg”,
flush=True,
)
for i, event in enumerate(refinement_history, 1):
‘’’

if text.count(needle) != 1:
raise SystemExit(
f”Safety stop: expected terminal history insertion point once; found {text.count(needle)}”
)

text = text.replace(needle, insert, 1)
path.write_text(text)

print(“Added closest-pair separation to terminal diagnostics.”)