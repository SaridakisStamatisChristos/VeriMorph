"""Compare preserved byte hashes against the independent historical probe record."""

import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
expected = json.loads((root / "docs/evidence/legacy-reproduction.json").read_text())[
    "original_sha256"
]
actual = {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in (root / "legacy/original-prototype").iterdir()
    if p.is_file()
}
assert actual == expected, (actual, expected)
print("Legacy byte hashes verified: 5 originals")
