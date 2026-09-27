#!/usr/bin/env python3
"""One-shot diagnostic: expose conjunction lambda-order angle behavior."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

p = Path("tools/planet_finder_search_core.py")
s = p.read_text()

old = '''        conjunction_attempts_by_body = {name: 0 for name in ordered_names}
        conjunction_route_diagnostics = {}

        def label_angle(row):
'''
new = '''        conjunction_attempts_by_body = {name: 0 for name in ordered_names}
        conjunction_route_diagnostics = {}
        # Diagnostic only: characterize the circular-angle relation that the
        # lambda-order gate accepts/rejects.  Do not alter solver decisions.
        lambda_order_diag = {
            "accepted": 0,
            "rejected": 0,
            "accepted_delta_min": None,
            "accepted_delta_max": None,
            "rejected_delta_min": None,
            "rejected_delta_max": None,
            "accepted_samples": [],
            "rejected_samples": [],
        }

        def label_angle(row):
'''
if s.count(old) != 1:
    raise SystemExit(f"Safety stop: expected lambda diagnostic insertion marker once; found {s.count(old)}")
s = s.replace(old, new, 1)

old = '''                chosen[name] = row
                if not preserves_lambda_order():
                    diagnostic_rejections["lambda_order"] += 1
                    conjunction_rejections_by_body[name]["lambda_order"] += 1
                    chosen.pop(name, None)
                    continue
'''
new = '''                chosen[name] = row
                lambda_ok = preserves_lambda_order()
                if len(chosen) >= 2:
                    present = [n for n in ordered_names if n in chosen]
                    reference = group_items[0][1][2] - 90.0
                    normalized = [((label_angle(chosen[n]) - reference) % 360.0) for n in present]
                    # For the current two-body barrier this is the signed
                    # normalized separation tested by the monotonic gate.
                    delta = normalized[-1] - normalized[-2]
                    bucket = "accepted" if lambda_ok else "rejected"
                    lambda_order_diag[bucket] += 1
                    lo_key = f"{bucket}_delta_min"
                    hi_key = f"{bucket}_delta_max"
                    old_lo = lambda_order_diag[lo_key]
                    old_hi = lambda_order_diag[hi_key]
                    lambda_order_diag[lo_key] = delta if old_lo is None else min(old_lo, delta)
                    lambda_order_diag[hi_key] = delta if old_hi is None else max(old_hi, delta)
                    samples = lambda_order_diag[f"{bucket}_samples"]
                    if len(samples) < 8:
                        samples.append({
                            "names": tuple(present),
                            "raw_angles": tuple(round(label_angle(chosen[n]), 3) for n in present),
                            "normalized": tuple(round(v, 3) for v in normalized),
                            "delta": round(delta, 3),
                        })
                if not lambda_ok:
                    diagnostic_rejections["lambda_order"] += 1
                    conjunction_rejections_by_body[name]["lambda_order"] += 1
                    chosen.pop(name, None)
                    continue
'''
if s.count(old) != 1:
    raise SystemExit(f"Safety stop: expected lambda gate marker once; found {s.count(old)}")
s = s.replace(old, new, 1)

old = '''                f"rejections_by_body={conjunction_rejections_by_body} "
                f"rejections={diagnostic_rejections} "
                f"route_detail={route_summary} "
'''
new = '''                f"rejections_by_body={conjunction_rejections_by_body} "
                f"rejections={diagnostic_rejections} "
                f"lambda_order_detail={lambda_order_diag} "
                f"route_detail={route_summary} "
'''
if s.count(old) != 1:
    raise SystemExit(f"Safety stop: expected failure-summary marker once; found {s.count(old)}")
s = s.replace(old, new, 1)

p.write_text(s)
me = Path(__file__)
me.write_text(me.read_text().replace("ENABLED = True", "ENABLED = False", 1))
print("Installed conjunction lambda-order diagnostics; Repair Once is now OFF.")
