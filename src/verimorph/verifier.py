"""Mandatory static semantics and capability checks; no advisory bypass."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .errors import VeriMorphError
from .language import Node, Program, validate_structure, walk

VERIFIER_VERSION = "static-1"


@dataclass(frozen=True, slots=True)
class Policy:
    mutable_functions: tuple[str, ...] = ("main",)
    operators: tuple[str, ...] = ("literal", "arithmetic", "comparison")
    literal_min: int = -1000000
    literal_max: int = 1000000
    allow_evolve: bool = False
    version: str = "policy-1"

    def __post_init__(self) -> None:
        if (
            type(self.mutable_functions) is not tuple
            or not self.mutable_functions
            or len(set(self.mutable_functions)) != len(self.mutable_functions)
        ):
            raise VeriMorphError("policy", "nonempty unique function tuple required")
        if (
            type(self.operators) is not tuple
            or not self.operators
            or not set(self.operators) <= {"literal", "arithmetic", "comparison"}
        ):
            raise VeriMorphError("policy", "invalid operator allowlist")
        if (
            type(self.literal_min) is not int
            or type(self.literal_max) is not int
            or not -1000000 <= self.literal_min <= self.literal_max <= 1000000
            or type(self.allow_evolve) is not bool
            or self.version != "policy-1"
        ):
            raise VeriMorphError("policy", "invalid bounds/version/capability")

    def data(self) -> dict[str, object]:
        return asdict(self)


def verify(program: Program, policy: Policy) -> None:
    validate_structure(program)
    names = {f.name for f in program.functions}
    if "main" not in names:
        raise VeriMorphError("static", "main required")
    if not set(policy.mutable_functions) <= names:
        raise VeriMorphError("policy", "unknown mutable function")
    for _, node in walk(program):
        if node.kind == "evolve" and not policy.allow_evolve:
            raise VeriMorphError("capability", "EVOLVE denied by policy")
    for function in program.functions:
        variables = set(function.params)
        for _, node in walk(Program((function,))):
            if node.kind == "assign":
                variables.add(str(node.value))
        if len(variables) > 128:
            raise VeriMorphError("static", "local variable limit")
        _block(function.body, set(function.params), program)


def _expression(node: Node, defined: set[str], program: Program) -> None:
    if node.kind == "var" and node.value not in defined:
        raise VeriMorphError("static", f"variable {node.value} not definitely assigned")
    if node.kind == "call":
        target = program.function(str(node.value))
        if len(node.children) != len(target.params):
            raise VeriMorphError("static", "call arity mismatch")
    for child in node.children:
        _expression(child, defined, program)


def _block(nodes: tuple[Node, ...], defined: set[str], program: Program) -> set[str]:
    current = set(defined)
    for node in nodes:
        if node.kind in ("assign", "return", "print"):
            _expression(node.children[0], current, program)
            if node.kind == "assign":
                current.add(str(node.value))
        elif node.kind == "if":
            _expression(node.children[0], current, program)
            yes = _block(node.children[1].children, current, program)
            no = _block(node.children[2].children, current, program)
            current |= yes & no
        elif node.kind == "while":
            _expression(node.children[0], current, program)
            _block(node.children[1].children, current, program)
    return current
