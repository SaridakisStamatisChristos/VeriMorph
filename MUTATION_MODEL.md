# Mutation model

External Policy declares a tuple of allowed functions, operator classes, numeric
bounds and whether language EVOLVE is allowed. Default: main; literal/arithmetic/
comparison; [-1,000,000, 1,000,000]; EVOLVE denied.

| Operator | Allowed value change | Structure |
|---|---|---|
| literal | number -> bounded signed number | unchanged |
| arithmetic | +, -, *, / -> another from same set | binary children unchanged |
| comparison | <, <=, >, >=, ==, != -> another from same set | binary children unchanged |

Function names/parameters, variable names, statements, EVOLVE count, trusted
configuration and node kinds are never mutation targets. This narrow surface is
intentional. Programs may contain larger int64 constants, but generation only
proposes numeric neighbors within policy bounds. A stale before value, no-op,
wrong node kind, unknown target, wrong operator or disallowed function rejects.

Node paths such as `main/0/0` mean function main, statement 0, expression child 0.
Identity is relative to the recorded parent snapshot; raw source line numbers have
no meaning. Value-only changes preserve topology. Mutation ID, class, target,
before/after, RNG state and parent/candidate IDs are recorded per attempt.

A host constructs Proposal or search generates one; apply returns a new immutable
Program. Kernel performs complete admission, static checks, fresh execution,
mandatory behavioral contracts and immutable scoring before committing. This is
application-level transactionality with no concurrent or durable-service claim.

Run `python examples/transaction.py` for immutable-objective rejection, malformed
proposal rollback, and a successful commit. Runtime EVOLVE is illustrated in
examples/self_modify.vm with an external phase-0 oracle; the active phase-1 frame
keeps its original snapshot, while subsequent execution observes the new value.
