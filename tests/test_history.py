import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_all_historical_failure_modes_reproduced():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/reproduce_legacy.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    result = json.loads(proc.stdout)
    assert result["nontransactional"]["live_source_changed"]
    assert result["fitness_tampering"]["baseline"] == [100, True]
    assert result["fitness_tampering"]["candidate"] == [101, True]
    assert result["fitness_tampering"]["target_behavior_unchanged"]
    assert result["recursive_evaluation"]["first_parent_steps"] == [2] * 8
    assert result["recursive_evaluation"]["score_calls"] == 15
    assert result["demo_actual_edit"]["line2_after"] == "x = x + 1"
    assert result["advisory_analysis"]["compiled_despite_warning"]
    assert result["hmac"]["calculation_logged"]
    assert not result["hmac"]["trusted_expected_mac_input"]
    expected = json.loads((ROOT / "docs/evidence/legacy-reproduction.json").read_text())
    assert result == expected
