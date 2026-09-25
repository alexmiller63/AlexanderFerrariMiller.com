from pathlib import Path

# Guarded one-shot repair for the shared forward-check probe budget.
path = Path("tools/planet_finder_search_core.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        '''        forward_stats["checks"] += 1\n\n\n        def witness_for(item, boxes, paths, obstacles_now):\n''',
        '''        forward_stats["checks"] += 1\n        # One raw-probe budget is shared by this entire forward-check call,\n        # including every individual-body witness and all child/grandchild\n        # look-ahead.  Reaching the cap means UNKNOWN, never dead.\n        forward_probe_used = 0\n\n        def consume_forward_probe():\n            nonlocal forward_probe_used\n            if forward_probe_used >= forward_probe_cap:\n                return False\n            forward_probe_used += 1\n            return True\n\n        def witness_for(item, boxes, paths, obstacles_now):\n''',
    ),
    (
        '''            for _, _, future_box in legal_candidate_positions(\n                future_longitude, w, h, reserved, displacement_scale\n            ):\n                if witness_raw >= forward_probe_cap:\n                    return PROBE_LIMITED, None, witness_raw, reasons\n                witness_raw += 1\n''',
        '''            for _, _, future_box in legal_candidate_positions(\n                future_longitude, w, h, reserved, displacement_scale\n            ):\n                if not consume_forward_probe():\n                    return PROBE_LIMITED, None, witness_raw, reasons\n                witness_raw += 1\n''',
    ),
    (
        '''            for _, _, child_box in legal_candidate_positions(\n                child_longitude, child_w, child_h, reserved, displacement_scale\n            ):\n                if child_raw >= forward_probe_cap:\n                    pair_found = True\n                    diagnostic_print(\n                        f"Planet Finder {mode}: FORWARD PAIR PROBE CAP child={child_name} "\n                        f"raw={child_raw:,}/{forward_probe_cap:,}; treating as unknown",\n                        level=2,\n                        flush=True,\n                    )\n                    break\n                child_raw += 1\n''',
        '''            for _, _, child_box in legal_candidate_positions(\n                child_longitude, child_w, child_h, reserved, displacement_scale\n            ):\n                if not consume_forward_probe():\n                    pair_found = True\n                    diagnostic_print(\n                        f"Planet Finder {mode}: FORWARD PAIR PROBE CAP child={child_name} "\n                        f"used={forward_probe_used:,}/{forward_probe_cap:,}; treating as unknown",\n                        level=2,\n                        flush=True,\n                    )\n                    break\n                child_raw += 1\n''',
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"guard failed: expected one match, found {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Patched forward checking so the raw-probe cap is shared by each entire forward-check call; cap exhaustion remains UNKNOWN, not dead.")
