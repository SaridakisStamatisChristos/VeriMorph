import json
from dataclasses import FrozenInstanceError, replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from verimorph.budget import ExecutionBudget
from verimorph.kernel import Kernel
from verimorph.language import Node, canonical_source, parse, walk
from verimorph.mutation import RNG, Proposal, generate
from verimorph.oracle import Case, Oracle
from verimorph.provenance import Ledger
from verimorph.runtime import VM
from verimorph.verifier import Policy, verify

SOURCE = "FUNC fitness() { RETURN 100; } FUNC main() { RETURN 5; }"


def behavior(snapshot):
    return VM(snapshot.program, ExecutionBudget()).run()


@pytest.mark.parametrize(
    "proposal",
    [
        Proposal(1, "literal", "fitness/0/0", 100, 101),
        Proposal(1, "literal", "verifier/0", 1, 2),
        Proposal(1, "literal", "oracle/0", 1, 2),
        Proposal(1, "literal", "policy/0", 1, 2),
        Proposal(1, "literal", "main/0/0", 999, 6),
        Proposal(1, "literal", "main/0/0", 5, "RETURN ("),
        Proposal(1, "literal", "main/0/0", 5, True),
        Proposal(1, "arithmetic", "main/0/0", 5, "+"),
        Proposal(1, "literal", "main/0/0", 5, 1000001),
        Proposal(1, "literal", "main/0/0", 5, 4),
        Proposal(1, "literal", "main/0/0", 5, 5),
    ],
)
def test_rejected_mutation_preserves_state_and_behavior(proposal):
    k = Kernel(SOURCE)
    parent = k.committed
    expected = behavior(parent)
    assert not k.attempt(proposal)
    assert k.committed is parent
    assert behavior(k.committed) == expected
    k.finish()
    event = [
        json.loads(line)["payload"]
        for line in k.ledger.lines
        if json.loads(line)["payload"]["kind"] == "mutation"
    ][0]
    assert event["decision"] == "reject" and event["resulting"] == parent.snapshot_id


def test_successful_commit_lineage_and_snapshot_immutability():
    k = Kernel(SOURCE)
    parent = k.committed
    assert k.attempt(Proposal(1, "literal", "main/0/0", 5, 6))
    assert k.committed.parent_id == parent.snapshot_id
    assert k.committed.content_hash != parent.content_hash
    assert parent.source == canonical_source(parse(SOURCE))
    assert behavior(parent).returned == 5
    assert behavior(k.committed).returned == 6
    verify(k.committed.program, Policy())
    with pytest.raises(FrozenInstanceError):
        parent.source = "corrupt"
    k.finish()


def test_negative_numeric_mutation_roundtrip():
    k = Kernel("FUNC main() { RETURN 0; }", oracle=Oracle((Case(target=-5),)))
    assert k.attempt(Proposal(1, "literal", "main/0/0", 0, -1))
    assert behavior(k.committed).returned == -1


def test_historical_objective_tampering_regression():
    k = Kernel(SOURCE, oracle=Oracle((Case(target=12),)))
    identity = k._oracle.identity
    assert not k.attempt(Proposal(1, "literal", "fitness/0/0", 100, 101))
    assert k._oracle.identity == identity
    # Even when fitness is explicitly allowed as ordinary code, external scoring stays unchanged.
    permissive = Kernel(SOURCE, policy=Policy(mutable_functions=("main", "fitness")))
    assert not permissive.attempt(Proposal(1, "literal", "fitness/0/0", 100, 101))
    assert behavior(permissive.committed).returned == 5
    with pytest.raises(FrozenInstanceError):
        k._oracle.version = "tampered"


def test_candidate_locals_and_output_do_not_leak():
    source = "FUNC main() { x = 5; PRINT x; RETURN x; }"
    k = Kernel(source, oracle=Oracle((Case(target=12, expected_output=(5,)),)))
    parent = k.committed
    assert not k.attempt(Proposal(1, "literal", "main/0/0", 5, 6))
    assert behavior(k.committed).output == (5,)
    assert k.committed is parent


def test_invariant_rejection_precedes_improved_fitness():
    k = Kernel("FUNC main() { RETURN 5; }", oracle=Oracle((Case(target=12),), maximum=5))
    assert not k.attempt(Proposal(1, "literal", "main/0/0", 5, 6))
    event = json.loads(k.ledger.lines[-1])["payload"]
    assert event["stage"] == "invariant"


@given(st.integers(-1000, 1000))
def test_generated_atomic_failure(value):
    k = Kernel(f"FUNC main() {{ RETURN {value}; }}")
    parent = k.committed
    assert not k.attempt(Proposal(1, "literal", "main/0/0", value, "malformed"))
    assert k.committed == parent and behavior(parent) == behavior(k.committed)


@given(st.integers(0, 2**64 - 1))
def test_mutation_never_changes_immutable_nodes(seed):
    program = parse(SOURCE)
    p = generate(program, Policy(), RNG(seed), 1)
    child = p.apply(program, Policy())
    before = dict(walk(program))
    after = dict(walk(child))
    assert {path: n for path, n in before.items() if path.startswith("fitness/")} == {
        path: n for path, n in after.items() if path.startswith("fitness/")
    }
    assert parse(canonical_source(child)) == child


def test_io_failure_is_atomic(monkeypatch):
    ledger = Ledger()
    k = Kernel(SOURCE, ledger=ledger)
    k._start("manual")
    k._ensure_baseline()
    parent = k.committed

    def fail(payload):
        raise OSError("injected disk failure")

    monkeypatch.setattr(ledger, "append", fail)
    with pytest.raises(OSError):
        k.attempt(Proposal(1, "literal", "main/0/0", 5, 6))
    assert k.committed is parent


def test_malformed_ast_cannot_commit(monkeypatch):
    k = Kernel(SOURCE)
    original = Proposal.apply

    def malformed(self, program, policy):
        proper = original(self, program, policy)
        f = proper.functions[1]
        return replace(
            proper,
            functions=(
                proper.functions[0],
                replace(
                    f,
                    body=(
                        Node(
                            "return",
                            "",
                            (Node("binary", "**", (Node("number", 1), Node("number", 2))),),
                        ),
                    ),
                ),
            ),
        )

    monkeypatch.setattr(Proposal, "apply", malformed)
    parent = k.committed
    assert not k.attempt(Proposal(1, "literal", "main/0/0", 5, 6))
    assert k.committed is parent


def test_operator_mutations():
    k = Kernel("FUNC main() { RETURN 6 - 2; }")
    assert k.attempt(Proposal(1, "arithmetic", "main/0/0", "-", "*"))
    assert behavior(k.committed).returned == 12
    k = Kernel("FUNC main() { RETURN 5 < 2; }", oracle=Oracle((Case(target=1),)))
    assert k.attempt(Proposal(1, "comparison", "main/0/0", "<", ">"))
