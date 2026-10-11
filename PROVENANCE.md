# Provenance format (verimorph-ledger-1)

Local-first canonical JSONL. Each event has event_id, previous hash, payload and
SHA-256 hash of the other three fields. ASCII-escaped, sorted-key compact JSON,
no NaN/Infinity. Event sequence begins with header and must end with a seal.
No timestamps are claimed: deterministic run IDs bind snapshot/seed/mode/config.

Header captures canonical initial source/hash, policy, oracle, limits, seed,
verifier/format versions and operation. Baseline captures case results and score.
Each top-level proposal captures parent, operator/target/before/after, RNG state,
candidate hashes when constructed, completed verification stages, case results,
invariants, score/baseline, decision, rejection stage/reason, resource usage and
resulting snapshot. Nested previews capture proposal/candidate/results or failure,
shared consumption and speculative decision. End seals final snapshot/source,
score, attempt count, status and resource use.

Evidence is append-only through the runtime interface and fsynced for file-backed
runs. Existing paths are never overwritten. A failed append poisons the session
and cannot be followed by a commit. A crash may leave an incomplete record/file;
no recovery of incomplete runs is claimed. Memory-backed ledgers hold canonical
strings, not mutable dicts exposed to program state.

Read/write cap: 8 MiB; 1,026 events; read event cap 262,144 characters. Program
source, execution output and search counts add tighter runtime bounds. Terminal
records are reserved up front so budget exhaustion can be explained without
allowing additional computation. Inspector commands are host tools, not language
capabilities.

```sh
verimorph history run.jsonl
verimorph replay run.jsonl
verimorph inspect examples/evolve.vm
verimorph diff examples/evolve.vm final.vm
```

Snapshot content hash binds canonical source and language version. Snapshot ID
also binds parent ID, verifier version, full policy hash and full oracle hash.
Two identical programs in different lineages may have different snapshot IDs.
Hashes prove neither authorship nor host honesty. Keep an independent final
anchor for authenticity; semantic replay verifies consistency against execution.
