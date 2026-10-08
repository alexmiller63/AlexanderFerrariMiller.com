#!/usr/bin/env python3
"""Stable GitHub Actions launcher for the Planet Finder generator."""
from __future__ import annotations
from collections import deque
from datetime import date
import os
import re
import subprocess
import sys
import threading
import time

TRACE_LINES = 400


class Progress:
    """Track explicit publication events and the latest solver diagnostics."""

    def __init__(self, total_charts: int):
        self.started = time.monotonic()
        self.total_charts = total_charts
        self.completed = 0
        self.week = "pending"
        self.mode = "calculating"
        self.nodes = {}
        self.lock = threading.Lock()

    def observe(self, line: str) -> None:
        with self.lock:
            if line.startswith("PLANET_FINDER_PROGRESS "):
                fields = dict(re.findall(r"(\w+)=([^\s]+)", line))
                self.week = fields["iso"]
                self.mode = fields["mode"]
                if fields["event"] == "start":
                    self.nodes = {}
                elif fields["event"] == "complete":
                    self.completed += 1
                return
            match = re.match(r"Planet Finder (?:FinderMode\.)?([123]|greek|latin|mixed):", line, re.IGNORECASE)
            if match:
                # Counts belong to the current notation; never carry them into
                # the next mode. These are latest reported counts, not totals.
                notation = match[1].lower()
                if notation != self.mode:
                    self.mode = notation
                    self.nodes = {}
                for key, value in re.findall(r"(?<![\w-])(ordinary-dfs-nodes|nodes)=([\d,]+)", line):
                    category = "ordinary" if key == "ordinary-dfs-nodes" else "solver"
                    self.nodes[category] = value.replace(",", "")

    def report(self, status: str = "running") -> None:
        with self.lock:
            counts = ",".join(f"{key}:{value}" for key, value in sorted(self.nodes.items())) or "not-yet-reported"
            print(
                f"PLANET FINDER PROGRESS status={status} week={self.week} "
                f"notation={self.mode} elapsed={time.monotonic() - self.started:.0f}s "
                f"charts={self.completed}/{self.total_charts} latest-reported-nodes={counts}",
                flush=True,
            )


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def positive_int(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    try:
        number = int(value)
    except ValueError:
        raise SystemExit(f"{name} must be an integer") from None
    if number <= 0:
        raise SystemExit(f"{name} must be positive")
    return str(number)


def nonnegative_int(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    try:
        number = int(value)
    except ValueError:
        raise SystemExit(f"{name} must be an integer") from None
    if number < 0:
        raise SystemExit(f"{name} must be zero or greater")
    return str(number)


def iso_week_date(year_name: str, week_name: str) -> date:
    year = int(required(year_name))
    week = int(required(week_name))
    try:
        return date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise SystemExit(f"Invalid ISO week: {year}-W{week:02d}: {exc}") from None


def run_with_failure_trace(command: list[str], env: dict[str, str], total_charts: int = 0, heartbeat_seconds: float = 60) -> None:
    """Keep a bounded child-process trace and emit it only when the child fails."""
    trace = deque(maxlen=TRACE_LINES)
    progress = Progress(total_charts)
    stopped = threading.Event()
    env = dict(env, PYTHONUNBUFFERED="1")
    process = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    def heartbeat():
        while not stopped.wait(heartbeat_seconds):
            progress.report()

    reporter = threading.Thread(target=heartbeat, daemon=True)
    progress.report()
    reporter.start()
    try:
        for line in process.stdout:
            clean = line.rstrip("\n")
            trace.append(clean)
            progress.observe(clean)
            print(clean, flush=True)
        returncode = process.wait()
    finally:
        stopped.set()
        reporter.join()
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
            process.wait()
    progress.report("complete" if returncode == 0 else "failed")
    if returncode == 0:
        return

    print(f"PLANET FINDER FAILURE TRACE (last {len(trace)} lines)", flush=True)
    for line in trace:
        print(line, flush=True)
    raise SystemExit(returncode)


def main() -> None:
    start = iso_week_date("PLANET_FINDER_START_YEAR", "PLANET_FINDER_START_WEEK")
    end = iso_week_date("PLANET_FINDER_END_YEAR", "PLANET_FINDER_END_WEEK")
    if end < start:
        raise SystemExit("End ISO week must not precede start ISO week")
    env = os.environ.copy()
    env["PLANET_FINDER_CANDIDATES"] = positive_int("PLANET_FINDER_CANDIDATES", "5")
    env["PLANET_FINDER_MAX_NODE_CANDIDATES"] = positive_int("PLANET_FINDER_MAX_NODE_CANDIDATES", "200")
    env["PLANET_FINDER_MAX_SECONDS"] = positive_int("PLANET_FINDER_MAX_SECONDS", "360")
    env["PLANET_FINDER_DIAGNOSTIC_LEVEL"] = nonnegative_int("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")

    run_with_failure_trace(
        [sys.executable, "tools/populate_ephemeris_planet_finder_by_date.py",
         start.isoformat(), end.isoformat()],
        env,
        total_charts=((end - start).days // 7 + 1) * 3,
    )


if __name__ == "__main__":
    main()
