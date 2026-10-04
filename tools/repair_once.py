#!/usr/bin/env python3
"""One-shot: safely cache beat-limited alignment routed prefixes."""

from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

old = '''            if cached_rows is not None:
                cached_rows, cutoff = cached_rows
                count = len(cached_rows)
            else:
'''
new = '''            # Beat-limited prefixes are lower bounds, never exact domains.
            full_rank_limit = budget["max_node_candidates"]
            rank_limit = full_rank_limit
            beat_limited = False
            if best_count is not None:
                rank_limit = min(full_rank_limit, best_count + 2)
                beat_limited = rank_limit < full_rank_limit
            if cached_rows is not None:
                cached_values, cutoff, cached_prefix = cached_rows
                if cached_prefix and len(cached_values) < rank_limit:
                    cached_rows = None
                    cache_stat["hits"] -= 1
                    cache_stat["misses"] += 1
                else:
                    cached_rows = cached_values
                    count = min(len(cached_values), rank_limit) if cached_prefix else len(cached_values)
            if cached_rows is None:
'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: expected cache-read block count={text.count(old)}")
text = text.replace(old, new, 1)

old_limits = '''                full_rank_limit = budget["max_node_candidates"]
                rank_limit = full_rank_limit
                beat_limited = False
                if best_count is not None:
                    rank_limit = min(full_rank_limit, best_count + 2)
                    beat_limited = rank_limit < full_rank_limit
'''
if text.count(old_limits) != 1:
    raise SystemExit(f"Safety stop: expected rank-limit block count={text.count(old_limits)}")
text = text.replace(old_limits, "", 1)

old_store = '''                    if beat_limited:
                        cache_stat["beat_limited"] += 1
                        cache_stat["beat_limits"][rank_limit] = (
                            cache_stat["beat_limits"].get(rank_limit, 0) + 1
                        )
                        state_shape = (len(placed), len(leaders), len(leader_names))
                        cache_stat["state_shapes"][state_shape] = (
                            cache_stat["state_shapes"].get(state_shape, 0) + 1
                        )
                    else:
                        alignment_routed_domain_cache[cache_key] = (tuple(collected), cutoff)
                        cache_stat["stored"] += 1
'''
new_store = '''                    if beat_limited:
                        cache_stat["beat_limited"] += 1
                        cache_stat["beat_limits"][rank_limit] = (
                            cache_stat["beat_limits"].get(rank_limit, 0) + 1
                        )
                        state_shape = (len(placed), len(leaders), len(leader_names))
                        cache_stat["state_shapes"][state_shape] = (
                            cache_stat["state_shapes"].get(state_shape, 0) + 1
                        )
                        alignment_routed_domain_cache[cache_key] = (
                            tuple(collected), cutoff, True
                        )
                        cache_stat["stored"] += 1
                    else:
                        alignment_routed_domain_cache[cache_key] = (
                            tuple(collected), cutoff, False
                        )
                        cache_stat["stored"] += 1
'''
if text.count(old_store) != 1:
    raise SystemExit(f"Safety stop: expected cache-store block count={text.count(old_store)}")
text = text.replace(old_store, new_store, 1)

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

print("Cached beat-limited routed prefixes as lower bounds; Repair Once is OFF.")
