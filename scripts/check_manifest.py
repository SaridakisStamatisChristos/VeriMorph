"""Verify checked-in evidence hashes without trusting their generating transform."""

import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "docs/evidence/manifest.json").read_text())
for name, expected in manifest["file_hashes"].items():
    path = root / name
    assert path.is_file(), name
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    assert actual == expected, (name, actual, expected)
print(f"Evidence checksums verified: {len(manifest['file_hashes'])} files")
