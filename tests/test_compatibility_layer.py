import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))

from artifact_adapters import (  # noqa: E402
    adapt_legacy_retrieval_to_v1,
    parse_legacy_incident_markdown,
    read_durable_memory_from_legacy_claims,
)


class CompatibilityAdapterTests(unittest.TestCase):
    def test_repotrace_legacy_retrieval_adapts_to_v1(self) -> None:
        legacy_path = ROOT / "diagnostics/retrieval_results/incident-20260312-220604.json"
        payload = json.loads(legacy_path.read_text())

        attempt = adapt_legacy_retrieval_to_v1(
            payload,
            produced_by="tests",
            source_path=str(legacy_path),
            run_id="20260324T000000Z",
        )

        self.assertEqual("RetrievalAttempt.v1", attempt["schema_version"])
        self.assertEqual("incident-20260312-220604", attempt["incident_id"])
        self.assertEqual("motif_non_match", attempt["verdict"])
        self.assertIn("retrieval_attempt_id", attempt)
        self.assertTrue(attempt.get("next_discriminating_check") or attempt.get("gap_description"))
        self.assertTrue(isinstance(attempt.get("evidence_links"), list) and attempt["evidence_links"])

    def _read_fixture(self, path: Path) -> dict:
        data: dict[str, str | list[str]] = {}
        reference_commits: list[str] = []
        in_reference_commits = False

        for raw_line in path.read_text().splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if in_reference_commits and stripped.startswith("-"):
                reference_commits.append(stripped.split("-", 1)[1].strip())
                continue

            if raw_line.startswith(" "):
                continue

            if ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key == "reference_commits":
                    in_reference_commits = True
                    continue
                in_reference_commits = False
                data[key] = value

        data["reference_commits"] = reference_commits
        return data

    def test_nutriplanner_lineage_fixture_shows_interpretation_drift(self) -> None:
        fixture_path = ROOT / "eval/fixtures/nutriplanner-collapse-case.yaml"
        fixture = self._read_fixture(fixture_path)

        source_repo_path = Path(str(fixture.get("source_repo_path", "")))
        if not source_repo_path.exists():
            self.skipTest(f"fixture source repo not present: {source_repo_path}")

        retrieval_artifact_path = str(fixture["retrieval_artifact_path"])
        incident_evidence_path = str(fixture["incident_evidence_path"])
        commits = fixture["reference_commits"]
        self.assertEqual(2, len(commits))

        def git_show(commit: str, artifact_path: str) -> str:
            return subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(source_repo_path),
                    "show",
                    f"{commit}:{artifact_path}",
                ],
                text=True,
            )

        retrieval_old = json.loads(git_show(commits[0], retrieval_artifact_path))
        retrieval_new = json.loads(git_show(commits[1], retrieval_artifact_path))

        attempt_old = adapt_legacy_retrieval_to_v1(
            retrieval_old,
            produced_by="tests",
            source_path=f"{commits[0]}:{retrieval_artifact_path}",
            run_id="old",
        )
        attempt_new = adapt_legacy_retrieval_to_v1(
            retrieval_new,
            produced_by="tests",
            source_path=f"{commits[1]}:{retrieval_artifact_path}",
            run_id="new",
        )

        self.assertEqual(attempt_old["incident_id"], attempt_new["incident_id"])
        self.assertNotEqual(attempt_old["verdict"], attempt_new["verdict"])

        evidence_old = json.loads(git_show(commits[0], incident_evidence_path))
        evidence_new = json.loads(git_show(commits[1], incident_evidence_path))
        self.assertEqual(evidence_old, evidence_new)

    def test_forward_only_validator_rejects_missing_required_fields(self) -> None:
        bad_attempt = {
            "schema_version": "RetrievalAttempt.v1",
            "produced_by": "tests",
            "incident_id": "incident-test"
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad_attempt.json"
            path.write_text(json.dumps(bad_attempt) + "\n")

            result = subprocess.run(
                [sys.executable, "scripts/validate_artifacts.py", str(path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("missing required keys", result.stdout)

    def test_legacy_claims_reader_produces_concrete_provenance_fields(self) -> None:
        legacy_claims_path = ROOT / "diagnostics/claims.json"
        durable_memory = read_durable_memory_from_legacy_claims(legacy_claims_path)

        self.assertEqual("DurableMemory.v1", durable_memory["schema_version"])
        self.assertTrue(isinstance(durable_memory.get("claims"), list))

        first_claim = durable_memory["claims"][0]
        provenance = first_claim["provenance"]
        self.assertEqual(
            {"source_incident_ids", "retrieval_attempt_ids", "witness_ids", "commit_refs", "verifier_refs"},
            set(provenance.keys()),
        )

    def test_legacy_incident_markdown_maps_to_incident_view(self) -> None:
        markdown_path = ROOT / "diagnostics/incidents/incident-20260312-220604.md"
        incident_view = parse_legacy_incident_markdown(markdown_path)

        self.assertEqual("IncidentView.v1", incident_view["schema_version"])
        self.assertEqual("incident-20260312-220604", incident_view["incident_id"])
        self.assertIn("queue preview should show 4 tracks", incident_view["expected_behavior"])


if __name__ == "__main__":
    unittest.main()
