# Evidence manifest

CONDITIONAL — CI observation pending

| Gate | State | Evidence |
|---|---|---|
| A clean installation | VERIFIED | scripts/package_smoke.py; docs/evidence/package-smoke.json |
| B specified integer language | VERIFIED | tests/test_language.py; docs/evidence/test-results.txt |
| C atomic AST mutation and rejection | VERIFIED | tests/test_transaction.py::test_rejected_mutation_preserves_state_and_behavior; tests/test_transaction.py::test_malformed_ast_cannot_commit |
| D immutable trust/objective boundary | VERIFIED | tests/test_transaction.py::test_historical_objective_tampering_regression; tests/test_adversarial.py::test_no_host_or_legacy_capabilities |
| E hierarchical root resource control | VERIFIED | tests/test_budget.py::test_recursive_evolve_never_receives_fresh_account; tests/test_budget.py::test_global_exhaustion |
| F determinism and replay | VERIFIED | tests/test_replay.py::test_search_replay; tests/test_replay.py::test_same_seed_identical_histories_and_final; tests/test_replay.py::test_runtime_self_modification_pins_active_snapshot |
| G inspectable bounded provenance | VERIFIED | tests/test_replay.py::test_altered_history_detection; docs/evidence/seed42.jsonl; tests/test_adversarial.py::test_journal_failure_poisoning_prevents_later_commit |
| H historical failures and falsification | VERIFIED | tests/test_history.py::test_all_historical_failure_modes_reproduced; tests/test_adversarial.py; docs/evidence/failure-repair-ledger.json |
| I package/CLI | VERIFIED | scripts/package_smoke.py; docs/evidence/package-smoke.json |
| J green CI | UNVERIFIED | .github/workflows/ci.yml; docs/evidence/ci.json |
| K accurate docs and research position | VERIFIED | docs/evidence/FINAL_AUDIT.md; docs/research-position.md |
| L explicit security limits | VERIFIED | THREAT_MODEL.md; tests/test_adversarial.py |
| M unchanged original files | VERIFIED | scripts/check_legacy.py; docs/evidence/legacy-reproduction.json |
| N cold final audit | VERIFIED | docs/evidence/FINAL_AUDIT.md; docs/evidence/failure-repair-ledger.json |
| O reproducible benchmark | VERIFIED | benchmarks/bench.py; docs/evidence/benchmark.json |

File checksums: 78 files; see manifest.json. Self-reference exclusions are explicit.
Local Python: 3.12.14. Coverage: 92.81% including branches.

Limitations: finite cases, trusted Python/OS, cooperative time accounting, no OS sandbox or formal proof, single-owner kernel. Research novelty and production qualification are not established.
