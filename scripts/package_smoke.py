"""Install wheel into a fresh venv; invoke CLI outside the source checkout."""

import json
import os
import subprocess
import tempfile
import venv
from pathlib import Path

root = Path(__file__).resolve().parents[1]
wheels = list((root / "dist").glob("*.whl"))
assert len(wheels) == 1, wheels
with tempfile.TemporaryDirectory() as temp:
    work = Path(temp)
    env_dir = work / "venv"
    venv.EnvBuilder(with_pip=True).create(env_dir)
    bindir = env_dir / ("Scripts" if os.name == "nt" else "bin")
    py = bindir / ("python.exe" if os.name == "nt" else "python")
    cli = bindir / ("verimorph.exe" if os.name == "nt" else "verimorph")
    subprocess.run(
        [str(py), "-m", "pip", "install", "--no-deps", str(wheels[0])], check=True, cwd=work
    )
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    commands = [
        ["--help"],
        ["check", str(root / "examples/evolve.vm")],
        ["run", str(root / "examples/basic.vm")],
        ["evolve", str(root / "examples/evolve.vm"), "--ledger", str(work / "run.jsonl")],
        ["replay", str(work / "run.jsonl")],
        ["inspect", str(root / "examples/evolve.vm")],
    ]
    results = []
    for args in commands:
        result = subprocess.run(
            [str(cli), *args], cwd=work, env=env, check=True, capture_output=True, text=True
        )
        results.append({"args": args, "exit": result.returncode, "output": result.stdout.strip()})
    assert not any("legacy" in str(p) for p in (env_dir).rglob("interpreter_secure.py"))
    print(json.dumps({"package_smoke": "verified", "commands": results}, indent=2))
