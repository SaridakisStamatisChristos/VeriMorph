import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from verimorph.budget import ExecutionBudget, Limits
from verimorph.errors import BudgetExceeded, VeriMorphError
from verimorph.kernel import Kernel
from verimorph.language import parse
from verimorph.mutation import Proposal
from verimorph.oracle import Oracle
from verimorph.provenance import Ledger, decode
from verimorph.runtime import VM
from verimorph.verifier import Policy


def test_parser_surrogates_fail_explicitly():
    with pytest.raises(VeriMorphError, match="Unicode"):
        parse("\ud800")


def test_disposable_vm_cannot_reuse_output_or_state():
    vm = VM(parse("FUNC main() { PRINT 1; RETURN 1; }"), ExecutionBudget())
    assert vm.run().output == (1,)
    with pytest.raises(VeriMorphError, match="once"):
        vm.run()


def test_host_stack_escape_fails_closed():
    # Deep expression around each recursive call stresses host stack before VM call limit.
    expression = "main()"
    for _ in range(20):
        expression = "1 + (" + expression + ")"
    k = Kernel(f"FUNC main() {{ RETURN {expression}; }}")
    parent = k.committed
    k.search(1)
    assert k.committed is parent
    assert json.loads(k.ledger.lines[-1])["payload"]["status"] == "exhausted"
    with pytest.raises(BudgetExceeded):
        k.budget.check()


def test_journal_failure_poisoning_prevents_later_commit(tmp_path, monkeypatch):
    path = tmp_path / "run.jsonl"
    ledger = Ledger(path)
    k = Kernel("FUNC main() { RETURN 5; }", ledger=ledger)
    k._start("manual")
    k._ensure_baseline()
    parent = k.committed

    def fail(fd):
        raise OSError("fsync failed")

    monkeypatch.setattr("verimorph.provenance.os.fsync", fail)
    with pytest.raises(OSError):
        k.attempt(Proposal(1, "literal", "main/0/0", 5, 6))
    assert k.committed is parent
    with pytest.raises(VeriMorphError, match="closed"):
        k.attempt(Proposal(2, "literal", "main/0/0", 5, 6))
    with pytest.raises(VeriMorphError):
        decode(path.read_text())


def test_header_and_end_reservations_bound_audit_volume():
    k = Kernel("FUNC main() { RETURN 5; }", limits=Limits(audit_events=8))
    k.search(1000)
    assert len(k.ledger.lines) <= k.budget.limits.audit_events
    assert json.loads(k.ledger.lines[-1])["payload"]["status"] == "exhausted"


@given(st.text(max_size=300))
@settings(max_examples=200)
def test_ledger_decoder_fuzz(text):
    with pytest.raises(VeriMorphError):
        decode(text)


@pytest.mark.parametrize(
    "source",
    [
        "FUNC main() { RETURN open(1); }",
        "FUNC main() { RETURN socket(1); }",
        "FUNC main() { RETURN eval(1); }",
        "FUNC main() { RETURN exec(1); }",
        "FUNC main() { SEND_SOURCE 1; RETURN 0; }",
        "FUNC main() { MODIFY_LINE 1 2; RETURN 0; }",
        "FUNC main() { RETURN oracle.version; }",
    ],
)
def test_no_host_or_legacy_capabilities(source):
    with pytest.raises(VeriMorphError):
        Kernel(source)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Policy(mutable_functions=()),
        lambda: Policy(operators=("unknown",)),
        lambda: Policy(literal_min=4, literal_max=3),
        lambda: Policy(allow_evolve=1),
        lambda: Oracle(cases=()),
        lambda: Oracle(minimum=5, maximum=4),
    ],
)
def test_policy_oracle_config_fail_closed(factory):
    with pytest.raises(VeriMorphError):
        factory()


def test_no_optimizer_or_untrusted_python_evaluation():
    root = Path(__file__).parents[1] / "src/verimorph"
    import ast

    for file in root.glob("*.py"):
        tree = ast.parse(file.read_text())
        assert not any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in ("eval", "exec", "compile")
            for n in ast.walk(tree)
        )


def test_semantically_same_source_same_history():
    a = Kernel("FUNC main() { RETURN 5; }")
    b = Kernel("# comment\nFUNC main( )\n {\nRETURN 5 ;\n}\n")
    a.search(10)
    b.search(10)
    assert a.ledger.lines == b.ledger.lines


def test_host_recursion_error_becomes_sticky_budget_failure(monkeypatch):
    vm = VM(parse("FUNC main() { RETURN 1; }"), ExecutionBudget())

    def overflow(name, args):
        raise RecursionError("host limit")

    monkeypatch.setattr(vm, "call", overflow)
    with pytest.raises(BudgetExceeded, match="host_stack"):
        vm.run()
    with pytest.raises(BudgetExceeded, match="host_stack"):
        vm.budget.check()
