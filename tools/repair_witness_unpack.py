#!/usr/bin/env python3
from pathlib import Path

p = Path(__file__).with_name("generate_planet_finders.py")
s = p.read_text(encoding="utf-8")
old = """                grandchild_box, grandchild_path, grandchild_raw = witness_for(\n"""
new = """                grandchild_box, grandchild_path, grandchild_raw, grandchild_reasons = witness_for(\n"""
if s.count(old) != 1:
    raise SystemExit(f"Expected exactly one stale witness unpack, found {s.count(old)}")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("Repaired witness_for() unpacking")
