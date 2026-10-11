# Contributing

Obtain permission under LICENSE before using or redistributing the code.
For authorized development, create a virtual environment and install:

```sh
pip install --require-hashes -r requirements-dev.lock
pip install --no-build-isolation --no-deps -e .
python scripts/verify.py
```

The runtime has zero third-party dependencies. Development dependencies are
pinned with hashes. Update the lock deliberately with `uv pip compile pyproject.toml
--extra dev --universal --generate-hashes -o requirements-dev.lock`, then rerun dependency audit.

Changes to parser, integer semantics, policy, oracle, RNG, or ledger schema need
version review and replay tests. Preserve every original byte under legacy/.
Add an independent property or adversarial reproducer for fixes affecting
atomicity, resource control, or trust boundaries. Do not lower gates for examples.
The kernel is single-owner and single-threaded. Do not introduce unreviewed
concurrent commit paths. Record failures and repairs in docs/evidence.
