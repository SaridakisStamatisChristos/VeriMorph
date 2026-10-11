# Threat model

**Boundary:** hostile VeriMorph source and serialized evidence on a trusted Python
host. Host Python callers, external configuration, packages, OS and storage are
trusted. Language source cannot access their objects. No OS sandbox, memory-safe
native kernel, process isolation, hard deadline, or authenticated storage is claimed.

| Attack | Enforced response | Evidence |
|---|---|---|
| Objective/policy/verifier corruption | No host-object access; default mutability excludes objective-like function; even an allowed function cannot affect external score | transaction objective regression; capability tests |
| Arbitrary source edit/malformed AST | Value-only allowed operators, structure and canonical reparse before execution | malformed AST and rollback tests |
| Mutability target escape | Exact AST path and external function/operator allowlists | generated immutable-node property |
| Infinite loop/deep call | Shared sticky step/call budget | budget tests |
| Recursive EVOLVE/spawning | Shared VM/evaluation budget, capped nesting, speculative descendants | recursive-evolve regression |
| Numeric/memory amplification | int64 arithmetic; bounded source, AST, locals, frames, output | numeric/parser/output attacks |
| Output/audit flooding | Root output/audit charges, ledger size cap | amplification and reservation tests |
| Candidate state leakage | Fresh case VM/frame/output; pinned active snapshot | state leakage and runtime self-modification tests |
| Network/files/host evaluation | No language primitive; unknown calls reject, attribute/string/import grammar absent | capability-denial and AST host-eval scan |
| History alteration | Hash-chain validation and complete replay comparison | altered history and rehashed false score tests |
| Forged complete alternate run | Trusted final anchor required to authenticate expected history | anchor mismatch test; limitations below |
| Ledger write failure | No commit; poison session; incomplete ledger rejected | fsync fault injection |
| Deep parser/evidence input | Byte/token/node/depth and read limits | parser and evidence fuzz tests |

Security-critical checks reject, rather than emitting warnings. There is no
untrusted plugin interface or optional network capability. The historical code
has socket support but is outside the installed runtime and not safe to use as a
sandbox. Preserving it does not endorse its claims.

## Residual limits

Frozen dataclasses protect ordinary Python usage, not a malicious Python caller
using reflection, monkeypatching or object.__setattr__. Such a caller owns the
trusted host and is outside the boundary. Resource budgets cover language work,
not all allocations in Python/OS. Cooperative checks cannot interrupt blocking
fsync or guarantee termination if the host is stalled. MemoryError, OS kill,
power loss and hostile storage require external process/OS supervision.

Hash chains are tamper-evident relative to an expected chain/anchor; they are not
signatures. A host attacker can fabricate and rehash a different internally valid
run. Replay checks consistency, not authorship, timestamps, or truth of hardware
claims. Keep the final anchor in an independently trusted channel if authenticity
matters. Hash collision resistance is assumed; not proved by this repository.

Finite behavioral cases are not universal program verification. Definite assignment
and structural checks are enforced over all admitted nodes; behavioral invariants
are tested only on externally declared cases. Evolution can overfit those cases.
This repository is suitable for bounded experiments, not hostile multitenant
execution or safety-critical operation without further independent assurance.
