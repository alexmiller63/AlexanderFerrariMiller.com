from pathlib import Path

PATH = Path("tools/planet_finder_search_core.py")
text = PATH.read_text()

old_sig = "    def viable_candidates(item, depth):\n"
new_sig = "    def viable_candidates(item, depth, *, consume_body_budget=True):\n"
if old_sig not in text:
    raise SystemExit("viable_candidates signature guard not found")
text = text.replace(old_sig, new_sig, 1)

old_pre_cap = '''            if body_attempts[name] >= budget["max_node_candidates"]:\n                stats["blocked"] = "body-candidate-cap"\n                diagnostic_print(\n                    f"Planet Finder {mode}: BODY-CANDIDATE CAP order={order_index} "\n                    f"depth={depth}/{len(order)} body={name} "\n                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,}",\n                    flush=True,\n                )\n                raise DepthNodeBudgetExhausted(depth, name)\n'''
new_pre_cap = '''            if consume_body_budget and body_attempts[name] >= budget["max_node_candidates"]:\n                stats["blocked"] = "body-candidate-cap"\n                diagnostic_print(\n                    f"Planet Finder {mode}: BODY-CANDIDATE CAP order={order_index} "\n                    f"depth={depth}/{len(order)} body={name} "\n                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,}",\n                    flush=True,\n                )\n                raise DepthNodeBudgetExhausted(depth, name)\n'''
if text.count(old_pre_cap) != 1:
    raise SystemExit(f"expected one pre-yield body cap block, found {text.count(old_pre_cap)}")
text = text.replace(old_pre_cap, new_pre_cap, 1)

old_count = '''            body_candidates += 1\n            body_attempts[name] += 1\n            stats["generated"] += 1\n            stats["viable"] += 1\n            last_yield_at = time.monotonic()\n            yield box, path\n            if body_attempts[name] >= budget["max_node_candidates"]:\n                stats["blocked"] = "body-candidate-cap"\n                diagnostic_print(\n                    f"Planet Finder {mode}: BODY-CANDIDATE CAP order={order_index} "\n                    f"depth={depth}/{len(order)} body={name} "\n                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,}",\n                    flush=True,\n                )\n                raise DepthNodeBudgetExhausted(depth, name)\n'''
new_count = '''            body_candidates += 1\n            if consume_body_budget:\n                body_attempts[name] += 1\n            stats["generated"] += 1\n            stats["viable"] += 1\n            last_yield_at = time.monotonic()\n            yield box, path\n            if consume_body_budget and body_attempts[name] >= budget["max_node_candidates"]:\n                stats["blocked"] = "body-candidate-cap"\n                diagnostic_print(\n                    f"Planet Finder {mode}: BODY-CANDIDATE CAP order={order_index} "\n                    f"depth={depth}/{len(order)} body={name} "\n                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,}",\n                    flush=True,\n                )\n                raise DepthNodeBudgetExhausted(depth, name)\n'''
if text.count(old_count) != 1:
    raise SystemExit(f"expected one viable-candidate accounting block, found {text.count(old_count)}")
text = text.replace(old_count, new_count, 1)

marker = '''        return True\n\n    def search(depth):\n'''
helper = '''        return True\n\n    def solve_final_body(last_depth):\n        """Solve the final body directly against the placed penultimate body.\n\n        The ordinary per-body cap is deliberately not charged here. At this\n        point the task is a bounded compatibility join between the final two\n        bodies, not a new ordering search. This avoids repeatedly exhausting\n        Sun/Venus-style endgames after the first nine bodies are already fixed.\n        """\n        nonlocal candidates, backtracks, current_body\n        item = order[last_depth]\n        original_index, (symbol, name, longitude) = item\n        current_body = name\n        diagnostic_print(\n            f"Planet Finder {mode}: TWO-BODY ENDGAME penultimate={order[last_depth - 1][1][1]} "\n            f"final={name} depth={last_depth}/{len(order)}",\n            level=2,\n            flush=True,\n        )\n\n        for box, path in viable_candidates(item, last_depth, consume_body_budget=False):\n            candidates += 1\n            placed.append(box)\n            leaders.append(path)\n            leader_names.append(name)\n            staged[original_index] = (symbol, name, longitude, box, path)\n            try:\n                if search(len(order)):\n                    return True\n            finally:\n                staged.pop(original_index, None)\n                leaders.pop()\n                leader_names.pop()\n                placed.pop()\n            backtracks += 1\n        return False\n\n    def search(depth):\n'''
if marker not in text:
    raise SystemExit("search insertion guard not found")
text = text.replace(marker, helper, 1)

old_search = '''                if forward_check(depth + 1) and search(depth + 1):\n                    return True\n'''
new_search = '''                if depth == len(order) - 2:\n                    if solve_final_body(depth + 1):\n                        return True\n                elif forward_check(depth + 1) and search(depth + 1):\n                    return True\n'''
if text.count(old_search) != 1:
    raise SystemExit(f"expected one forward-check recursion block, found {text.count(old_search)}")
text = text.replace(old_search, new_search, 1)

PATH.write_text(text)
print("Applied Planet Finder two-body endgame solver patch")
