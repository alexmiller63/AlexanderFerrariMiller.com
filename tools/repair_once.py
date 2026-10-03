#!/usr/bin/env python3
"""One-shot: report alignment state repetition before deadline exit."""

from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")
needle = '''        if refinement_timed_out:
        dump_diagnostics("refinement deadline reached before search completed")
'''
replacement = '''        if refinement_timed_out:
        probe_total = sum(alignment_probe_signatures.values())
        probe_unique = len(alignment_probe_signatures)
        probe_repeated = probe_total - probe_unique
        top_repeats = sorted(
            (
                (count, key[0] + 1, key[1], key[2])
                for key, count in alignment_probe_signatures.items()
                if count > 1
            ),
            reverse=True,
        )[:12]
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT STATE REPETITION DEADLINE "
            f"evaluations={probe_total:,} unique={probe_unique:,} repeated={probe_repeated:,} "
            f"repeat_pct={(100.0 * probe_repeated / probe_total if probe_total else 0.0):.1f}% "
            f"top={top_repeats}",
            level=1, flush=True,
        )
        report_alignment_phase_profile()
        dump_diagnostics("refinement deadline reached before search completed")
'''
if text.count(needle) != 1:
    raise SystemExit("Safety stop: deadline diagnostic insertion point missing or non-unique")
P.write_text(text.replace(needle, replacement, 1), encoding="utf-8")

me = Path(__file__)
source = me.read_text(encoding="utf-8")
needle = "\nENABLED = True\n"
if source.count(needle) != 1:
    raise SystemExit("Safety stop: ENABLED assignment not unique")
me.write_text(source.replace(needle, "\nENABLED = False\n", 1), encoding="utf-8")
print("Installed alignment deadline repetition diagnostics; Repair Once is OFF.")
