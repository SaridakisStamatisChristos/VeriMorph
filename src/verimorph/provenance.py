"""Bounded hash-chained JSONL evidence; trusted anchors are required for authenticity."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .errors import VeriMorphError
from .snapshots import canonical, digest

MAX_LEDGER_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 1026


class Ledger:
    def __init__(self, path: Path | None = None):
        self._lines: list[str] = []
        self._hash = "0" * 64
        self._bytes = 0
        self._file = None if path is None else path.open("x", encoding="utf-8", newline="\n")
        self._closed = False

    def append(self, payload: dict[str, Any]) -> None:
        if self._closed:
            raise VeriMorphError("provenance", "ledger closed")
        event = {"event_id": len(self._lines), "previous": self._hash, "payload": payload}
        checksum = digest(event)
        line = canonical({**event, "hash": checksum}) + "\n"
        size = len(line.encode())
        if self._bytes + size > MAX_LEDGER_BYTES or len(self._lines) >= MAX_EVENTS:
            raise VeriMorphError("provenance", "ledger capacity exhausted")
        # I/O failure precedes both evidence state and commit; never overwrite history.
        if self._file is not None:
            try:
                self._file.write(line)
                self._file.flush()
                os.fsync(self._file.fileno())
            except OSError:
                self._closed = True
                self._file.close()
                raise
        self._lines.append(line)
        self._bytes += size
        self._hash = checksum

    @property
    def lines(self) -> tuple[str, ...]:
        return tuple(self._lines)

    @property
    def anchor(self) -> str:
        return self._hash

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
        self._closed = True


def load(path: Path, expected_anchor: str | None = None) -> tuple[dict[str, Any], ...]:
    with path.open("rb") as stream:
        raw = stream.read(MAX_LEDGER_BYTES + 1)
    if len(raw) > MAX_LEDGER_BYTES:
        raise VeriMorphError("provenance", "ledger too large")
    return decode(raw.decode("utf-8"), expected_anchor)


def decode(text: str, expected_anchor: str | None = None) -> tuple[dict[str, Any], ...]:
    if len(text) > MAX_LEDGER_BYTES or len(text.encode()) > MAX_LEDGER_BYTES:
        raise VeriMorphError("provenance", "ledger too large")
    previous = "0" * 64
    events = []
    for i, line in enumerate(text.splitlines()):
        if i >= MAX_EVENTS or len(line) > 262144:
            raise VeriMorphError("provenance", "event limit")
        try:
            event = json.loads(
                line, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON"))
            )
            if (
                not isinstance(event, dict)
                or set(event) != {"event_id", "previous", "payload", "hash"}
                or type(event["event_id"]) is not int
                or event["event_id"] != i
                or event["previous"] != previous
                or not isinstance(event["payload"], dict)
            ):
                raise ValueError("event shape/sequence mismatch")
            body = {k: v for k, v in event.items() if k != "hash"}
            if digest(body) != event["hash"]:
                raise ValueError("hash mismatch")
        except (ValueError, TypeError, RecursionError) as e:
            raise VeriMorphError("provenance", f"invalid event {i}: {e}") from e
        previous = event["hash"]
        events.append(event)
    if (
        not events
        or events[0]["payload"].get("kind") != "header"
        or events[-1]["payload"].get("kind") != "end"
    ):
        raise VeriMorphError("provenance", "complete header/end seal required")
    if expected_anchor is not None and previous != expected_anchor:
        raise VeriMorphError("provenance", "trusted anchor mismatch")
    return tuple(events)
