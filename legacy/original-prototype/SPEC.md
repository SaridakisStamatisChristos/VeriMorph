# Mini-Language Near NASA-Grade — Formal Spec (Skeleton)

## 1. Memory Model
- Heap soft limit: 1 GiB (process RSS)
- Stack depth limit: 1000 frames
- Variables: function-parameter binding overrides global
- GC: Python runtime; no custom GC in this build

## 2. Execution Model
- Each AST node visit increments a **step**.
- `max_steps` triggers `RuntimeLimit`.
- Self-mod semantics: `MODIFY_LINE` mutates `source_lines`, `RECOMPILE_AND_GOTO` raises jump → `compile()` → resume.

## 3. Security Model
- Network disabled by default; allowlist enforced when enabled.
- Source integrity: optional HMAC-SHA256 recorded in audit log.
- Validation: size, line length, charset; forbidden patterns.

## 4. Determinism
- Evolution uses seeded RNG when `deterministic_seed` set.
- Fitness evaluation uses fixed seed (12345).

## 5. Resource Contracts
- Decorator `@resource_contract(max_steps, max_time_ms)` checks local invariants for decorated operations.
