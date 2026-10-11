"""PREPARE -> VERIFY -> EVALUATE -> DECIDE -> journal -> atomic reference swap."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .budget import ExecutionBudget, Limits
from .errors import BudgetExceeded, VeriMorphError
from .language import MAX_SOURCE, Program, canonical_source, parse, walk
from .mutation import RNG, Proposal, generate
from .oracle import Oracle
from .provenance import Ledger
from .runtime import VM, Result
from .snapshots import Snapshot, digest
from .verifier import VERIFIER_VERSION, Policy, verify


class Kernel:
    """Single owner/thread; embedding Python is trusted. No durable service state."""

    def __init__(
        self,
        source: str,
        policy: Policy | None = None,
        oracle: Oracle | None = None,
        limits: Limits | None = None,
        seed: int = 42,
        ledger: Ledger | None = None,
    ):
        policy = Policy() if policy is None else policy
        oracle = Oracle() if oracle is None else oracle
        limits = Limits() if limits is None else limits
        self._policy = policy
        self._oracle = oracle
        self._budget = ExecutionBudget(limits)
        self._rng = RNG(seed)
        self._seed = seed
        self._ledger = Ledger() if ledger is None else ledger
        program = self._prepare(source)
        verify(program, policy)
        self._committed = Snapshot.create(program, digest(policy.data()), oracle.identity)
        self._initial = self._committed
        self._baseline: int | None = None
        self._started = False
        self._finished = False
        self._index = 0
        self._nested_index = 0
        self._terminal = "complete"

    @property
    def committed(self) -> Snapshot:
        return self._committed

    @property
    def budget(self) -> ExecutionBudget:
        return self._budget

    @property
    def ledger(self) -> Ledger:
        return self._ledger

    def _prepare(self, source: str) -> Program:
        if len(source) > MAX_SOURCE:
            raise VeriMorphError("lex", "source too large")
        self._budget.charge("compilations")
        program = parse(source)
        self._budget.charge("source_bytes", len(canonical_source(program).encode()))
        self._budget.charge("ast_nodes", len(walk(program)))
        return program

    def _start(self, mode: str, **config: Any) -> None:
        if self._started or self._finished:
            raise VeriMorphError("session", "session already started or closed")
        self._budget.charge("audit_events", 4)
        self._ledger.append(
            {
                "kind": "header",
                "format": "verimorph-ledger-1",
                "run_id": digest(
                    {
                        "snapshot": self._initial.snapshot_id,
                        "seed": self._seed,
                        "mode": mode,
                        "config": config,
                        "limits": asdict(self._budget.limits),
                    }
                ),
                "source": self._initial.source,
                "initial": self._initial.snapshot_id,
                "policy": self._policy.data(),
                "oracle": self._oracle.data(),
                "limits": asdict(self._budget.limits),
                "seed": self._seed,
                "verifier": VERIFIER_VERSION,
                "mode": mode,
                "config": config,
            }
        )
        self._started = True

    def _evaluate(self, snapshot: Snapshot) -> tuple[tuple[Result, ...], int]:
        results = tuple(
            VM(snapshot.program, self._budget, lambda count: self._preview(snapshot, count)).run(
                case.args
            )
            for case in self._oracle.cases
        )
        return results, self._oracle.score(results)

    def _preview(self, parent: Snapshot, count: int) -> None:
        # Descendant work is speculative: no write to the global committed reference.
        best = parent
        for _ in range(count):
            self._budget.charge("audit_events")  # reserve evidence before doing work
            self._nested_index += 1
            event: dict[str, Any] = {
                "kind": "nested",
                "index": self._nested_index,
                "parent": best.snapshot_id,
                "decision": "reject",
            }
            try:
                self._budget.charge("mutations")
                p = generate(best.program, self._policy, self._rng, self._nested_index)
                event["proposal"] = asdict(p)
                candidate = self._candidate(best, p)
                event["candidate"] = candidate.snapshot_id
                results, score = self._evaluate(candidate)
                event.update(
                    score=score, results=[asdict(r) for r in results], decision="verified-preview"
                )
                best = candidate
            except VeriMorphError as e:
                event.update(stage=e.stage, reason=e.reason)
                raise
            finally:
                event["resources"] = self._budget.usage()
                self._ledger.append(event)

    def _candidate(
        self, parent: Snapshot, proposal: Proposal, stages: list[str] | None = None
    ) -> Snapshot:
        stages = [] if stages is None else stages
        program = proposal.apply(parent.program, self._policy)
        stages.append("mutation-policy")
        source = canonical_source(program)
        stages.append("structure")
        reparsed = self._prepare(source)
        stages.append("parse")
        if reparsed != program:
            raise VeriMorphError("structure", "candidate roundtrip mismatch")
        verify(reparsed, self._policy)
        stages.extend(["static", "capability"])
        candidate = Snapshot.create(reparsed, parent.policy_hash, parent.oracle_hash, parent)
        stages.append("snapshot")
        return candidate

    def _ensure_baseline(self) -> None:
        if self._baseline is not None:
            return
        self._budget.charge("audit_events")
        event: dict[str, Any] = {"kind": "baseline", "snapshot": self._committed.snapshot_id}
        try:
            results, score = self._evaluate(self._committed)
            event.update(score=score, results=[asdict(r) for r in results])
            self._baseline = score
        except VeriMorphError as e:
            self._terminal = "failed"
            event.update(stage=e.stage, reason=e.reason)
            raise
        finally:
            event["resources"] = self._budget.usage()
            self._ledger.append(event)

    def attempt(
        self, proposal: Proposal, *, generated: bool = False, rng_before: int | None = None
    ) -> bool:
        if not self._started:
            self._start("manual")
        if self._finished:
            raise VeriMorphError("session", "session closed")
        self._ensure_baseline()
        self._budget.charge("audit_events")
        parent = self._committed
        self._index += 1
        event: dict[str, Any] = {
            "kind": "mutation",
            "index": self._index,
            "parent": parent.snapshot_id,
            "proposal": asdict(proposal),
            "generated": generated,
            "rng_before": rng_before,
            "baseline_score": self._baseline,
            "decision": "reject",
            "stages": [],
        }
        candidate: Snapshot | None = None
        score: int | None = None
        accepted = False
        try:
            self._budget.charge("mutations")
            candidate = self._candidate(parent, proposal, event["stages"])
            event["candidate"] = candidate.snapshot_id
            event["candidate_content"] = candidate.content_hash
            results, score = self._evaluate(candidate)
            event.update(score=score, results=[asdict(r) for r in results], invariants="pass")
            event["stages"].extend(["execution", "invariants", "oracle"])
            self._budget.check()
            if parent is not self._committed:
                raise VeriMorphError("commit", "stale parent")
            if self._baseline is not None and score > self._baseline:
                accepted = True
                event.update(decision="commit", resulting=candidate.snapshot_id)
            else:
                event.update(stage="selection", reason="strict improvement required")
        except VeriMorphError as e:
            event.update(stage=e.stage, reason=e.reason)
            if isinstance(e, BudgetExceeded):
                self._terminal = "exhausted"
        event["resources"] = self._budget.usage()
        event.setdefault("resulting", parent.snapshot_id)
        # Exactly one global state swap, after all gates and journal durability.
        try:
            self._ledger.append(event)
        except (OSError, VeriMorphError):
            self._terminal = "failed"
            self._finished = True
            self._ledger.close()
            raise
        if accepted and candidate is not None and score is not None:
            self._committed = candidate
            self._baseline = score
        return accepted

    def search(self, iterations: int = 32) -> Snapshot:
        if type(iterations) is not int or not 0 <= iterations <= 1000:
            raise VeriMorphError("config", "iterations must be 0..1000")
        self._start("search", iterations=iterations)
        try:
            self._ensure_baseline()
            for _ in range(iterations):
                self._budget.check()
                before = self._rng.state
                proposal = generate(
                    self._committed.program, self._policy, self._rng, self._index + 1
                )
                self.attempt(proposal, generated=True, rng_before=before)
                if self._terminal != "complete":
                    break
        except VeriMorphError as e:
            self._terminal = "exhausted" if isinstance(e, BudgetExceeded) else "failed"
            self._ledger.append(
                {
                    "kind": "error",
                    "stage": e.stage,
                    "reason": e.reason,
                    "resources": self._budget.usage(),
                }
            )
        finally:
            self.finish()
        return self._committed

    def execute(self, args: tuple[int, ...] = ()) -> Result:
        self._start("run", args=args)
        pinned = self._committed

        def evolve(count: int) -> None:
            self._ensure_baseline()
            for _ in range(count):
                before = self._rng.state
                proposal = generate(
                    self._committed.program, self._policy, self._rng, self._index + 1
                )
                self.attempt(proposal, generated=True, rng_before=before)
                self._budget.check()

        try:
            result = VM(pinned.program, self._budget, evolve).run(args)
            self._ledger.append(
                {
                    "kind": "run-result",
                    "result": asdict(result),
                    "pinned": pinned.snapshot_id,
                    "resources": self._budget.usage(),
                }
            )
            return result
        except VeriMorphError as e:
            self._terminal = "exhausted" if isinstance(e, BudgetExceeded) else "failed"
            self._ledger.append(
                {
                    "kind": "error",
                    "stage": e.stage,
                    "reason": e.reason,
                    "resources": self._budget.usage(),
                }
            )
            raise
        finally:
            self.finish()

    def finish(self) -> None:
        if self._finished:
            return
        if not self._started:
            self._start("manual")
        # End seal is reserved outside attempt accounting and cannot permit another commit.
        self._ledger.append(
            {
                "kind": "end",
                "final": self._committed.snapshot_id,
                "source": self._committed.source,
                "score": self._baseline,
                "status": self._terminal,
                "resources": self._budget.usage(),
                "attempts": self._index,
            }
        )
        self._ledger.close()
        self._finished = True
