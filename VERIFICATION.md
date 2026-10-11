# Verification gates

The pipeline is executable in kernel.py and deliberately fail-closed:

1. External config domain validation and root preflight.
2. Lex/parse/AST structural limits; canonical roundtrip.
3. Mandatory static definite assignment, defined functions/arity and locals cap.
4. Trust/capability checks and explicit mutation target/operator policy.
5. Immutable, lineage-bound candidate construction.
6. Fresh disposable case VMs, sharing the root account.
7. Mandatory output and return-range behavioral contracts.
8. External immutable squared-error fitness.
9. Strict improvement and unchanged committed parent.
10. Evidence append, flush/fsync, then one committed reference swap.

Stages can fail with a precise stage/reason even before candidate hashing. Successful
prefix stages and case results appear in mutation records. No warning channel can
bypass mandatory checks. Finite-case testing is explicitly not a formal proof.

```sh
python scripts/verify.py
python -m pytest tests/test_transaction.py tests/test_budget.py tests/test_replay.py -q
python -m pytest tests/test_adversarial.py -q
python scripts/reproduce_legacy.py
```

Generated tests use Hypothesis for int arithmetic, parser/evidence fuzzing,
canonical roundtrips, immutable-node preservation, rejection atomicity and seeded
search. Arithmetic compares against an independent host reference; mutation state
checks independently rerun the old snapshot rather than trusting decision logs.
Replay reexecutes through a new kernel and compares the entire event sequence.
An AST scan rejects eval/exec/compile calls in the installed source.

Coverage is evidence about exercised paths, not proof of correctness. The final
manifest records measured coverage. No vanity coverage threshold replaces the
behavioral tests. Critical atomicity, objective, nested budgets and replay have
named direct regression tests.
