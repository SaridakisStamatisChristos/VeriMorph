# Integer language and execution contract (integer-1)

VeriMorph 0.1.0 intentionally replaces the historical grammar. Compatibility is
limited to the conceptual use of functions, arithmetic, loops and evolution.

## Lexical grammar

UTF-8 source: at most 65,536 bytes; canonical source must also fit this limit.
ASCII identifiers match `[A-Za-z][A-Za-z0-9_]{0,63}`. Keywords are case-sensitive.
Whitespace separates tokens; `#` starts a line comment. There are no strings,
arrays, imports, objects, attributes, filesystem or network primitives.
Tokens have at most 64 characters. Token count <=16,384; AST nodes <=4,096;
parser nesting and AST path depth <=48. Function count <=128; parameters and
call arguments <=16; distinct local variables per function <=128.

```ebnf
program   = function, { function } ;
function  = "FUNC", identifier, "(", [identifier, {",", identifier}], ")", block ;
block     = "{", {statement}, "}" ;
statement = identifier, "=", expression, ";"
          | "RETURN", expression, ";"
          | "PRINT", expression, ";"
          | "IF", expression, block, ["ELSE", block]
          | "WHILE", expression, block
          | "EVOLVE", positive_integer_literal, ";" ;
primary   = integer_literal | identifier | "(", expression, ")"
          | identifier, "(", [expression, {",", expression}], ")" ;
```

Precedence, low to high: `== !=`; `< <= > >=`; `+ -`; `* /`; unary `+ -`;
primary/call. Binary operators associate left. Comparisons return 0 or 1 and
may chain as ordinary left-associative binary operations, not Python comparisons.
Unary numeric constants normalize to signed numeric AST nodes.

## Values and scope

Every language value is a signed 64-bit integer [-2^63, 2^63-1]. Literals,
inputs, unary results and arithmetic results reject overflow. Multiplication
uses bounded host intermediate integers (at most 128 bits). `/` is mathematical
floor division, including negative operands. Zero division rejects. No floating
point, wraparound, or implicit coercion. Nonzero is true; zero is false.

Variables are function-local. Parameters bind into a fresh frame; assignments
stay in that frame. There are no globals. Reading an undefined variable is a
static rejection unless definitely assigned on all preceding branch paths;
the runtime independently rejects missing variables. Loop assignments do not
establish definite assignment after the loop. Static analysis checks unreachable
code conservatively too. Calls require a defined function and exact arity.
Return immediately exits the function; a function reaching the end returns 0.
The entry is `main`; its parameters receive CLI `--arg` or external oracle inputs.
Arguments evaluate left to right. Functions may recurse under a shared depth cap.

`WHILE` reevaluates its condition before each iteration. Empty infinite loops
still charge condition evaluations. `PRINT` appends integer outputs to a bounded
trace; it never directly invokes a host printer or file writer.

## Mutation, evolution and commit

There is no MODIFY_LINE, RECOMPILE_AND_GOTO, OPTIMIZE, or SEND_SOURCE compatibility
path. Numeric and arithmetic/comparison proposals replace only node values,
retain AST structure, and require an externally allowed function/operator.
The external policy also constrains mutated numeric values to its declared range.

`EVOLVE N;` uses literal N in 1..1000 and requires an explicit policy capability.
In a normal kernel run it invokes a seeded search through the same commit gate.
Active execution pins the old snapshot: changes affect future runs, not already
running frames. During oracle/candidate evaluation, EVOLVE creates speculative
nested evaluations only; their snapshots never enter committed state. All work
shares the root budget and RNG stream. Unconditional recursive EVOLVE therefore
exhausts the shared evaluation-depth budget, rather than spawning fresh accounts.

A candidate passes mutation policy, structure/parse, static semantics,
capabilities, snapshot consistency, bounded execution on every oracle case,
mandatory return/output invariants and external scoring. Strictly greater score
is required; ties reject. The squared-error oracle returns
`-sum((returned-target)^2)` over fixed cases. Host scores may exceed 64-bit range;
there are at most 64 terms of bounded integer difference. This is deterministic.

Commit appends evidence before replacing exactly one immutable snapshot
reference. Rejection preserves that reference and fresh-run behavior. Resource
usage, RNG advancement and rejection evidence persist; they are not rolled back.
The kernel is single-owner/thread. No durable multi-process service commit is
claimed. Replay reconstructs journaled snapshot transitions.

## Failure and resources

Expected failures raise VeriMorphError with stage/reason; budget errors are
sticky BudgetExceeded. CLI failures return exit 2. Search retains its last valid
snapshot and seals evidence with failed/exhausted status. No improvement is a
successful completed search, not a failure. Ledger I/O failure prevents commit,
poisons the session, and leaves an incomplete ledger that replay rejects.

Limits: root cumulative steps, VM evaluations, mutations, candidate compilations,
canonical source bytes admitted, AST nodes admitted, output bytes and reserved
audit records; shared active call depth and evaluation depth; cooperative monotonic
wall deadline. Compilation means a candidate admission operation (including
bounded roundtrip checks), not every internal parser invocation. Parser work is
bounded per compilation but not charged as VM steps. There is no measured-RSS
or hard OS memory/time guarantee. Bounded integer width, local/frame counts, AST,
source and output constrain language allocation. Embedding-host allocations and
blocking trusted I/O are outside this guarantee. A host RecursionError becomes
sticky `host_stack` budget exhaustion.

Header reserves four records: header, end, and at most two terminal/run events.
Baseline and each mutation/nested attempt reserve another before computation.
Unused reservations are conservative. JSONL is independently capped at 8 MiB
and 1,026 records. A rejected record still consumes its reserved resources.

## Semantic changes from history

Local frames replace global variables; undefined variables no longer yield zero;
source edits are replaced by value-level proposals; fitness is external; network
and optimization are removed; all child computation shares one account; objective
functions in program source are ordinary immutable code by default and have no
privileged scoring role. HMAC logging is replaced by explicit hash-chain checking
and semantic replay with optional trusted final anchor.
