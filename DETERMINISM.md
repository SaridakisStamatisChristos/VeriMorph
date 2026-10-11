# Determinism and replay contract

Given identical canonical initial program, external policy/oracle/limits, seed,
operation and arguments, and versioned semantics, completed compute-bounded runs
produce equivalent proposals, decisions, resource charges and final snapshots.
Source whitespace/comments do not change canonical identity or admission charges.
No timestamp or wall-duration metric enters semantic evidence.

The RNG is SplitMix64: unsigned 64-bit state starts at the seed; each draw adds
0x9E3779B97F4A7C15, then xor-shift/multiply by 0xBF58476D1CE4E5B9 and
0x94D049BB133111EB with 64-bit masking and a final xor-shift by 31.
Index choice is multiply-high `floor(word*count/2^64)`. It is deterministic;
no cryptographic or perfect-uniformity claim is made. Eligible node order follows
function/source order then depth-first AST child order. Literal choices are -1,+1
within bounds; operator choices use the documented order in mutation.py.

Nested evaluation shares the stream as well as the root budget. Search is greedy
hill-climbing with strict improvement; each proposal is based on the current best.
Ties and invalid candidates consume resources and advance the stream without commit.

Replay validates hash-chain sequence/end seal, reconstructs config and initial
snapshot, reexecutes search/run/manual proposals, and compares every semantic event.
It does not just trust the recorded score or final source. An external expected
anchor additionally detects replacement by another valid history.

```sh
verimorph evolve examples/evolve.vm --seed 42 --ledger run.jsonl
verimorph replay run.jsonl --anchor <printed-anchor>
```

Wall deadline exhaustion and host-stack exhaustion may occur differently across
platforms, instrumentation and load. Their histories are not promised replayable
on another environment. Replay reports a mismatch instead of fabricating equivalence.
Successful or deterministic count-exhausted runs are the replay target. Version
changes intentionally reject old evidence unless a future compatible adapter is
implemented. Only the current ledger/semantic versions are supported.
