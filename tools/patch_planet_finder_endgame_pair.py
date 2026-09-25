from pathlib import Path

PATH = Path("tools/planet_finder_search_core.py")
text = PATH.read_text()

old_sig = (
    "    def viable_candidates(item, depth, *, consume_body_budget=True, "
    "raw_probe_state=None, raw_probe_cap=None):\n"
)
new_sig = "    def viable_candidates(item, depth, *, consume_body_budget=True):\n"
if text.count(old_sig) != 1:
    raise SystemExit(f"expected one capped viable_candidates signature, found {text.count(old_sig)}")
text = text.replace(old_sig, new_sig, 1)

old_raw = '''            raw_positions += 1\n            if raw_probe_state is not None:\n                raw_probe_state["used"] = raw_probe_state.get("used", 0) + 1\n                if raw_probe_cap is not None and raw_probe_state["used"] > raw_probe_cap:\n                    blocker = raw_probe_state.get("blocker", name)\n                    label = raw_probe_state.get("label", name)\n                    diagnostic_print(\n                        f"Planet Finder {mode}: TWO-BODY ENDGAME RAW CAP "\n                        f"pair={label} used={raw_probe_cap:,}/{raw_probe_cap:,}; "\n                        "treating as capped/unknown",\n                        level=1,\n                        flush=True,\n                    )\n                    raise DepthNodeBudgetExhausted(depth, blocker)\n\n            # Narrow instrumentation for pathological candidate generation.\n'''
new_raw = '''            raw_positions += 1\n\n            # Narrow instrumentation for pathological candidate generation.\n'''
if text.count(old_raw) != 1:
    raise SystemExit(f"expected one raw-probe cap block, found {text.count(old_raw)}")
text = text.replace(old_raw, new_raw, 1)

start = text.find("    def solve_final_pair(first_depth):\n")
end = text.find("\n    def search(depth):\n", start)
if start < 0 or end < 0:
    raise SystemExit("solve_final_pair block guard not found")

new_helper = '''    def solve_final_pair(first_depth):\n        """Solve the final two bodies until success, exhaustion, or mode deadline.\n\n        Neither member consumes the ordinary per-body DFS budget. The existing\n        mode/refinement deadline remains authoritative, so the endgame is not\n        cut short by a separate raw-probe limit.\n        """\n        nonlocal candidates, backtracks, current_body\n        first_item = order[first_depth]\n        second_item = order[first_depth + 1]\n        first_index, (first_symbol, first_name, first_longitude) = first_item\n        second_index, (second_symbol, second_name, second_longitude) = second_item\n        pair_attempts = 0\n        current_body = first_name\n        diagnostic_print(\n            f"Planet Finder {mode}: TWO-BODY ENDGAME pair={first_name}+{second_name} "\n            f"depth={first_depth}/{len(order)} deadline-controlled",\n            level=1,\n            flush=True,\n        )\n\n        for first_box, first_path in viable_candidates(\n            first_item,\n            first_depth,\n            consume_body_budget=False,\n        ):\n            candidates += 1\n            placed.append(first_box)\n            leaders.append(first_path)\n            leader_names.append(first_name)\n            staged[first_index] = (\n                first_symbol, first_name, first_longitude, first_box, first_path\n            )\n            try:\n                current_body = second_name\n                for second_box, second_path in viable_candidates(\n                    second_item,\n                    first_depth + 1,\n                    consume_body_budget=False,\n                ):\n                    pair_attempts += 1\n                    candidates += 1\n                    placed.append(second_box)\n                    leaders.append(second_path)\n                    leader_names.append(second_name)\n                    staged[second_index] = (\n                        second_symbol, second_name, second_longitude,\n                        second_box, second_path,\n                    )\n                    try:\n                        if search(len(order)):\n                            return True\n                    finally:\n                        staged.pop(second_index, None)\n                        leaders.pop()\n                        leader_names.pop()\n                        placed.pop()\n                    backtracks += 1\n            finally:\n                staged.pop(first_index, None)\n                leaders.pop()\n                leader_names.pop()\n                placed.pop()\n            backtracks += 1\n        return False\n'''
text = text[:start] + new_helper + text[end:]

PATH.write_text(text)
print("Removed Planet Finder two-body raw-probe cap; endgame now uses mode deadline")
