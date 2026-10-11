"""Value-only AST proposals; node identities are paths in a parent snapshot."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .errors import VeriMorphError
from .language import Node, Program, integer, walk
from .verifier import Policy


@dataclass(frozen=True, slots=True)
class Proposal:
    mutation_id: int
    operator: str
    target: str
    before: str | int
    after: str | int

    def apply(self, program: Program, policy: Policy) -> Program:
        nodes = dict(walk(program))
        if self.target not in nodes or self.target.split("/")[0] not in policy.mutable_functions:
            raise VeriMorphError("mutation-policy", "target outside mutable domain")
        node = nodes[self.target]
        if (
            self.operator not in policy.operators
            or type(self.before) is not type(node.value)
            or self.before != node.value
        ):
            raise VeriMorphError("mutation-policy", "operator denied or stale before value")
        if self.operator == "literal":
            if (
                node.kind != "number"
                or type(self.after) is not int
                or not policy.literal_min <= self.after <= policy.literal_max
            ):
                raise VeriMorphError("mutation-policy", "invalid literal mutation")
            integer(self.after)
        else:
            domain = (
                ("+", "-", "*", "/")
                if self.operator == "arithmetic"
                else ("<", "<=", ">", ">=", "==", "!=")
            )
            if node.kind != "binary" or node.value not in domain or self.after not in domain:
                raise VeriMorphError("mutation-policy", "invalid operator substitution")
        if self.after == self.before:
            raise VeriMorphError("mutation-policy", "no-op proposal")

        def visit(n: Node, path: str) -> Node:
            if path == self.target:
                return replace(n, value=self.after)
            return replace(
                n, children=tuple(visit(c, f"{path}/{i}") for i, c in enumerate(n.children))
            )

        return Program(
            tuple(
                replace(f, body=tuple(visit(n, f"{f.name}/{i}") for i, n in enumerate(f.body)))
                for f in program.functions
            )
        )


class RNG:
    """Specified SplitMix64 stream, independent of Python's random implementation."""

    MASK = 2**64 - 1

    def __init__(self, seed: int):
        if type(seed) is not int or not 0 <= seed <= self.MASK:
            raise VeriMorphError("config", "seed must be unsigned 64-bit")
        self.state = seed

    def next(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & self.MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & self.MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & self.MASK
        return (z ^ (z >> 31)) & self.MASK

    def choose(self, count: int) -> int:
        if count <= 0:
            raise VeriMorphError("mutation", "empty choice")
        # Multiply-high mapping is deterministic; no uniformity claim is needed.
        return (self.next() * count) >> 64


def generate(program: Program, policy: Policy, rng: RNG, index: int) -> Proposal:
    choices = []
    for path, node in walk(program):
        if path.split("/")[0] not in policy.mutable_functions:
            continue
        if node.kind == "number" and "literal" in policy.operators:
            options: tuple[str | int, ...] = tuple(
                x
                for x in (int(node.value) - 1, int(node.value) + 1)
                if policy.literal_min <= x <= policy.literal_max
            )
            operator = "literal"
        elif node.kind == "binary":
            operator = "arithmetic" if node.value in ("+", "-", "*", "/") else "comparison"
            domain = (
                ("+", "-", "*", "/")
                if operator == "arithmetic"
                else ("<", "<=", ">", ">=", "==", "!=")
            )
            options = (
                tuple(x for x in domain if x != node.value) if operator in policy.operators else ()
            )
        else:
            continue
        if options:
            choices.append((path, node, operator, options))
    if not choices:
        raise VeriMorphError("mutation", "no eligible targets")
    path, node, operator, options = choices[rng.choose(len(choices))]
    return Proposal(index, operator, path, node.value, options[rng.choose(len(options))])
