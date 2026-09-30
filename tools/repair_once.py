#!/usr/bin/env python3
"""One-shot repair: install the fast W36 Venus probe behind existing Repair Once.

No new workflow is created. Repair Once installs the diagnostic hook and probe,
then executes the probe immediately in the same already-registered workflow.
Production behavior is unchanged unless PLANET_FINDER_FAST_VENUS_PROBE=1.
"""
from pathlib import Path
import os
import subprocess
import sys

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

CORE = Path("tools/planet_finder_search_core.py")
text = CORE.read_text(encoding="utf-8")

hook = '''                if os.environ.get("PLANET_FINDER_FAST_VENUS_PROBE") == "1":
                    immutable = delta["immutable_reserved"] + delta["immutable_rim"]
                    placed = (delta["overlap"] + delta["leader_existing"] +
                              delta["route"] + delta["leader_rim"] + delta["leader_graze"])
                    summary = (
                        f"FAST W36 VENUS PROBE: generated={delta['generated']} "
                        f"viable={delta['viable']} immutable={immutable} placed={placed} "
                        f"detail[reserved={delta['immutable_reserved']},rim={delta['immutable_rim']},"
                        f"overlap={delta['overlap']},leader={delta['leader_existing']},"
                        f"route={delta['route']},leader-rim={delta['leader_rim']},"
                        f"graze={delta['leader_graze']}] "
                        f"uranus_box={delta['uranus_box']} uranus_path={delta['uranus_path']}"
                    )
                    print(summary, flush=True)
                    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
                    if summary_path:
                        with open(summary_path, "a", encoding="utf-8") as summary_file:
                            summary_file.write("### Fast W36 Venus probe\\n\\n" + summary + "\\n")
                    raise RuntimeError("FAST_W36_VENUS_PROBE_COMPLETE")
'''

if hook not in text:
    old = '''                uranus_venus_prefixes.append(delta)\n\n            backtracks += 1\n'''
    new = '''                uranus_venus_prefixes.append(delta)\n''' + hook + '''\n            backtracks += 1\n'''
    if text.count(old) != 1:
        raise SystemExit(f"Safety stop: Uranus/Venus probe anchor count={text.count(old)}; expected 1")
    text = text.replace(old, new, 1)
    CORE.write_text(text, encoding="utf-8")
else:
    print("Fast Venus hook already installed; reusing it.")

probe = Path("tools/fast_w36_venus_probe.py")
probe.write_text('''#!/usr/bin/env python3\nimport os\nimport sys\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\nsys.path.insert(0, str(ROOT / "tools"))\nsys.path.insert(0, str(ROOT / "tests"))\n\nfrom planet_finder_geometry import FinderMode\nfrom planet_finder_search import layout\nfrom test_planet_finder_system import synthetic_bodies\nfrom test_planet_finder_ultimate_ladders import W36_KNOWN_GOOD\n\nos.environ["PLANET_FINDER_DIAGNOSTIC_LEVEL"] = "0"\nos.environ["PLANET_FINDER_FAST_VENUS_PROBE"] = "1"\n\nbodies = synthetic_bodies(W36_KNOWN_GOOD)\ntry:\n    layout(FinderMode.GREEK, bodies, target_solutions=1,\n           budget={"max_node_candidates": 2000, "max_seconds": 15.0},\n           context_label="fast-W36-Venus-probe")\nexcept RuntimeError as exc:\n    if str(exc) == "FAST_W36_VENUS_PROBE_COMPLETE":\n        print("FAST W36 VENUS PROBE: COMPLETE", flush=True)\n        raise SystemExit(0)\n    raise\nraise SystemExit("Probe unexpectedly completed a layout before reaching the Uranus->Venus diagnostic point")\n''', encoding="utf-8")

# Run now, inside AA-Repair Once, so no new Actions workflow is needed.
result = subprocess.run([sys.executable, str(probe)], check=False)
if result.returncode != 0:
    raise SystemExit(result.returncode)

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print("Fast W36 Venus probe completed inside Repair Once; no workflow file created. Repair Once is now OFF.")
