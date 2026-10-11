import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from verimorph.budget import Limits
from verimorph.errors import VeriMorphError
from verimorph.kernel import Kernel
from verimorph.mutation import RNG, Proposal
from verimorph.oracle import Case, Oracle
from verimorph.provenance import Ledger, decode, load
from verimorph.replay import replay
from verimorph.snapshots import canonical, digest
from verimorph.verifier import Policy

SOURCE = "FUNC main() { RETURN 5; }"


def test_same_seed_identical_histories_and_final():
    a = Kernel(SOURCE, seed=42)
    b = Kernel(SOURCE, seed=42)
    a.search(32)
    b.search(32)
    assert a.ledger.lines == b.ledger.lines
    assert a.committed == b.committed
    assert "RETURN 12;" in a.committed.source
    c = Kernel(SOURCE, seed=43)
    c.search(32)
    assert a.ledger.lines != c.ledger.lines


@given(st.integers(0, 2**64 - 1))
def test_seeded_search_reproducible(seed):
    a = Kernel(SOURCE, seed=seed)
    b = Kernel(SOURCE, seed=seed)
    a.search(5)
    b.search(5)
    assert a.ledger.lines == b.ledger.lines


@pytest.mark.parametrize("seed", [0, 1, 42, 2**64 - 1])
def test_search_replay(tmp_path, seed):
    path = tmp_path / "run.jsonl"
    k = Kernel(SOURCE, seed=seed, ledger=Ledger(path))
    k.search(32)
    result = replay(path, k.ledger.anchor)
    assert result.committed == k.committed
    assert result.ledger.lines == k.ledger.lines


def test_manual_replay_and_rejections(tmp_path):
    path = tmp_path / "run.jsonl"
    k = Kernel(SOURCE, ledger=Ledger(path))
    k.attempt(Proposal(1, "literal", "main/0/0", 5, 6))
    k.attempt(Proposal(2, "literal", "main/0/0", 6, 4))
    k.finish()
    assert replay(path).committed == k.committed


def test_runtime_self_modification_pins_active_snapshot(tmp_path):
    source = (
        "FUNC value() { RETURN 5; } FUNC main(phase) { IF phase { EVOLVE 32; } RETURN value(); }"
    )
    oracle = Oracle((Case((0,), 12),))
    policy = Policy(mutable_functions=("value",), allow_evolve=True)
    path = tmp_path / "run.jsonl"
    k = Kernel(source, policy, oracle, ledger=Ledger(path))
    parent = k.committed
    result = k.execute((1,))
    assert result.returned == 5
    assert k.committed is not parent
    fresh = Kernel(k.committed.source, policy, oracle)
    assert fresh.execute((0,)).returned == 12
    assert replay(path).committed == k.committed


@pytest.mark.parametrize(
    "source",
    [SOURCE, "FUNC main() { WHILE 1 {} RETURN 5; }", "FUNC main() { EVOLVE 1; RETURN 5; }"],
)
def test_exhausted_replay(tmp_path, source):
    path = tmp_path / "run.jsonl"
    k = Kernel(
        source,
        policy=Policy(allow_evolve=True),
        limits=Limits(steps=15, evaluation_depth=3),
        ledger=Ledger(path),
    )
    k.search(32)
    assert replay(path).committed == k.committed


def test_altered_history_detection(tmp_path):
    path = tmp_path / "run.jsonl"
    k = Kernel(SOURCE, ledger=Ledger(path))
    k.search(5)
    original = path.read_text()
    path.write_text(original.replace('"target":12', '"target":13'))
    with pytest.raises(VeriMorphError):
        replay(path)
    # A hostile host can rehash a forged chain, but reexecution detects false decisions.
    events = [json.loads(line) for line in original.splitlines()]
    mutation = next(e for e in events if e["payload"]["kind"] == "mutation")
    mutation["payload"]["score"] = 123456
    previous = "0" * 64
    for event in events:
        event["previous"] = previous
        event["hash"] = digest({key: value for key, value in event.items() if key != "hash"})
        previous = event["hash"]
    path.write_text("".join(canonical(event) + "\n" for event in events))
    with pytest.raises(VeriMorphError, match="semantic evidence mismatch"):
        replay(path)
    with pytest.raises(VeriMorphError, match="anchor mismatch"):
        replay(path, k.ledger.anchor)


@pytest.mark.parametrize("text", ["", "{}\n", "not JSON\n", "[" * 2000, '{"event_id":NaN}'])
def test_malformed_ledger(text):
    with pytest.raises(VeriMorphError):
        decode(text)


def test_truncated_history_and_exclusive_create(tmp_path):
    path = tmp_path / "run.jsonl"
    k = Kernel(SOURCE, ledger=Ledger(path))
    k.search(2)
    path.write_text("".join(path.read_text().splitlines(True)[:-1]))
    with pytest.raises(VeriMorphError, match="seal"):
        load(path)
    with pytest.raises(FileExistsError):
        Ledger(path)


def test_rng_known_vector():
    rng = RNG(0)
    assert rng.next() == 0xE220A8397B1DCDAF
    assert rng.next() == 0x6E789E6AA1B965F4


def test_resource_and_oracle_versions_change_snapshot_identity():
    a = Kernel(SOURCE)
    b = Kernel(SOURCE, oracle=Oracle((Case(target=13),)))
    assert a.committed.content_hash == b.committed.content_hash
    assert a.committed.snapshot_id != b.committed.snapshot_id
