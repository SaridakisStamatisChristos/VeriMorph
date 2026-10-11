"""Reexecute evidence with current versioned semantics; compare every semantic event."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .budget import Limits
from .errors import VeriMorphError
from .kernel import Kernel
from .mutation import Proposal
from .oracle import Case, Oracle
from .provenance import decode, load
from .verifier import VERIFIER_VERSION, Policy


def configuration(header: dict[str, Any]) -> tuple[Policy, Oracle, Limits]:
    try:
        p = dict(header["policy"])
        p["mutable_functions"] = tuple(p["mutable_functions"])
        p["operators"] = tuple(p["operators"])
        o = dict(header["oracle"])
        o["cases"] = tuple(
            Case(
                tuple(c["args"]),
                c["target"],
                None if c["expected_output"] is None else tuple(c["expected_output"]),
            )
            for c in o["cases"]
        )
        return Policy(**p), Oracle(**o), Limits(**header["limits"])
    except (KeyError, TypeError, ValueError) as e:
        raise VeriMorphError("replay", "invalid configuration") from e


def replay(path: Path, expected_anchor: str | None = None) -> Kernel:
    events = load(path, expected_anchor)
    header = events[0]["payload"]
    if header.get("format") != "verimorph-ledger-1" or header.get("verifier") != VERIFIER_VERSION:
        raise VeriMorphError("replay", "unsupported evidence version")
    policy, oracle, limits = configuration(header)
    kernel = Kernel(header["source"], policy, oracle, limits, header["seed"])
    if kernel.committed.snapshot_id != header.get("initial"):
        raise VeriMorphError("replay", "initial snapshot mismatch")
    mode = header.get("mode")
    try:
        if mode == "search":
            kernel.search(header["config"]["iterations"])
        elif mode == "run":
            kernel.execute(tuple(header["config"]["args"]))
        elif mode == "manual":
            for event in events[1:-1]:
                payload = event["payload"]
                if payload.get("kind") == "mutation":
                    kernel.attempt(Proposal(**payload["proposal"]))
            kernel.finish()
        else:
            raise VeriMorphError("replay", "unsupported operation")
    except VeriMorphError:
        kernel.finish()
    actual = decode("".join(kernel.ledger.lines))
    if actual != events:
        raise VeriMorphError("replay", "semantic evidence mismatch")
    return kernel
