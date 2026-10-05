from pathlib import Path

PATH = Path("tools/planet_finder_search_core.py")
s = PATH.read_text(encoding="utf-8")

needle = '''        nodes += 1
        deepest = max(deepest, depth)
        depth_visits[depth] = depth_visits.get(depth, 0) + 1

        if depth == len(order):
'''

replacement = '''        nodes += 1
        deepest = max(deepest, depth)
        depth_visits[depth] = depth_visits.get(depth, 0) + 1

        # Diagnostic-only W17 Venus depth trace.  At every committed DFS
        # prefix, exhaustively count Venus candidates against exactly that
        # prefix.  This exposes the first positive -> zero transition and the
        # newly committed body that caused it.  The trace is opt-in and never
        # participates in normal search decisions.
        if os.environ.get("PLANET_FINDER_VENUS_DEPTH_TRACE") == "1":
            venus_item = next(
                (
                    item for future_depth, item in enumerate(order)
                    if future_depth >= depth
                    and item[0] not in staged
                    and item[1][1] == "Venus"
                ),
                None,
            )
            if venus_item is not None:
                before_stats = dict(diagnostic_stats.get((depth, "Venus"), {}))
                venus_count = 0
                venus_probe = viable_candidates(
                    venus_item, depth, consume_body_budget=False
                )
                try:
                    for _ in venus_probe:
                        venus_count += 1
                finally:
                    venus_probe.close()
                after_stats = diagnostic_stats.get((depth, "Venus"), {})
                keys = (
                    "generated", "viable", "immutable_reserved", "immutable_rim",
                    "overlap", "leader_existing", "route", "leader_rim",
                    "leader_graze",
                )
                delta = {
                    key: after_stats.get(key, 0) - before_stats.get(key, 0)
                    for key in keys
                }
                parent = leader_names[-1] if leader_names else "ROOT"
                diagnostic_print(
                    f"Planet Finder {mode}: VENUS DEPTH TRACE "
                    f"depth={depth}/{len(order)} parent={parent} "
                    f"prefix={'|'.join(leader_names) or 'ROOT'} "
                    f"viable={venus_count} generated={delta['generated']} "
                    f"rejects[reserved={delta['immutable_reserved']},"
                    f"rim={delta['immutable_rim']},overlap={delta['overlap']},"
                    f"existing-leader={delta['leader_existing']},"
                    f"route={delta['route']},leader-rim={delta['leader_rim']},"
                    f"leader-graze={delta['leader_graze']}]",
                    level=1, flush=True,
                )
                if venus_count == 0:
                    raise RuntimeError(
                        f"VENUS_DEPTH_TRACE_ZERO depth={depth} parent={parent} "
                        f"prefix={'|'.join(leader_names) or 'ROOT'}"
                    )

        if depth == len(order):
'''

if s.count(needle) != 1:
    raise SystemExit(f"guard count={s.count(needle)}; expected 1")

PATH.write_text(s.replace(needle, replacement, 1), encoding="utf-8")
print("Instrumented Venus viability by DFS depth; opt in with PLANET_FINDER_VENUS_DEPTH_TRACE=1")
