# VeriMorph

A verified runtime for bounded, auditable self-modifying programs.

VeriMorph is an experimental integer-language runtime. It constructs AST changes
as isolated candidates, verifies them, evaluates an immutable external objective,
and records the decision before replacing an immutable committed snapshot.
All descendant execution consumes one root resource budget.

Here, **verified** means passing explicit executable checks. It does not mean
formal verification or OS sandboxing. Host Python and the operating system are
trusted. This is not a general Python replacement.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
verimorph check examples/evolve.vm
verimorph run examples/basic.vm
verimorph evolve examples/evolve.vm --seed 42 --iterations 32 --ledger run.jsonl
verimorph replay run.jsonl
verimorph history run.jsonl
pytest
```

Ledger and output files use exclusive creation. Remove or choose another path
before rerunning an example. No network/file/host capability exists in the language.

The immutable objective and policy are external JSON or frozen Python objects,
never functions in mutable program source. Only explicitly allowed functions'
numeric literals and arithmetic/comparison operators may change. Ties are rejected.
A running VM pins its snapshot; accepted changes affect future executions.

See [SPEC.md](SPEC.md), [ARCHITECTURE.md](ARCHITECTURE.md),
[THREAT_MODEL.md](THREAT_MODEL.md), and [docs/evidence](docs/evidence).
The original prototype is preserved byte-for-byte under `legacy/original-prototype`
and is not imported by the installed runtime.

Evidence status and acceptance verdict are maintained in the final audit and
manifest. Claims are limited to declared language inputs under the trusted-host
model. Finite oracle cases do not establish correctness on every possible input.
