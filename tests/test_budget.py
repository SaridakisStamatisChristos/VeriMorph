import json
from dataclasses import FrozenInstanceError, replace

import pytest

from verimorph.budget import ExecutionBudget, Limits
from verimorph.errors import BudgetExceeded, VeriMorphError
from verimorph.kernel import Kernel
from verimorph.mutation import Proposal
from verimorph.verifier import Policy


def test_root_budget_shared_and_sticky():
    root = ExecutionBudget(Limits(steps=3))
    root.charge("steps")
    with root.evaluation():
        root.charge("steps", 2)
        with pytest.raises(BudgetExceeded):
            with root.evaluation():
                root.charge("steps")
    assert root.usage()["steps"] == 3
    with pytest.raises(BudgetExceeded):
        root.charge("steps", 0)
    with pytest.raises(FrozenInstanceError):
        root.limits.steps = 100000
    usage = root.usage()
    usage["steps"] = 0
    assert root.usage()["steps"] == 3


@pytest.mark.parametrize(
    "source, limits, dimension",
    [
        ("FUNC main() { WHILE 1 {} RETURN 5; }", Limits(steps=50), "steps"),
        ("FUNC main() { RETURN main(); }", Limits(call_depth=5), "call_depth"),
        (
            "FUNC main() { WHILE 1 { PRINT 999; } RETURN 5; }",
            Limits(output_bytes=10),
            "output_bytes",
        ),
        ("FUNC main() { EVOLVE 1; RETURN 5; }", Limits(evaluation_depth=3), "evaluation_depth"),
    ],
)
def test_global_exhaustion(source, limits, dimension):
    k = Kernel(source, limits=limits, policy=Policy(allow_evolve=True))
    parent = k.committed
    k.search(2)
    assert k.committed is parent
    end = json.loads(k.ledger.lines[-1])["payload"]
    assert end["status"] == "exhausted"
    with pytest.raises(BudgetExceeded, match=dimension):
        k.budget.check()


def test_recursive_evolve_never_receives_fresh_account():
    k = Kernel(
        "FUNC main() { EVOLVE 1; RETURN 5; }",
        policy=Policy(allow_evolve=True),
        limits=Limits(evaluation_depth=3),
    )
    parent = k.committed
    k.search(1)
    assert k.committed is parent
    assert k.budget.usage()["evaluations"] == 4
    assert k.budget.usage()["mutations"] == 3
    events = [json.loads(line)["payload"] for line in k.ledger.lines]
    assert len([x for x in events if x["kind"] == "nested"]) == 3
    assert any(x.get("stage") == "budget" for x in events)


@pytest.mark.parametrize(
    "dimension",
    ["mutations", "compilations", "evaluations", "ast_nodes", "source_bytes", "audit_events"],
)
def test_resource_dimensions_fail_closed(dimension):
    base = Limits()
    limits = replace(
        base,
        **{
            dimension: 2
            if dimension not in ("source_bytes", "ast_nodes", "audit_events")
            else {"source_bytes": 60, "ast_nodes": 5, "audit_events": 6}[dimension]
        },
    )
    k = Kernel("FUNC main() { RETURN 5; }", limits=limits)
    k.search(30)
    assert k.budget.usage()[dimension] <= getattr(limits, dimension)
    end = json.loads(k.ledger.lines[-1])["payload"]
    assert end["status"] == "exhausted"
    verify_source = k.committed.source
    assert "FUNC main" in verify_source


def test_no_commit_after_budget_failure():
    k = Kernel("FUNC main() { RETURN 5; }", limits=Limits(steps=6))
    parent = k.committed
    assert k.attempt(Proposal(1, "literal", "main/0/0", 5, 6))
    best = k.committed
    assert not k.attempt(Proposal(2, "literal", "main/0/0", 6, 7))
    assert k.committed is best and best is not parent
    with pytest.raises(BudgetExceeded):
        k.attempt(Proposal(3, "literal", "main/0/0", 6, 8))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"steps": 0},
        {"steps": True},
        {"wall_ms": -1},
        {"call_depth": 100},
        {"evaluation_depth": 100},
    ],
)
def test_invalid_limit_config(kwargs):
    with pytest.raises(VeriMorphError):
        Limits(**kwargs)


def test_deadline_is_cooperative_and_fails_closed(monkeypatch):
    root = ExecutionBudget()
    monkeypatch.setattr("verimorph.budget.time.monotonic", lambda: root._deadline + 1)
    with pytest.raises(BudgetExceeded, match="wall_ms"):
        root.check()
