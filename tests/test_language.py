from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from verimorph.budget import ExecutionBudget
from verimorph.errors import VeriMorphError
from verimorph.language import (
    MAX_INT,
    MIN_INT,
    Node,
    Program,
    canonical_source,
    parse,
    validate_structure,
)
from verimorph.runtime import VM
from verimorph.verifier import Policy, verify


def run(source, args=()):
    program = parse(source)
    verify(program, Policy())
    return VM(program, ExecutionBudget()).run(args)


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("2 + 3 * 4", 14),
        ("(2 + 3) * 4", 20),
        ("-7 / 3", -3),
        ("7 / -3", -3),
        ("-7 / -3", 2),
        ("3 < 4", 1),
        ("4 <= 4", 1),
        ("5 > 4", 1),
        ("5 >= 6", 0),
        ("5 == 5", 1),
        ("5 != 5", 0),
        ("10 - 3 - 2", 5),
        ("20 / 2 / 2", 5),
        (str(MAX_INT), MAX_INT),
        (str(MIN_INT), MIN_INT),
        ("-(5)", -5),
        ("+(3)", 3),
    ],
)
def test_semantics(expression, expected):
    assert run(f"FUNC main() {{ RETURN {expression}; }}").returned == expected


def test_functions_scope_loop_and_zero_return():
    source = """FUNC helper(x) { x = x + 1; RETURN x; }
    FUNC main() { x = 0; WHILE x < 5 { x = helper(x); } PRINT x; IF x == 5 { RETURN 0; } RETURN 9; }"""
    assert run(source).returned == 0
    assert run(source).output == (5,)


def test_locals_do_not_leak_across_calls():
    source = "FUNC f(x) { x = 100; RETURN x; } FUNC main() { x = 3; y = f(x); RETURN x; }"
    assert run(source).returned == 3


@pytest.mark.parametrize(
    "source",
    [
        "",
        "FUNC main() { RETURN unknown; }",
        "FUNC main() { IF 1 { x = 2; } RETURN x; }",
        "FUNC main() { WHILE 0 { x = 2; } RETURN x; }",
        "FUNC main() { RETURN absent(); }",
        "FUNC f(x) { RETURN x; } FUNC main() { RETURN f(); }",
        "FUNC main(x,x) { RETURN x; }",
        "FUNC main() { RETURN 1; } FUNC main() { RETURN 2; }",
        "FUNC other() { RETURN 1; }",
        "FUNC main() { RETURN (1; }",
        "FUNC main() { EVOLVE 0; }",
        "FUNC main() { RETURN 9223372036854775808; }",
        "FUNC main() { SEND_SOURCE 1; }",
        "FUNC main() { RETURN __import__(1); }",
    ],
)
def test_static_fail_closed(source):
    with pytest.raises(VeriMorphError):
        verify(parse(source), Policy())


@pytest.mark.parametrize(
    "expression",
    ["1 / 0", f"{MAX_INT} + 1", f"{MIN_INT} / -1", f"{MAX_INT} * {MAX_INT}", f"-({MIN_INT})"],
)
def test_runtime_numeric_fail_closed(expression):
    with pytest.raises(VeriMorphError):
        run(f"FUNC main() {{ RETURN {expression}; }}")


def test_if_definite_assignment_intersection():
    assert run("FUNC main() { IF 1 { x = 2; } ELSE { x = 3; } RETURN x; }").returned == 2


@given(
    st.integers(-100000, 100000),
    st.integers(-100000, 100000),
    st.sampled_from(["+", "-", "*", "/"]),
)
def test_arithmetic_against_independent_host_oracle(a, b, op):
    if op == "/" and b == 0:
        return
    reference = {"+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b, "/": lambda: a // b}[
        op
    ]()
    source = f"FUNC main() {{ RETURN {a} {op} {b}; }}"
    assert run(source).returned == reference
    program = parse(source)
    assert parse(canonical_source(program)) == program


@given(st.integers(-1000, 1000))
def test_metamorphic_identity(a):
    assert run(f"FUNC main() {{ RETURN ({a} + 0) * 1; }}").returned == a


@given(st.text(max_size=500))
@settings(max_examples=300)
def test_parser_fuzz_fails_explicitly(text):
    try:
        program = parse(text)
    except VeriMorphError:
        return
    assert parse(canonical_source(program)) == program


@pytest.mark.parametrize(
    "source",
    [
        "x" * 65537,
        "FUNC main() { RETURN " + "(" * 100 + "1" + ")" * 100 + "; }",
        "FUNC main() {" + "IF 1 {" * 100 + "RETURN 1;" + "}" * 101,
        "FUNC main() { RETURN " + "1+" * 5000 + "1; }",
        "FUNC main() { RETURN " + "9" * 1000 + "; }",
    ],
    ids=["oversize", "deep-expression", "deep-block", "long-chain", "long-integer"],
)
def test_parser_abuse(source):
    with pytest.raises(VeriMorphError):
        parse(source)


@pytest.mark.parametrize(
    "bad",
    [
        Node("binary", "**", (Node("number", 1), Node("number", 2))),
        Node("call", "eval", (Node("block"),)),
        Node("number", True),
        Node("evolve", 1001),
        Node("unknown"),
    ],
)
def test_structural_invalid_nodes(bad):
    program = parse("FUNC main() { RETURN 1; }")
    malformed = Program((replace(program.functions[0], body=(bad,)),))
    with pytest.raises(VeriMorphError):
        validate_structure(malformed)
