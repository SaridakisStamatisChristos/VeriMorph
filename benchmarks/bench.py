"""Checked workloads; no external baseline or superiority claim. Run from repo root."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

from verimorph.budget import ExecutionBudget
from verimorph.kernel import Kernel
from verimorph.language import parse
from verimorph.oracle import Oracle
from verimorph.provenance import Ledger
from verimorph.replay import replay
from verimorph.runtime import VM
from verimorph.snapshots import Snapshot, digest
from verimorph.verifier import Policy, verify

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--inner", type=int, default=20)
    args = parser.parse_args()
    if args.repetitions < 3 or args.inner < 1:
        parser.error("at least 3 repetitions, 1 inner operation")
    source = (ROOT / "benchmarks/workload.vm").read_text()
    program = parse(source)
    policy = Policy()
    oracle = Oracle()
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "replay.jsonl"
        seed = Kernel("FUNC main() { RETURN 5; }", ledger=Ledger(path))
        seed.search(32)
        cases = {
            "parse": lambda: parse(source),
            "execute_100_loop_iterations": lambda: VM(program, ExecutionBudget()).run(),
            "snapshot": lambda: Snapshot.create(program, digest(policy.data()), oracle.identity),
            "static_verify": lambda: verify(program, policy),
            "evaluate_32_candidates_memory_ledger": lambda: Kernel(
                "FUNC main() { RETURN 5; }"
            ).search(32),
            "replay_32_candidates": lambda: replay(path),
        }
        measurements = {}
        for name, operation in cases.items():
            for _ in range(2):
                operation()
            times = []
            for _ in range(args.repetitions):
                start = time.perf_counter_ns()
                for _ in range(args.inner):
                    operation()
                times.append((time.perf_counter_ns() - start) / args.inner / 1000)
            measurements[name] = {
                "unit": "microseconds/operation",
                "samples": times,
                "median": statistics.median(times),
                "min": min(times),
                "max": max(times),
                "stdev": statistics.stdev(times),
            }
        fsync = []
        for i in range(args.repetitions):
            start = time.perf_counter_ns()
            k = Kernel("FUNC main() { RETURN 5; }", ledger=Ledger(Path(temp) / f"fsync-{i}.jsonl"))
            k.search(32)
            fsync.append((time.perf_counter_ns() - start) / 1000)
        measurements["evaluate_32_candidates_fsync_ledger"] = {
            "unit": "microseconds/operation",
            "samples": fsync,
            "median": statistics.median(fsync),
            "min": min(fsync),
            "max": max(fsync),
            "stdev": statistics.stdev(fsync),
        }
    cpu = platform.processor()
    if Path("/proc/cpuinfo").exists():
        cpu = next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            cpu,
        )
    print(
        json.dumps(
            {
                "environment": {
                    "platform": platform.platform(),
                    "machine": platform.machine(),
                    "cpu": cpu,
                    "python": sys.version,
                    "logical_cpus": __import__("os").cpu_count(),
                },
                "command": f"python benchmarks/bench.py --repetitions {args.repetitions} --inner {args.inner}",
                "repetitions": args.repetitions,
                "inner": args.inner,
                "warmup": 2,
                "workload_sha256": __import__("hashlib").sha256(source.encode()).hexdigest(),
                "results": measurements,
                "limitations": "Shared container; timings are noisy and are not comparative evidence. Fsync path is temporary local filesystem.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
