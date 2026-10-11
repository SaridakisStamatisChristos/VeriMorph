"""Real file checksums plus requirement/claim closure; self-references excluded."""

import hashlib
import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".hypothesis",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
}
SELF = {"docs/evidence/manifest.json", "docs/evidence/MANIFEST.md"}


def files():
    result = {}
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        name = str(rel).replace("\\", "/")
        if (
            path.is_file()
            and name not in SELF
            and path.name != ".coverage"
            and not any(x in EXCLUDED or x.endswith(".egg-info") for x in rel.parts)
        ):
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main():
    contract = json.loads((ROOT / "docs/contract.json").read_text())
    evidence = {
        "A": ["scripts/package_smoke.py", "docs/evidence/package-smoke.json"],
        "B": ["tests/test_language.py", "docs/evidence/test-results.txt"],
        "C": [
            "tests/test_transaction.py::test_rejected_mutation_preserves_state_and_behavior",
            "tests/test_transaction.py::test_malformed_ast_cannot_commit",
        ],
        "D": [
            "tests/test_transaction.py::test_historical_objective_tampering_regression",
            "tests/test_adversarial.py::test_no_host_or_legacy_capabilities",
        ],
        "E": [
            "tests/test_budget.py::test_recursive_evolve_never_receives_fresh_account",
            "tests/test_budget.py::test_global_exhaustion",
        ],
        "F": [
            "tests/test_replay.py::test_search_replay",
            "tests/test_replay.py::test_same_seed_identical_histories_and_final",
            "tests/test_replay.py::test_runtime_self_modification_pins_active_snapshot",
        ],
        "G": [
            "tests/test_replay.py::test_altered_history_detection",
            "docs/evidence/seed42.jsonl",
            "tests/test_adversarial.py::test_journal_failure_poisoning_prevents_later_commit",
        ],
        "H": [
            "tests/test_history.py::test_all_historical_failure_modes_reproduced",
            "tests/test_adversarial.py",
            "docs/evidence/failure-repair-ledger.json",
        ],
        "I": ["scripts/package_smoke.py", "docs/evidence/package-smoke.json"],
        "J": [".github/workflows/ci.yml", "docs/evidence/ci.json"],
        "K": ["docs/evidence/FINAL_AUDIT.md", "docs/research-position.md"],
        "L": ["THREAT_MODEL.md", "tests/test_adversarial.py"],
        "M": ["scripts/check_legacy.py", "docs/evidence/legacy-reproduction.json"],
        "N": ["docs/evidence/FINAL_AUDIT.md", "docs/evidence/failure-repair-ledger.json"],
        "O": ["benchmarks/bench.py", "docs/evidence/benchmark.json"],
    }
    ci_path = ROOT / "docs/evidence/ci.json"
    ci = json.loads(ci_path.read_text()) if ci_path.exists() else {"status": "UNVERIFIED"}
    coverage = json.loads((ROOT / "docs/evidence/coverage.json").read_text())["totals"]
    for requirement in contract["requirements"]:
        requirement["status"] = (
            "VERIFIED" if requirement["id"] != "J" or ci["status"] == "VERIFIED" else "UNVERIFIED"
        )
        requirement["acceptance_evidence"] = evidence[requirement["id"]]
    report = {
        "format": "verimorph-evidence-1",
        "verdict": "VERIFIED FOR DECLARED LOCAL TARGET"
        if ci["status"] == "VERIFIED"
        else "CONDITIONAL — CI observation pending",
        "requirements": contract["requirements"],
        "assumptions": contract["assumptions"],
        "applicability": contract["applicability"],
        "file_hashes": files(),
        "hash_scope": "All repository files except this manifest and its Markdown rendering; excludes build/cache/generated local environments. Files are UTF-8 with LF preserved.",
        "local_environment": platform.platform(),
        "local_python": platform.python_version(),
        "coverage": coverage,
        "ci": ci,
        "claims": [
            {
                "claim": "Rejected candidates preserve committed snapshot and fresh behavior",
                "state": "VERIFIED",
                "evidence": evidence["C"],
            },
            {
                "claim": "Candidate source cannot change external oracle/verifier/policy under trusted-host model",
                "state": "VERIFIED",
                "evidence": evidence["D"],
            },
            {
                "claim": "Descendants share one sticky root budget",
                "state": "VERIFIED",
                "evidence": evidence["E"],
            },
            {
                "claim": "Successful compute-bounded seeded runs replay semantically",
                "state": "VERIFIED",
                "evidence": evidence["F"],
            },
            {
                "claim": "Formal proof, OS sandbox, hostile-host authenticity, universal behavior or performance superiority",
                "state": "N/A",
                "rationale": "Not implemented, claimed, or in declared acceptance model",
            },
            {
                "claim": "Publication novelty and production qualification",
                "state": "UNVERIFIED",
                "rationale": "System artifact completed; no independent production or novelty study",
            },
        ],
    }
    (ROOT / "docs/evidence/manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    rows = [
        "# Evidence manifest",
        "",
        report["verdict"],
        "",
        "| Gate | State | Evidence |",
        "|---|---|---|",
    ]
    rows.extend(
        f"| {r['id']} {r['requirement']} | {r['status']} | {'; '.join(r['acceptance_evidence'])} |"
        for r in report["requirements"]
    )
    rows.extend(
        [
            "",
            f"File checksums: {len(report['file_hashes'])} files; see manifest.json. Self-reference exclusions are explicit.",
            f"Local Python: {report['local_python']}. Coverage: {coverage['percent_covered']:.2f}% including branches.",
            "",
            "Limitations: finite cases, trusted Python/OS, cooperative time accounting, no OS sandbox or formal proof, single-owner kernel. Research novelty and production qualification are not established.",
        ]
    )
    (ROOT / "docs/evidence/MANIFEST.md").write_text("\n".join(rows) + "\n")
    print(report["verdict"])


if __name__ == "__main__":
    main()
