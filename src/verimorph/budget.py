"""One sticky root account. Descendants use the same object and cannot reset it."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import NoReturn

from .errors import BudgetExceeded, VeriMorphError


@dataclass(frozen=True, slots=True)
class Limits:
    steps: int = 100000
    evaluations: int = 512
    mutations: int = 256
    compilations: int = 256
    source_bytes: int = 1048576
    ast_nodes: int = 65536
    output_bytes: int = 16384
    audit_events: int = 258
    evaluation_depth: int = 8
    call_depth: int = 32
    wall_ms: int = 10000

    def __post_init__(self) -> None:
        for key, value in asdict(self).items():
            if type(value) is not int or not 1 <= value <= 10**9:
                raise VeriMorphError("config", f"invalid limit {key}")
        if self.call_depth > 32 or self.evaluation_depth > 8:
            raise VeriMorphError("config", "depth exceeds safe host stack bounds")


class ExecutionBudget:
    def __init__(self, limits: Limits | None = None):
        limits = Limits() if limits is None else limits
        self._limits = limits
        self._used = {
            k: 0 for k in asdict(limits) if k not in ("evaluation_depth", "call_depth", "wall_ms")
        }
        self._depth = 0
        self._calls = 0
        self._deadline = time.monotonic() + limits.wall_ms / 1000
        self._exhausted: str | None = None

    @property
    def limits(self) -> Limits:
        return self._limits

    def check(self) -> None:
        if self._exhausted is not None:
            raise BudgetExceeded(self._exhausted)
        if time.monotonic() > self._deadline:
            self._exhausted = "wall_ms"
            raise BudgetExceeded("wall_ms")

    def fail(self, dimension: str) -> NoReturn:
        self._exhausted = dimension
        raise BudgetExceeded(dimension)

    def charge(self, dimension: str, amount: int = 1) -> None:
        self.check()
        if dimension not in self._used or type(amount) is not int or amount < 0:
            raise VeriMorphError("budget", "invalid charge")
        limit = getattr(self._limits, dimension)
        if self._used[dimension] + amount > limit:
            self._exhausted = dimension
            raise BudgetExceeded(dimension)
        self._used[dimension] += amount

    @contextmanager
    def evaluation(self) -> Iterator[None]:
        self.charge("evaluations")
        if self._depth >= self._limits.evaluation_depth:
            self._exhausted = "evaluation_depth"
            raise BudgetExceeded("evaluation_depth")
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1

    @contextmanager
    def call(self) -> Iterator[None]:
        self.check()
        if self._calls >= self._limits.call_depth:
            self._exhausted = "call_depth"
            raise BudgetExceeded("call_depth")
        self._calls += 1
        try:
            yield
        finally:
            self._calls -= 1

    def usage(self) -> dict[str, int]:
        return dict(self._used)
