import subprocess
import sys

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

print("Running progressive W02 Planet Finder Greek regression ladder...")
result = subprocess.run([
    sys.executable, "-m", "pytest", "-vv", "-s",
    "tests/test_planet_finder_system.py::test_level_30_progressive_real_w02_greek_breakpoint",
])
raise SystemExit(result.returncode)
