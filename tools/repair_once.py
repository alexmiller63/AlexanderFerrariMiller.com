from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

needle = '''                raise RuntimeError(
                    f"Planet Finder {mode} mode wall-clock budget exhausted "
                    f"during candidate generation for {name} after {run_elapsed:.1f}s "
'''

replacement = '''                dump_diagnostics("wall-clock")
                raise RuntimeError(
                    f"Planet Finder {mode} mode wall-clock budget exhausted "
                    f"during candidate generation for {name} after {run_elapsed:.1f}s "
'''

if text.count(needle) != 1:
    raise SystemExit(
        f"Safety stop: expected candidate-generation timeout once; found {text.count(needle)}"
    )

text = text.replace(needle, replacement, 1)
path.write_text(text)

print("Added full terminal diagnostic before candidate-generation wall-clock exception.")
