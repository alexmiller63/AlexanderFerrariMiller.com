#!/usr/bin/env python3
"""One-shot: avoid duplicate routed forward proof at the final alignment pair."""

from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

old = """                if alignment_forward_ok and next_remaining:
                    forward_items = sorted(
"""
new = """                # At the final pair, do not run a separate existence probe.
                # The recursive call immediately below performs the same routed
                # proof authoritatively for the last member. Skipping that
                # duplicate positive probe is body-agnostic and changes neither
                # candidate order nor legality.
                if alignment_forward_ok and len(next_remaining) > 1:
                    forward_items = sorted(
"""
if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: expected alignment-forward gate count={text.count(old)}"
    )
text = text.replace(old, new, 1)
P.write_text(text, encoding="utf-8")

me = Path(__file__)
source = me.read_text(encoding="utf-8")
arming_line = "ENABLED" + " = True"
lines = source.splitlines()
matches = [i for i, line in enumerate(lines) if line.strip() == arming_line]
if len(matches) != 1:
    raise SystemExit(f"Safety stop: arming line count={len(matches)}")
lines[matches[0]] = "ENABLED = False"
me.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("Skipped duplicate final-pair alignment forward proof; Repair Once is OFF.")
