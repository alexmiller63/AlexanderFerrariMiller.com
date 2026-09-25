from pathlib import Path

path = Path("tools/planet_finder_search_core.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        '''    forward_blockers = {}\n\n    def forward_check(next_depth):\n''',
        '''    forward_blockers = {}\n    # Forward checking is only a pruning hint.  Bound raw look-ahead work so\n    # a difficult body cannot monopolize the mode clock.  Hitting this cap is\n    # UNKNOWN, never proof that the branch is dead.\n    forward_probe_cap = max(\n        1, int(os.environ.get("PLANET_FINDER_FORWARD_PROBE_CAP", "1000"))\n    )\n    PROBE_LIMITED = object()\n\n    def forward_check(next_depth):\n''',
    ),
    (
        '''            for _, _, future_box in legal_candidate_positions(\n                future_longitude, w, h, reserved, displacement_scale\n            ):\n                witness_raw += 1\n''',
        '''            for _, _, future_box in legal_candidate_positions(\n                future_longitude, w, h, reserved, displacement_scale\n            ):\n                if witness_raw >= forward_probe_cap:\n                    return PROBE_LIMITED, None, witness_raw, reasons\n                witness_raw += 1\n''',
    ),
    (
        '''            future_box, future_path, witness_raw, witness_reasons = witness_for(\n                item, placed, leaders, obstacles\n            )\n            witness = future_box is not None\n''',
        '''            future_box, future_path, witness_raw, witness_reasons = witness_for(\n                item, placed, leaders, obstacles\n            )\n            if future_box is PROBE_LIMITED:\n                diagnostic_print(\n                    f"Planet Finder {mode}: FORWARD PROBE CAP body={future_name} "\n                    f"raw={witness_raw:,}/{forward_probe_cap:,}; treating as unknown",\n                    level=2,\n                    flush=True,\n                )\n                continue\n            witness = future_box is not None\n''',
    ),
    (
        '''            for _, _, child_box in legal_candidate_positions(\n                child_longitude, child_w, child_h, reserved, displacement_scale\n            ):\n                child_raw += 1\n''',
        '''            for _, _, child_box in legal_candidate_positions(\n                child_longitude, child_w, child_h, reserved, displacement_scale\n            ):\n                if child_raw >= forward_probe_cap:\n                    pair_found = True\n                    diagnostic_print(\n                        f"Planet Finder {mode}: FORWARD PAIR PROBE CAP child={child_name} "\n                        f"raw={child_raw:,}/{forward_probe_cap:,}; treating as unknown",\n                        level=2,\n                        flush=True,\n                    )\n                    break\n                child_raw += 1\n''',
    ),
    (
        '''                grandchild_box, grandchild_path, grandchild_raw, grandchild_reasons = witness_for(\n                    grandchild_item,\n                    [*placed, child_box],\n                    [*leaders, child_path],\n                    [*obstacles, child_box],\n                )\n                grandchild_raw_total += grandchild_raw\n                if grandchild_box is not None:\n                    pair_found = True\n                    break\n''',
        '''                grandchild_box, grandchild_path, grandchild_raw, grandchild_reasons = witness_for(\n                    grandchild_item,\n                    [*placed, child_box],\n                    [*leaders, child_path],\n                    [*obstacles, child_box],\n                )\n                grandchild_raw_total += grandchild_raw\n                if grandchild_box is PROBE_LIMITED:\n                    pair_found = True\n                    diagnostic_print(\n                        f"Planet Finder {mode}: FORWARD PROBE CAP body={grandchild_name} "\n                        f"raw={grandchild_raw:,}/{forward_probe_cap:,}; treating as unknown",\n                        level=2,\n                        flush=True,\n                    )\n                    break\n                if grandchild_box is not None:\n                    pair_found = True\n                    break\n''',
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"guard failed: expected one match, found {count}: {old[:80]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Patched forward checking with a bounded raw-probe cap; cap exhaustion is UNKNOWN, not dead.")
