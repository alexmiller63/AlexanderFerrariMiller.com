from pathlib import Path

GEOMETRY = Path("tools/planet_finder_geometry.py")
SEARCH = Path("tools/planet_finder_search.py")

p = GEOMETRY
s = p.read_text()
start = s.index("def candidate_positions(longitude: float, displacement_scale: float = 2.0):\n")
end = s.index("\ndef legal_candidate_positions(", start)
new = '''def candidate_positions(longitude: float, displacement_scale: float = 2.0):
    """Yield each canonical label candidate once, cheapest geometry first.

    displacement_scale remains temporarily for API compatibility, but the
    complete lattice is always 0, +/-0.25, ... +/-2.00 label lengths.
    """
    theta = math.radians(180 + longitude)
    tx, ty = -math.sin(theta), -math.cos(theta)
    offered: list[tuple[float, float]] = []
    radii = (*PREFERRED_LABEL_RADII, *EXPANDED_LABEL_RADII)
    quarter_step = LABEL_LENGTH * 0.25
    for shell in range(9):
        shifts = (0.0,) if shell == 0 else (-shell * quarter_step, shell * quarter_step)
        for shift in shifts:
            for r in radii:
                bx, by = xy(longitude, r)
                x, y = bx + shift * tx, by + shift * ty
                if any(math.hypot(x - ox, y - oy) < 1e-9 for ox, oy in offered):
                    continue
                offered.append((x, y))
                yield x, y

'''
s = s[:start] + new + s[end + 1:]
p.write_text(s)

p = SEARCH
s = p.read_text()
start = s.index("    order = indexed\n")
end = s.index("    if not all_solutions:\n", start)
new = '''    order = indexed
    all_solutions = []
    contest_keys = []
    order_index = 0
    attempted_orders = set()
    body_attempts = {name: 0 for _, (_, name, _) in indexed}
    search_history = []
    state = "SEARCH_ORDER"
    promote_body = None

    def terminal_search(reason):
        final_sequence = " > ".join(item[1][1] for item in order)
        diagnostic_print(
            f"Planet Finder {mode}: TERMINAL SEARCH DIAGNOSTIC "
            f"reason={reason} attempts={len(search_history)} final-sequence={final_sequence}",
            flush=True,
        )
        raise RuntimeError(
            f"Planet Finder {mode}: canonical candidate lattice exhausted; {reason}; "
            "see TERMINAL SEARCH DIAGNOSTIC above"
        )

    def next_promotion_order(current_order, body_name):
        body_index = next((i for i, item in enumerate(current_order) if item[1][1] == body_name), None)
        if body_index is None:
            return "MISSING", None
        if body_index == 0:
            return "AT_FRONT", None
        candidate = list(current_order)
        candidate[body_index - 1], candidate[body_index] = candidate[body_index], candidate[body_index - 1]
        names = tuple(item[1][1] for item in candidate)
        if names in attempted_orders:
            return "CYCLE", candidate
        return "PROMOTE", candidate

    while state != "SCORE":
        now = time.monotonic()
        if now - budget["started"] >= budget["max_seconds"]:
            raise RuntimeError(
                f"Planet Finder {mode} mode wall-clock budget exhausted "
                f"(limit {budget['max_seconds']:.1f}s)"
            )

        if state == "PROMOTE":
            transition, promoted_order = next_promotion_order(order, promote_body)
            if transition == "AT_FRONT":
                terminal_search(f"blocker {promote_body} already promoted to position 0")
            elif transition == "PROMOTE":
                promoted_names = tuple(item[1][1] for item in promoted_order)
                order = promoted_order
                body_attempts[promote_body] = 0
                diagnostic_print(
                    f"Planet Finder {mode}: PROMOTE body={promote_body}; moved left one lambda neighbor; "
                    "restarting sequence=" + " > ".join(promoted_names), flush=True,
                )
                state = "SEARCH_ORDER"
            elif transition == "CYCLE":
                terminal_search(f"ordering cycle while promoting {promote_body}")
            else:
                raise RuntimeError(
                    f"Planet Finder {mode}: controller invariant violated: blocker "
                    f"{promote_body!r} is absent from the recursive search order"
                )
            continue

        if state != "SEARCH_ORDER":
            raise RuntimeError(f"Planet Finder {mode}: invalid controller state {state}")

        order_names = tuple(item[1][1] for item in order)
        if order_names in attempted_orders:
            terminal_search("repeated ordering in single canonical lattice")
        attempted_orders.add(order_names)
        order_index += 1
        diagnostic_print(
            f"Planet Finder {mode}: squeaky-wheel lazy DFS "
            f"{context_label + ' ' if context_label else ''}"
            f"order={order_index} target={target_solutions} "
            f"max-node-candidates={budget['max_node_candidates']:,} "
            f"candidate-lattice=0,+/-0.25,...,+/-2.00 label-lengths sequence="
            + " > ".join(order_names), flush=True,
        )

        try:
            outcome = _solve_order(
                mode, bodies, order, budget,
                target_solutions=target_solutions,
                order_index=order_index,
                total_orders=None,
                context_label=context_label,
                displacement_scale=0.25,
                body_attempts=body_attempts,
                refinement_deadline=budget["started"] + budget["max_seconds"],
            )
        except DepthNodeBudgetExhausted as exc:
            outcome = SearchOutcome("CAPPED", [], [], exc.name, None)

        if outcome.kind == "SOLVED":
            all_solutions = outcome.solutions
            contest_keys = outcome.contest_keys
            state = "SCORE"
            continue

        if outcome.kind == "INCONCLUSIVE":
            raise RuntimeError(
                f"Planet Finder {mode}: bounded search inconclusive; "
                f"no valid {target_solutions}-contestant contest was established"
            )
        if outcome.kind not in ("CAPPED", "EXHAUSTED") or not outcome.blocker:
            raise RuntimeError(
                f"Planet Finder {mode}: invalid search outcome kind={outcome.kind} blocker={outcome.blocker}"
            )

        all_solutions = outcome.solutions
        contest_keys = outcome.contest_keys
        promote_body = outcome.blocker
        search_history.append({"kind": outcome.kind, "blocker": promote_body, "order": order_names})
        diagnostic_print(
            f"Planet Finder {mode}: SEARCH OUTCOME {outcome.kind} "
            f"body={promote_body} contestants={len(all_solutions)}/{target_solutions}", flush=True,
        )
        state = "PROMOTE"

'''
s = s[:start] + new + s[end:]
p.write_text(s)

print("Canonical candidate lattice patch applied.")
