# Delivery plan and topology lock

Users: researchers and systems engineers studying bounded self-modification.
Python with no runtime dependencies keeps the trusted core inspectable.

Batch 1: historical preservation, reproduction, contract, semantics.
Batch 2: immutable AST/parser, static verifier, execution budget and VM.
Batch 3: snapshots, AST proposals, external oracle, transactional kernel,
seeded search, hash-chained ledger, replay, CLI.
Batch 4: examples, generated/adversarial/metamorphic tests, CI, package.
Batch 5: falsification, repairs, measured benchmark, evidence, final audit.

Dependency graph: language -> verifier/snapshot/mutation; budget + language ->
runtime; snapshot + verifier + runtime + oracle + mutation + provenance ->
kernel; kernel -> replay/CLI. No program node contains host callbacks, policies,
or objectives. The VM receives a narrow evolution callback only from trusted
kernel code. Candidates cannot supply callbacks. Search creates fresh VM state
for every oracle case. A running VM pins its snapshot; commits affect future runs.

Primary risks: parsing depth, integer amplification, recursive evaluation,
replay validation, partial mutation, host I/O failure. Their gates include
independent arithmetic reference tests, generated mutations, bounded recursion,
fault injection, and clean-package invocation. Wall deadlines are cooperative
and excluded from semantic determinism claims.
