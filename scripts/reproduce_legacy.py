"""Bounded, offline reproduction of defects in the supplied local prototype."""

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "legacy/original-prototype/interpreter_secure.py"
spec = importlib.util.spec_from_file_location("legacy_probe", path)
assert spec and spec.loader

m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
results = {}
source = ["FUNC main() {", "RETURN 1", "}"]
i = m.Interpreter(source)
i._do_modify_line(m.ModifyLineStmt(m.Number(2), m.StringLit("RETURN (")))
try:
    i.compile()
except SyntaxError as e:
    results["nontransactional"] = {
        "live_source_changed": i.source_lines != source,
        "compile_error": str(e),
    }
source = ["FUNC fitness() {", "RETURN 100", "}", "FUNC main() {", "RETURN 1", "}"]
i = m.Interpreter(source, deterministic_seed=0)
baseline = i._score_program(source, "main", "fitness")
for attempt in range(500):
    candidate = i._mutate_source_once(source)
    if candidate[1] == "RETURN 101":
        results["fitness_tampering"] = {
            "seed": 0,
            "attempt": attempt,
            "baseline": baseline,
            "candidate": i._score_program(candidate, "main", "fitness"),
            "target_behavior_unchanged": candidate[4] == source[4],
        }
        break
# Probe instrumentation bounds evaluator spawning without running an unbounded attack.
original = m.Interpreter._score_program
calls = 0
parent_steps = []


def bounded_probe(self, *args):
    global calls
    calls += 1
    parent_steps.append(self.steps)
    if calls >= 8:
        raise m.RuntimeLimit("probe stops at eight nested score calls")
    return original(self, *args)


m.Interpreter._score_program = bounded_probe
try:
    i = m.Interpreter(["FUNC main() {", "EVOLVE main 1", "}"], max_steps=3)
    i.call("main", [])
except m.RuntimeLimit:
    pass
finally:
    m.Interpreter._score_program = original
results["recursive_evaluation"] = {
    "score_calls": calls,
    "first_parent_steps": parent_steps[:8],
    "per_interpreter_limit": 3,
    "probe_cap": 8,
    "interpretation": "fresh child counters; bounded instrumentation, not a timeout claim",
}
results["demo_line_target"] = {"line2": m.DEMO_SOURCE.splitlines()[1], "line2_inside": "fitness"}
i = m.Interpreter(
    source, static_analyzer=lambda program: ["mandatory failure probe"], hmac_key=b"local-test"
)
results["advisory_analysis"] = {
    "compiled_despite_warning": i.program is not None,
    "warning_logged": any(e.get("kind") == "static_warn" for e in i.audit.events),
}
results["hmac"] = {
    "calculation_logged": any(e.get("kind") == "integrity" for e in i.audit.events),
    "trusted_expected_mac_input": False,
}
results["original_sha256"] = {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.parent.iterdir() if p.is_file()
}
with contextlib.redirect_stdout(io.StringIO()):
    demo = m.Interpreter(m.DEMO_SOURCE.splitlines())
    try:
        demo.call("main", [])
    except m.RecompileJump:
        demo.compile()
results["demo_actual_edit"] = {
    "line2_after": demo.source_lines[1],
    "main_assignment": demo.source_lines[5],
}
print(json.dumps(results, indent=2, sort_keys=True))
