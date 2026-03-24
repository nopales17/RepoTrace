import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))

from artifact_adapters import load_promise_registry_v1, validate_promise_card  # noqa: E402


class PromiseRegistryTests(unittest.TestCase):
    def _valid_card(self, promise_id: str = "promise-test") -> dict:
        return {
            "promise_id": promise_id,
            "statement": "Selection should drive preview deterministically.",
            "why_it_exists": "User-visible correctness contract.",
            "actors": ["user", "ui", "rule engine"],
            "assets_or_rights": ["correct preview"],
            "protected_state": "selected key and rendered count stay aligned",
            "interaction_families": ["selection", "preview render"],
            "consistency_boundaries": ["ui/runtime/rule key agreement"],
            "settlement_horizon": "single interaction to first render",
            "representations": ["incident", "retrieval", "witnesses"],
            "admin_or_external_surfaces": ["diagnostics"],
            "stress_axes": ["lookup miss"],
            "evidence_refs": {
                "source_incident_ids": ["incident-test"],
                "retrieval_refs": ["diagnostics/retrieval_results/incident-test.json"],
                "witness_refs": ["diagnostics/evidence/witness_sets/incident-test.witness_set.json"],
                "fixture_refs": ["eval/fixtures/repotrace-current-incident.yaml"],
                "verifier_refs": ["tests"],
            },
            "priority": "high",
            "confidence": 0.8,
            "status": "accepted",
        }

    def _write_registry(self, path: Path, promises: list[dict]) -> None:
        payload = {
            "schema_version": "PromiseRegistry.v1",
            "produced_by": "tests",
            "registry_version": 1,
            "generated_at": "2026-03-24T00:00:00Z",
            "promises": promises,
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")

    def test_promise_card_required_field_validation(self) -> None:
        card = self._valid_card()
        del card["statement"]
        errors = validate_promise_card(card, context="card")
        self.assertTrue(errors)
        self.assertIn("missing required keys", errors[0])

    def test_registry_loading_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "promise_registry.json"
            self._write_registry(
                path,
                promises=[
                    self._valid_card("promise-z"),
                    self._valid_card("promise-a"),
                ],
            )

            loaded = load_promise_registry_v1(path)
            self.assertEqual(
                ["promise-a", "promise-z"],
                [card["promise_id"] for card in loaded["promises"]],
            )

    def test_registry_rejects_duplicate_promise_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "promise_registry.json"
            self._write_registry(
                path,
                promises=[
                    self._valid_card("promise-dup"),
                    self._valid_card("promise-dup"),
                ],
            )

            with self.assertRaises(ValueError):
                load_promise_registry_v1(path)

    def test_registry_rejects_invalid_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "promise_registry.json"
            card = self._valid_card("promise-status")
            card["status"] = "deprecated"
            self._write_registry(path, promises=[card])

            with self.assertRaises(ValueError):
                load_promise_registry_v1(path)

    def test_example_fixture_promises_load(self) -> None:
        registry_path = ROOT / "diagnostics/memory/promise_registry.json"
        registry = load_promise_registry_v1(registry_path)

        promise_ids = {card["promise_id"] for card in registry["promises"]}
        self.assertIn("promise-repotrace-queue-preview-reflects-selected-collection", promise_ids)
        self.assertIn("promise-nutriplanner-collapse-boundary-lockstep", promise_ids)

        all_fixture_refs = {
            fixture_ref
            for card in registry["promises"]
            for fixture_ref in card["evidence_refs"].get("fixture_refs", [])
        }
        self.assertIn("eval/fixtures/repotrace-current-incident.yaml", all_fixture_refs)
        self.assertIn("eval/fixtures/nutriplanner-collapse-case.yaml", all_fixture_refs)


if __name__ == "__main__":
    unittest.main()
