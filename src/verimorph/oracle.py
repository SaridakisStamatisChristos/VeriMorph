"""Frozen external behavioral contracts and integer fitness objective."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .errors import VeriMorphError
from .language import MAX_INT, MIN_INT, integer
from .runtime import Result
from .snapshots import digest


@dataclass(frozen=True, slots=True)
class Case:
    args: tuple[int, ...] = ()
    target: int = 12
    expected_output: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        integer(self.target)
        if (
            type(self.args) is not tuple
            or len(self.args) > 16
            or self.expected_output is not None
            and (type(self.expected_output) is not tuple or len(self.expected_output) > 256)
        ):
            raise VeriMorphError("oracle", "invalid case")
        for x in (*self.args, *(self.expected_output or ())):
            integer(x)


@dataclass(frozen=True, slots=True)
class Oracle:
    cases: tuple[Case, ...] = (Case(),)
    minimum: int = MIN_INT
    maximum: int = MAX_INT
    version: str = "squared-error-1"

    def __post_init__(self) -> None:
        if (
            type(self.cases) is not tuple
            or not 1 <= len(self.cases) <= 64
            or any(type(c) is not Case for c in self.cases)
        ):
            raise VeriMorphError("oracle", "1..64 immutable cases required")
        integer(self.minimum)
        integer(self.maximum)
        if self.minimum > self.maximum or self.version != "squared-error-1":
            raise VeriMorphError("oracle", "invalid invariant/version")

    def data(self) -> dict[str, object]:
        return asdict(self)

    @property
    def identity(self) -> str:
        return digest(self.data())

    def score(self, results: tuple[Result, ...]) -> int:
        if len(results) != len(self.cases):
            raise VeriMorphError("invariant", "missing case results")
        for case, result in zip(self.cases, results, strict=True):
            if not self.minimum <= result.returned <= self.maximum:
                raise VeriMorphError("invariant", "return outside mandatory range")
            if case.expected_output is not None and result.output != case.expected_output:
                raise VeriMorphError("invariant", "output contract mismatch")
        return -sum((r.returned - c.target) ** 2 for c, r in zip(self.cases, results, strict=True))
