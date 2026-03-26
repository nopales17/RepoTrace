import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))

from artifact_adapters import (  # noqa: E402
    derive_promise_card_stubs_from_accepted_candidates,
    load_promise_derivation_worksheet_v1,
    load_promise_derivation_worksheets_from_dir_v1,
    validate_promise_card,
    validate_promise_derivation_worksheet_v1,
)


class PromiseDerivationWorksheetTests(unittest.TestCase):
    def _valid_worksheet(self, worksheet_id: str = "worksheet-test") -> dict:
        return {
            "schema_version": "PromiseDerivationWorksheet.v1",
            "produced_by": "tests",
            "worksheet_id": worksheet_id,
            "system_name": "RepoTrace",
            "purpose": "Derive manual promise candidates before scanning.",
            "actors": ["user", "ui", "runtime"],
            "assets_or_rights": ["correct preview count"],
            "transition_families": ["queue lookup", "preview render"],
            "representations": ["incident", "witness set"],
            "consistency_boundaries": ["ui/runtime key agreement", "preview count agreement"],
            "settlement_horizons": ["selection to first preview render"],
            "admin_or_external_surfaces": ["diagnostics export"],
            "candidate_promises": [
                {
                    "candidate_id": "candidate-a",
                    "statement": "Queue lookup resolves the selected key.",
                    "actor_scope": "ui + runtime",
                    "protected_state": "selected key agreement across ui/runtime",
                    "interaction_families": ["queue lookup"],
                    "consistency_boundaries": ["ui/runtime key agreement"],
                    "rationale": "Incident shows lookup divergence.",
                    "priority": "high",
                    "confidence": 0.85,
                    "status": "accepted",
                },
                {
                    "candidate_id": "candidate-b",
                    "statement": "Preview count projects resolved queue count.",
                    "actor_scope": "runtime + preview",
                    "protected_state": "rendered count equals resolved queue count",
                    "interaction_families": ["preview render"],
                    "consistency_boundaries": ["preview count agreement"],
                    "rationale": "Follow-up after lookup agreement.",
                    "priority": "medium",
                    "confidence": 0.62,
                    "status": "deferred",
                },
            ],
            "open_questions": ["Is lookup miss isolated to one collection key?"],
            "evidence_refs": {
                "source_incident_ids": ["incident-test"],
                "retrieval_refs": ["diagnostics/retrieval_results/incident-test.json"],
                "witness_refs": ["diagnostics/evidence/witness_sets/incident-test.witness_set.json"],
                "fixture_refs": ["eval/fixtures/repotrace-current-incident.yaml"],
                "verifier_refs": ["tests"],
            },
            "status": "draft",
            "created_at": "2026-03-24T00:00:00Z",
            "updated_at": "2026-03-24T00:00:00Z",
        }

    def _write_worksheet(self, path: Path, worksheet: dict) -> None:
        path.write_text(json.dumps(worksheet, indent=2) + "\n")

    def test_required_field_validation(self) -> None:
        worksheet = self._valid_worksheet()
        del worksheet["system_name"]

        errors = validate_promise_derivation_worksheet_v1(worksheet, context="worksheet")
        self.assertTrue(errors)
        self.assertIn("missing required keys", errors[0])

    def test_rejects_duplicate_candidate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "worksheet.json"
            worksheet = self._valid_worksheet()
            worksheet["candidate_promises"].append(dict(worksheet["candidate_promises"][0]))
            self._write_worksheet(path, worksheet)

            with self.assertRaises(ValueError):
                load_promise_derivation_worksheet_v1(path)

    def test_rejects_candidate_references_to_missing_family_or_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "worksheet.json"
            worksheet = self._valid_worksheet()
            worksheet["candidate_promises"][0]["interaction_families"] = ["family-missing"]
            worksheet["candidate_promises"][0]["consistency_boundaries"] = ["boundary-missing"]
            self._write_worksheet(path, worksheet)

            with self.assertRaises(ValueError):
                load_promise_derivation_worksheet_v1(path)

    def test_deterministic_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "worksheet.json"
            worksheet = self._valid_worksheet()
            worksheet["candidate_promises"] = [
                dict(worksheet["candidate_promises"][1]),
                dict(worksheet["candidate_promises"][0]),
            ]
            self._write_worksheet(path, worksheet)

            loaded = load_promise_derivation_worksheet_v1(path)
            self.assertEqual(
                ["candidate-a", "candidate-b"],
                [candidate["candidate_id"] for candidate in loaded["candidate_promises"]],
            )

    def test_accepted_candidate_derives_promise_card_stub(self) -> None:
        worksheet = self._valid_worksheet()

        suggestions = derive_promise_card_stubs_from_accepted_candidates(
            worksheet,
            produced_by="tests",
        )

        self.assertEqual(1, len(suggestions))
        suggestion = suggestions[0]
        self.assertEqual("candidate-a", suggestion["source_candidate_id"])
        self.assertEqual("hypothesized", suggestion["status"])
        self.assertEqual(["queue lookup"], suggestion["interaction_families"])

        errors = validate_promise_card(suggestion, context="stub")
        self.assertEqual([], errors)

    def test_example_worksheets_load(self) -> None:
        worksheets_dir = ROOT / "diagnostics/memory/promise_derivation_worksheets"
        loaded = load_promise_derivation_worksheets_from_dir_v1(worksheets_dir)

        self.assertEqual(2, len(loaded))
        worksheet_ids = {worksheet["worksheet_id"] for worksheet in loaded}
        self.assertIn("worksheet-repotrace-queue-preview-v1", worksheet_ids)
        self.assertIn("worksheet-nutriplanner-collapse-lockstep-v1", worksheet_ids)


if __name__ == "__main__":
    unittest.main()
