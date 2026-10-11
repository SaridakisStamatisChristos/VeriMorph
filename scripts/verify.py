"""One-command local verification; commands mirror CI."""

import subprocess
import sys

commands = [
    [sys.executable, "-m", "ruff", "check", "."],
    [sys.executable, "-m", "ruff", "format", "--check", "."],
    [sys.executable, "-m", "mypy"],
    [sys.executable, "-m", "coverage", "run", "-m", "pytest", "-q"],
    [sys.executable, "-m", "coverage", "report"],
    [sys.executable, "scripts/check_legacy.py"],
    [sys.executable, "scripts/check_manifest.py"],
    [sys.executable, "-m", "build"],
    [sys.executable, "scripts/package_smoke.py"],
]
for command in commands:
    print(" ".join(command), flush=True)
    subprocess.run(command, check=True)
