import json
from pathlib import Path

import pytest

from verimorph.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_cli_commands_and_replay(tmp_path, capsys):
    source = ROOT / "examples/evolve.vm"
    assert main(["check", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"]
    assert main(["inspect", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["nodes"]
    path = tmp_path / "run.jsonl"
    output = tmp_path / "final.vm"
    assert (
        main(
            ["evolve", str(source), "--ledger", str(path), "--output", str(output), "--seed", "42"]
        )
        == 0
    )
    end = json.loads(capsys.readouterr().out)
    assert end["score"] == 0 and output.exists()
    assert main(["replay", str(path), "--anchor", end["anchor"]]) == 0
    assert json.loads(capsys.readouterr().out)["replay"] == "verified"
    assert main(["history", str(path)]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 35
    assert main(["diff", str(source), str(output)]) == 0
    assert "+FUNC main() { RETURN 12;" in capsys.readouterr().out
    assert main(["run", str(ROOT / "examples/basic.vm")]) == 0
    assert json.loads(capsys.readouterr().out)["output"] == [12]


def test_cli_runtime_self_modify_and_recursive_denial(tmp_path, capsys):
    assert (
        main(
            [
                "run",
                str(ROOT / "examples/self_modify.vm"),
                "--config",
                str(ROOT / "examples/self_modify.json"),
                "--arg",
                "1",
                "--ledger",
                str(tmp_path / "self.jsonl"),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["returned"] == 5
    assert main(["replay", str(tmp_path / "self.jsonl")]) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "evolve",
                str(ROOT / "examples/recursive_evolve.vm"),
                "--config",
                str(ROOT / "examples/recursive_evolve.json"),
                "--ledger",
                str(tmp_path / "nested.jsonl"),
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["status"] == "exhausted"


@pytest.mark.parametrize(
    "args",
    [
        ["check", "/does-not-exist"],
        ["evolve", "examples/evolve.vm", "--seed", "-1"],
        ["evolve", "examples/evolve.vm", "--iterations", "-1"],
        ["run", "examples/basic.vm", "--steps", "0"],
        ["run", "examples/basic.vm", "--arg", "1"],
        ["evolve", "examples/evolve.vm", "--target", str(2**64)],
    ],
)
def test_cli_failure_exit(args, capsys):
    assert main(args) == 2
    assert capsys.readouterr().err


def test_cli_existing_files_never_overwritten(tmp_path):
    path = tmp_path / "existing.jsonl"
    path.write_text("precious")
    assert main(["evolve", "examples/evolve.vm", "--ledger", str(path)]) == 2
    assert path.read_text() == "precious"


def test_cli_config_malformed(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{}")
    assert main(["check", "examples/evolve.vm", "--config", str(path)]) == 2


def test_help():
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
