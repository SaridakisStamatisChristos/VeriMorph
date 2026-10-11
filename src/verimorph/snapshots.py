"""Content-addressed, immutable snapshots with separate lineage identity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .language import Program, canonical_source, parse
from .verifier import VERIFIER_VERSION


def canonical(data: object) -> str:
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def digest(data: object) -> str:
    return hashlib.sha256(canonical(data).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Snapshot:
    program: Program
    source: str
    content_hash: str
    snapshot_id: str
    parent_id: str | None
    policy_hash: str
    oracle_hash: str

    @classmethod
    def create(
        cls, program: Program, policy_hash: str, oracle_hash: str, parent: Snapshot | None = None
    ) -> Snapshot:
        source = canonical_source(program)
        # Reparse canonical source to independently enforce the serializer boundary.
        if parse(source) != program:
            from .errors import VeriMorphError

            raise VeriMorphError("snapshot", "canonical roundtrip mismatch")
        content_hash = digest({"language": "integer-1", "source": source})
        parent_id = None if parent is None else parent.snapshot_id
        identity = digest(
            {
                "content": content_hash,
                "parent": parent_id,
                "policy": policy_hash,
                "oracle": oracle_hash,
                "verifier": VERIFIER_VERSION,
            }
        )
        return cls(program, source, content_hash, identity, parent_id, policy_hash, oracle_hash)
