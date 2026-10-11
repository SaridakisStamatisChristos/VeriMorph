"""Fail-closed errors with stable stage attribution."""


class VeriMorphError(Exception):
    """Expected language/kernel failure."""

    def __init__(self, stage: str, reason: str):
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}: {reason}")


class BudgetExceeded(VeriMorphError):
    def __init__(self, dimension: str):
        super().__init__("budget", f"exhausted {dimension}")
