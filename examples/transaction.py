"""Run after installing VeriMorph: python examples/transaction.py."""

from verimorph.kernel import Kernel
from verimorph.mutation import Proposal

kernel = Kernel("FUNC fitness() { RETURN 100; } FUNC main() { RETURN 5; }")
parent = kernel.committed
assert not kernel.attempt(Proposal(1, "literal", "fitness/0/0", 100, 101))
assert kernel.committed is parent
assert not kernel.attempt(Proposal(2, "literal", "main/0/0", 5, "RETURN ("))
assert kernel.committed is parent
assert kernel.attempt(Proposal(3, "literal", "main/0/0", 5, 6))
kernel.finish()
print(kernel.committed.source, end="")
