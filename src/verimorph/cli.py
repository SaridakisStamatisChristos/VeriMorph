"""Local, bounded CLI with JSON diagnostics and explicit failure exit codes."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from .budget import Limits
from .errors import VeriMorphError
from .kernel import Kernel
from .language import MAX_SOURCE, canonical_source, parse, walk
from .oracle import Case, Oracle
from .provenance import Ledger, load
from .replay import configuration, replay
from .snapshots import Snapshot, canonical, digest
from .verifier import Policy, verify


def read_source(path: Path) -> str:
    with path.open("rb") as stream:
        data = stream.read(MAX_SOURCE + 1)
    if len(data) > MAX_SOURCE:
        raise VeriMorphError("lex", "source too large")
    return data.decode("utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="verimorph",
        description="Bounded transactional self-modification; no OS sandbox or formal-proof claim.",
    )
    sub = p.add_subparsers(dest="command", required=True)
    for command in ("check", "run", "evolve", "inspect"):
        cmd = sub.add_parser(command)
        cmd.add_argument("program", type=Path)
        cmd.add_argument(
            "--config",
            type=Path,
            help="external JSON with policy/oracle/limits; never program text",
        )
        if command in ("run", "evolve"):
            cmd.add_argument("--seed", type=int, default=42)
            cmd.add_argument("--steps", type=int)
            cmd.add_argument(
                "--ledger", type=Path, help="new JSONL file; existing paths are never overwritten"
            )
        if command == "run":
            cmd.add_argument("--arg", type=int, action="append", default=[])
        if command == "evolve":
            cmd.add_argument("--iterations", type=int, default=32)
            cmd.add_argument("--target", type=int, help="single no-argument return-value objective")
            cmd.add_argument(
                "--output", type=Path, help="new committed-source file; exclusive create"
            )
    for command in ("replay", "history"):
        cmd = sub.add_parser(command)
        cmd.add_argument("ledger", type=Path)
        cmd.add_argument("--anchor", help="expected trusted final ledger hash")
    diff = sub.add_parser("diff")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    ledger: Ledger | None = None
    try:
        if args.command == "replay":
            k = replay(args.ledger, args.anchor)
            print(
                canonical(
                    {
                        "replay": "verified",
                        "final": k.committed.snapshot_id,
                        "anchor": k.ledger.anchor,
                    }
                )
            )
            return 0
        if args.command == "history":
            for event in load(args.ledger, args.anchor):
                print(canonical(event))
            return 0
        if args.command == "diff":
            print(
                "".join(
                    difflib.unified_diff(
                        canonical_source(parse(read_source(args.before))).splitlines(True),
                        canonical_source(parse(read_source(args.after))).splitlines(True),
                        fromfile=str(args.before),
                        tofile=str(args.after),
                    )
                ),
                end="",
            )
            return 0
        policy, oracle, limits = Policy(), Oracle(), Limits()
        if args.config is not None:
            if args.config.stat().st_size > 65536:
                raise VeriMorphError("config", "configuration too large")
            config: dict[str, Any] = json.loads(args.config.read_text())
            policy, oracle, limits = configuration(config)
        source = read_source(args.program)
        program = parse(source)
        verify(program, policy)
        if args.command in ("check", "inspect"):
            snap = Snapshot.create(program, digest(policy.data()), oracle.identity)
            payload: dict[str, Any] = {
                "valid": True,
                "snapshot": snap.snapshot_id,
                "content_hash": snap.content_hash,
            }
            if args.command == "inspect":
                payload.update(
                    source=snap.source,
                    nodes=[
                        {"id": path, "kind": node.kind, "value": node.value}
                        for path, node in walk(program)
                    ],
                )
            print(canonical(payload))
            return 0
        if args.steps is not None:
            limits = replace(limits, steps=args.steps)
        if args.command == "evolve" and args.target is not None:
            oracle = Oracle((Case(target=args.target),))
        ledger = Ledger(args.ledger)
        k = Kernel(source, policy, oracle, limits, args.seed, ledger)
        if args.command == "run":
            result = k.execute(tuple(args.arg))
            print(canonical(asdict(result)))
        else:
            k.search(args.iterations)
            if args.output is not None:
                with args.output.open("x", encoding="utf-8") as stream:
                    stream.write(k.committed.source)
            end = json.loads(k.ledger.lines[-1])["payload"]
            print(canonical({**end, "anchor": k.ledger.anchor}))
            return 0 if end["status"] == "complete" else 2
        return 0
    except (VeriMorphError, OSError, ValueError, TypeError, RecursionError) as e:
        print(canonical({"error": str(e)}), file=sys.stderr)
        return 2
    finally:
        if ledger is not None:
            ledger.close()


if __name__ == "__main__":
    raise SystemExit(main())
