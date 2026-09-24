from pathlib import Path

path = Path("tools/generate_planet_finders.py")
text = path.read_text(encoding="utf-8")

old = '''            for _, _, future_box in legal_candidate_positions(
                future_longitude, w, h, reserved, displacement_scale
            ):
                witness_raw += 1
'''
new = '''            for _, _, future_box in legal_candidate_positions(
                future_longitude, w, h, reserved, displacement_scale
            ):
                # Forward checking can scan a large raw candidate stream.  It
                # must obey the same refinement slice and mode wall clock as
                # the real DFS; otherwise look-ahead can monopolize the clock
                # after DFS has already reached its deadline.
                now = time.monotonic()
                if refinement_deadline is not None and now >= refinement_deadline:
                    diagnostic_print(
                        f"Planet Finder {mode}: FORWARD-CHECK REFINEMENT DEADLINE "
                        f"order={order_index} future-depth={future_depth}/{len(order)} "
                        f"body={future_name}; returning to controller",
                        flush=True,
                    )
                    return False
                if now - budget["started"] >= budget["max_seconds"]:
                    raise RuntimeError(
                        f"Planet Finder {mode} mode wall-clock budget exhausted "
                        f"during forward check for {future_name} "
                        f"(limit {budget['max_seconds']:.1f}s)"
                    )
                witness_raw += 1
'''

if text.count(old) != 1:
    raise SystemExit(f"guard failed: expected one forward-check loop, found {text.count(old)}")

path.write_text(text.replace(old, new), encoding="utf-8")
print("Patched forward_check to enforce refinement and mode deadlines.")
