"""Integer-only VM. No Python objects, network, files, or host imports in the language."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .budget import ExecutionBudget
from .errors import VeriMorphError
from .language import Node, Program, integer


@dataclass(frozen=True, slots=True)
class Result:
    returned: int
    output: tuple[int, ...]


class VM:
    def __init__(
        self, program: Program, budget: ExecutionBudget, evolve: Callable[[int], None] | None = None
    ):
        self.program = program
        self.budget = budget
        self._evolve = evolve
        self._output: list[int] = []
        self._ran = False

    def run(self, args: tuple[int, ...] = ()) -> Result:
        if self._ran:
            raise VeriMorphError("execution", "VM is disposable and may run once")
        self._ran = True
        try:
            with self.budget.evaluation():
                returned = self.call("main", args)
            return Result(returned, tuple(self._output))
        except RecursionError:
            self.budget.fail("host_stack")

    def call(self, name: str, args: tuple[int, ...]) -> int:
        self.budget.charge("steps")
        function = self.program.function(name)
        if len(args) != len(function.params):
            raise VeriMorphError("execution", "argument arity mismatch")
        with self.budget.call():
            local = {p: integer(v) for p, v in zip(function.params, args, strict=True)}
            returned = self.block(function.body, local)
            return 0 if returned is None else returned

    def expression(self, n: Node, local: dict[str, int]) -> int:
        self.budget.charge("steps")
        if n.kind == "number":
            return integer(int(n.value))
        if n.kind == "var":
            if n.value not in local:
                raise VeriMorphError("execution", f"undefined variable {n.value}")
            return local[str(n.value)]
        if n.kind == "call":
            return self.call(str(n.value), tuple(self.expression(c, local) for c in n.children))
        left = self.expression(n.children[0], local)
        if n.kind == "unary":
            return integer(-left if n.value == "-" else left)
        right = self.expression(n.children[1], local)
        op = n.value
        if op == "+":
            value = left + right
        elif op == "-":
            value = left - right
        elif op == "*":
            value = left * right
        elif op == "/":
            if right == 0:
                raise VeriMorphError("execution", "division by zero")
            value = left // right
        elif op == "<":
            value = int(left < right)
        elif op == "<=":
            value = int(left <= right)
        elif op == ">":
            value = int(left > right)
        elif op == ">=":
            value = int(left >= right)
        elif op == "==":
            value = int(left == right)
        elif op == "!=":
            value = int(left != right)
        else:
            raise VeriMorphError("execution", "unknown operator")
        return integer(value)

    def block(self, body: tuple[Node, ...], local: dict[str, int]) -> int | None:
        for n in body:
            self.budget.charge("steps")
            if n.kind == "assign":
                local[str(n.value)] = self.expression(n.children[0], local)
            elif n.kind == "return":
                return self.expression(n.children[0], local)
            elif n.kind == "print":
                value = self.expression(n.children[0], local)
                self.budget.charge("output_bytes", len(str(value).encode()) + 1)
                self._output.append(value)
            elif n.kind == "if":
                selected = n.children[1 if self.expression(n.children[0], local) else 2]
                returned = self.block(selected.children, local)
                if returned is not None:
                    return returned
            elif n.kind == "while":
                while self.expression(n.children[0], local):
                    returned = self.block(n.children[1].children, local)
                    if returned is not None:
                        return returned
            elif n.kind == "evolve":
                if self._evolve is None:
                    raise VeriMorphError("capability", "EVOLVE requires trusted kernel")
                self._evolve(int(n.value))
        return None
