#!/usr/bin/env python3
"""One-shot: add blocker identities to forward-check terminal diagnostics."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Safety stop: {label} anchor count={count}")
    text = text.replace(old, new, 1)

replace_once(
    '    forward_stats = {"checks": 0, "pruned": 0, "witnesses": 0, "by_body": {}}\n',
    '    forward_stats = {"checks": 0, "pruned": 0, "witnesses": 0, "by_body": {}}\n'
    '    # Diagnostic only: blocker identities for forward candidate rejection.\n'
    '    forward_blocker_names = {}\n',
    "forward blocker store",
)

replace_once(
    '        def witness_for(item, boxes, paths, obstacles_now):\n',
    '        def witness_for(item, boxes, paths, obstacles_now, collect_blockers=True):\n',
    "witness signature",
)

replace_once(
    '                if overlap_hits:\n'
    '                    reasons["placed-overlap"] += 1\n',
    '                if overlap_hits:\n'
    '                    reasons["placed-overlap"] += 1\n'
    '                    if collect_blockers:\n'
    '                        buckets = forward_blocker_names.setdefault(future_name, {"placed-overlap": {}, "existing-leader": {}, "leader-graze": {}})\n'
    '                        for i in overlap_hits:\n'
    '                            blocker = leader_names[i] if i < len(leader_names) else f"placed_{i}"\n'
    '                            counts = buckets["placed-overlap"]\n'
    '                            counts[blocker] = counts.get(blocker, 0) + 1\n',
    "overlap blockers",
)

replace_once(
    '                if leader_hits:\n'
    '                    reasons["existing-leader"] += 1\n',
    '                if leader_hits:\n'
    '                    reasons["existing-leader"] += 1\n'
    '                    if collect_blockers:\n'
    '                        buckets = forward_blocker_names.setdefault(future_name, {"placed-overlap": {}, "existing-leader": {}, "leader-graze": {}})\n'
    '                        for j in leader_hits:\n'
    '                            blocker = leader_names[j] if j < len(leader_names) else f"leader_{j}"\n'
    '                            counts = buckets["existing-leader"]\n'
    '                            counts[blocker] = counts.get(blocker, 0) + 1\n',
    "existing leader blockers",
)

replace_once(
    '                if leaders_too_close(path, paths):\n'
    '                    reasons["leader-graze"] += 1\n'
    '                    if future_name == "Ceres":\n',
    '                if leaders_too_close(path, paths):\n'
    '                    reasons["leader-graze"] += 1\n'
    '                    if collect_blockers:\n'
    '                        _, blocker_pair = minimum_leader_separation(path, paths)\n'
    '                        if blocker_pair is not None:\n'
    '                            j = blocker_pair[0]\n'
    '                            blocker = leader_names[j] if j < len(leader_names) else f"leader_{j}"\n'
    '                            buckets = forward_blocker_names.setdefault(future_name, {"placed-overlap": {}, "existing-leader": {}, "leader-graze": {}})\n'
    '                            counts = buckets["leader-graze"]\n'
    '                            counts[blocker] = counts.get(blocker, 0) + 1\n'
    '                    if future_name == "Ceres":\n',
    "leader graze blockers",
)

replace_once(
    '                    parentless_box, _, _, _ = witness_for(\n'
    '                        item, placed[:-1], leaders[:-1], [*reserved, *placed[:-1]]\n'
    '                    )\n',
    '                    parentless_box, _, _, _ = witness_for(\n'
    '                        item, placed[:-1], leaders[:-1], [*reserved, *placed[:-1]],\n'
    '                        collect_blockers=False,\n'
    '                    )\n',
    "parentless diagnostic isolation",
)

needle = '''            diagnostic_print(
                f"Planet Finder {mode}: FORWARD BODY body={body} "
                f"checks={stat['checks']:,} dead={stat['dead']:,} raw={stat['raw']:,} "
                f"placed-overlap={reasons.get('placed-overlap', 0):,} "
                f"existing-leader={reasons.get('existing-leader', 0):,} "
                f"route={reasons.get('route', 0):,} "
                f"leader-rim={reasons.get('leader-rim', 0):,} "
                f"leader-graze={reasons.get('leader-graze', 0):,}",
                flush=True,
            )
'''
replacement = needle + '''            blocker_buckets = forward_blocker_names.get(body, {})
            if blocker_buckets:
                def ranked_forward_blockers(kind):
                    return ",".join(
                        f"{name}={count:,}"
                        for name, count in sorted(
                            blocker_buckets.get(kind, {}).items(),
                            key=lambda item: (-item[1], item[0]),
                        )
                    ) or "-"
                diagnostic_print(
                    f"Planet Finder {mode}: FORWARD BODY BLOCKERS body={body} "
                    f"placed-overlap=[{ranked_forward_blockers('placed-overlap')}] "
                    f"existing-leader=[{ranked_forward_blockers('existing-leader')}] "
                    f"leader-graze=[{ranked_forward_blockers('leader-graze')}]",
                    flush=True,
                )
'''
replace_once(needle, replacement, "terminal blocker report")

P.write_text(text, encoding="utf-8")
me = Path(__file__)
me.write_text(me.read_text(encoding="utf-8").replace("ENABLED = True", "ENABLED = False", 1), encoding="utf-8")
print("Added forward blocker identity diagnostics; Repair Once is now OFF.")
