# VeriMorph campaign result

The prototype's concept has been rebuilt around an immutable AST and a small
trusted kernel. Source lines are never edited in place. A candidate must pass
external mutation policy, bounded parser/structure/static gates, fresh execution,
behavioral contracts and an immutable external oracle before journaled commit.
Nested evaluations consume the same sticky resource account.

Architecture and language decisions: signed int64/floor division, lexical locals,
strict definite assignment, three value-only mutation operators, a greedy seeded
search, SplitMix64, immutable content/lineage snapshots, JSONL evidence, no network,
filesystem, Python evaluation, optimizer, cloud infrastructure or runtime dependencies.
See ARCHITECTURE.md and SPEC.md for exact semantics.

All six historical issues were reproduced in the supplied local code. The five
original files remain byte-identical and excluded from runtime installation.
Reward tampering reproduced deterministically at seed 0 / attempt 6; the original
score changed from 100 to 101 while main's behavior stayed unchanged.

Falsification covered rollback, malformed ASTs, objective/verifier/policy targets,
recursive EVOLVE, loops/calls, output/audit floods, state leakage, same-seed runs,
rehashed false history, truncation, malformed/deep parser input, host capabilities,
and journal I/O fault injection. No optimizer exists, so optimizer miscompilation
is N/A. Observed bugs and repairs are recorded in failure-repair-ledger.json.

The executed suite contains 146 passing tests, including generated/property,
metamorphic, adversarial and historical probes. Strict typing, lint/format,
dependency audit, package build, legacy hashes and wheel CLI smoke passed locally.
Exact coverage and compatibility evidence are in manifest.json; CI observation
is maintained in ci.json rather than inferred from workflow file presence.

Benchmarks record seven repetitions, raw samples, dispersion, CPU/OS/Python,
checked workload hash and command. They measure parse, execution, static checks,
snapshot creation, 32-candidate evaluation, fsync provenance and replay. No
external baseline or performance superiority is claimed. See benchmark.json.

## Reproduce

```sh
python -m venv .venv
# POSIX: . .venv/bin/activate; Windows: .venv\Scripts\Activate.ps1
pip install --require-hashes -r requirements-dev.lock
pip install --no-build-isolation --no-deps -e .
python scripts/verify.py
python scripts/check_manifest.py
python scripts/reproduce_legacy.py
python -m pytest tests/test_transaction.py tests/test_budget.py tests/test_replay.py -q
python -m pytest tests/test_adversarial.py tests/test_history.py -q
verimorph run examples/self_modify.vm --config examples/self_modify.json --arg 1 --ledger self-run.jsonl
verimorph evolve examples/evolve.vm --seed 42 --ledger run.jsonl
verimorph replay run.jsonl
verimorph history run.jsonl
python benchmarks/bench.py --repetitions 7 --inner 20
python -m pip_audit -r requirements-dev.lock --disable-pip
```

## Separate verdicts and exact remaining limits

| Dimension | Verdict |
|---|---|
| Code quality | Typed, modular, small stdlib-only runtime; reviewable local implementation |
| Correctness confidence | Strong executable evidence for stated static/transaction/resource invariants; finite behavior cases only |
| Security posture | Enforced language boundary under trusted Python/OS; no OS sandbox or hostile-host claim |
| Reproducibility | Seeded semantic replay and checked evidence; deadlines/host stack may differ across environments |
| Research readiness | Complete experimental artifact; publication novelty/theorems/external comparisons remain unproven |
| Production readiness | Suitable for declared local experiments; not qualified for hostile multitenancy, safety-critical or durable concurrent service use |

No unresolved BLOCKER or HIGH defect was identified within the declared threat
model. Independent human review and mechanized proofs are absent; resource
accounting is cooperative and does not impose an OS RSS ceiling; concurrent/durable
commit recovery is absent; trusted-anchor distribution is the caller's responsibility;
exhaustive prior-art clearance/external performance comparison is absent.

Recommended next work follows from these limits: independent kernel review, a
formal transition/resource model if pursuing a paper, and held-out/ablated research
experiments. OS process supervision and durable concurrency belong to a separate
scope if deployment beyond the current model is requested.
