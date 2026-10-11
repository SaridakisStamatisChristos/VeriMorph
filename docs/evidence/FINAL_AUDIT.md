# Cold final audit

Review performed against the complete source and executable boundaries, treating
the repository as a third-party submission. This is a separate review phase by
the implementing assistant, not an independent human or external security audit.

Reviewed parser/AST admission, int64 arithmetic, lexical frames, mutation allowlists,
oracle separation, all root charge sites, pinned execution, journal-before-swap,
replay reexecution, package exclusion of legacy, CLI errors, dead code/dependencies,
workflow commands, and documentation assertions.

## Findings and dispositions

- HIGH: noncanonical initial accounting caused replay mismatch. Fixed and reverified.
- HIGH: journal failure needed session poisoning to exclude retries after partial I/O.
  Fixed; fsync fault injection verifies unchanged committed reference and no retry.
- MEDIUM: VM reuse retained output. Fixed through an enforced single-use contract.
- MEDIUM: host recursion exceptions needed fail-closed attribution. Fixed; an
  independent fault-injected path verifies sticky accounting after host stack failure.
- MEDIUM: signed numeric canonicalization needed stable negative literal nodes.
  Fixed; generated arithmetic/roundtrip and MIN_INT tests verify behavior.
- INFORMATIONAL: no OS sandbox, no universal behavioral proof, unauthenticated
  hash chains without external anchor, cooperative deadlines, single-owner kernel,
  finite case overfitting. Explicit design limits, not hidden security claims.
- INFORMATIONAL: external publication novelty and production qualification remain
  unproven. Research position explicitly separates implementation from novelty.

Detailed reproducers/earliest invalidated phases are in failure-repair-ledger.json.
No unresolved BLOCKER or HIGH code finding identified within the declared model.
CI acceptance is pending observation and will be recorded separately on exact heads.
Python/OS compatibility is claimed only where execution evidence exists.

## Unresolved issues

1. Independent human review/mechanized proof absent; do not claim formal verification.
2. No OS isolation, hard RSS/deadline enforcement, or hostile-host protection.
3. No durable multi-process commit recovery or concurrent kernel support.
4. No exhaustive prior-art clearance or external performance baseline.
5. Deadline/host-stack exhaustion histories may not replay on other environments.

These are documented limits for this experimental runtime. Expanding the threat
model would turn items 2/3 into blocking architecture work. They are not required
for a trusted-host, single-owner local experiment.
