# Benchmark characterization

Seven measured repetitions with two warmups; each core repetition contains 20 operations.
Shared Linux container on AMD EPYC 9V74; Python 3.12.14. No external baseline or superiority claim.

| Operation | Median µs | Min–max µs |
|---|---:|---:|
| evaluate_32_candidates_fsync_ledger | 4593.66 | 4146.54–5436.18 |
| evaluate_32_candidates_memory_ledger | 3762.27 | 3557.04–3845.09 |
| execute_100_loop_iterations | 301.31 | 299.87–303.53 |
| parse | 50.09 | 49.06–52.86 |
| replay_32_candidates | 6035.14 | 5411.03–6584.23 |
| snapshot | 101.41 | 93.91–108.11 |
| static_verify | 31.17 | 30.79–32.40 |

Exact environment, commands, workload hash, all samples and standard deviations are in benchmark.json.
Fsync provenance ran on the container temporary filesystem; results should not be generalized to other storage.
