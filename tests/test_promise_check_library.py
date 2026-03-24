import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))

from artifact_adapters import (  # noqa: E402
    load_promise_check_libraries_from_dir_v1,
    load_promise_check_library_v1,
    load_promise_touch_map_v1,
    suggest_checks_for_accepted_slice_candidate,
    validate_check_card_v1,
)


class PromiseCheckLibraryTests(unittest.TestCase):
    def _valid_check_card(self, check_id: str = "check-a") -> dict:
        return {
            "check_id": check_id,
            "statement": "Manual check statement.",
            "promise_id": "promise-test",
            "interaction_family": "family-a",
            "consistency_boundary": "boundary-a",
            "objective": "Discriminate one hypothesis.",
            "check_type": "trace",
            "required_inputs": ["input-a"],
            "procedure_steps": ["step-a"],
            "expected_signals": ["signal-a"],
            "failure_signals": ["failure-a"],
            "evidence_outputs": ["output-a"],
            "cost": "low",
            "strength": "high",
            "provenance_refs": ["ref-a"],
            "status": "accepted",
        }

    def _valid_library(self, checks: list[dict]) -> dict:
        return {
            "schema_version": "PromiseCheckLibrary.v1",
            "produced_by": "tests",
            "library_id": "library-test",
            "library_version": 1,
            "generated_at": "2026-03-24T00:00:00Z",
            "checks": checks,
        }

    def _write_library(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, indent=2) + "\n")

    def _valid_touch_map(self) -> dict:
        return {
            "schema_version": "PromiseTouchMap.v1",
            "produced_by": "tests",
            "touch_map_id": "touch-map-test",
            "promise_id": "promise-test",
            "purpose_context": "manual",
            "actors": ["user", "ui"],
            "protected_state": "state",
            "mutable_surfaces": [
                {
                    "surface_id": "surface-a",
                    "kind": "ui_state",
                    "ref": "ui.a",
                    "actor_scope": "ui",
                    "notes": "seed",
                }
            ],
            "interaction_families": [
                {
                    "family_id": "family-a",
                    "statement": "family statement",
                    "surface_ids": ["surface-a"],
                    "actor_scope": "ui",
                    "transition_refs": ["a->b"],
                }
            ],
            "consistency_boundaries": [
                {
                    "boundary_id": "boundary-a",
                    "statement": "boundary statement",
                    "representation_a": "a",
                    "representation_b": "b",
                    "settlement_horizon": "h",
                    "notes": "seed",
                }
            ],
            "pressure_axes": ["axis-a"],
            "slice_candidates": [
                {
                    "slice_id": "slice-a",
                    "interaction_family": "family-a",
                    "consistency_boundary": "boundary-a",
                    "rationale": "seed",
                    "priority": "high",
                    "confidence": 0.8,
                    "status": "accepted",
                }
            ],
            "evidence_refs": {
                "source_incident_ids": ["incident-test"],
            },
            "created_at": "2026-03-24T00:00:00Z",
            "updated_at": "2026-03-24T00:00:00Z",
        }

    def test_required_field_validation(self) -> None:
        check = self._valid_check_card()
        del check["statement"]

        errors = validate_check_card_v1(check, context="check")
        self.assertTrue(errors)
        self.assertIn("missing required keys", errors[0])

    def test_status_validation(self) -> None:
        check = self._valid_check_card()
        check["status"] = "paused"

        errors = validate_check_card_v1(check, context="check")
        self.assertTrue(any("status must be one of" in error for error in errors))

    def test_duplicate_check_id_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "library.json"
            payload = self._valid_library(
                checks=[
                    self._valid_check_card("check-dup"),
                    self._valid_check_card("check-dup"),
                ]
            )
            self._write_library(path, payload)

            with self.assertRaises(ValueError):
                load_promise_check_library_v1(path)

    def test_deterministic_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "library.json"
            payload = self._valid_library(
                checks=[
                    self._valid_check_card("check-z"),
                    self._valid_check_card("check-a"),
                ]
            )
            self._write_library(path, payload)

            loaded = load_promise_check_library_v1(path)
            self.assertEqual(["check-a", "check-z"], [check["check_id"] for check in loaded["checks"]])

    def test_slice_to_check_suggestion_behavior(self) -> None:
        touch_map = self._valid_touch_map()
        slice_candidate = touch_map["slice_candidates"][0]

        matching_accepted = self._valid_check_card("check-accepted")
        matching_accepted["strength"] = "high"
        matching_accepted["cost"] = "low"

        matching_draft = self._valid_check_card("check-draft")
        matching_draft["status"] = "draft"
        matching_draft["strength"] = "medium"
        matching_draft["cost"] = "medium"

        non_matching = self._valid_check_card("check-other-boundary")
        non_matching["consistency_boundary"] = "boundary-other"

        deprecated = self._valid_check_card("check-deprecated")
        deprecated["status"] = "deprecated"

        library = self._valid_library(
            checks=[
                non_matching,
                matching_draft,
                deprecated,
                matching_accepted,
            ]
        )

        suggestions = suggest_checks_for_accepted_slice_candidate(touch_map, slice_candidate, library)
        self.assertEqual(["check-accepted", "check-draft"], [item["check_id"] for item in suggestions])
        self.assertTrue(all(item["manual_only"] is True for item in suggestions))

    def test_example_artifact_loading(self) -> None:
        libraries_dir = ROOT / "diagnostics/memory/promise_check_libraries"
        libraries = load_promise_check_libraries_from_dir_v1(libraries_dir)

        self.assertEqual(1, len(libraries))
        checks = libraries[0]["checks"]
        promise_ids = {check["promise_id"] for check in checks}
        self.assertIn("promise-repotrace-queue-preview-reflects-selected-collection", promise_ids)
        self.assertIn("promise-nutriplanner-collapse-boundary-lockstep", promise_ids)

        touch_map_path = (
            ROOT
            / "diagnostics/memory/promise_touch_maps"
            / "promise-repotrace-queue-preview-reflects-selected-collection.touch_map.json"
        )
        touch_map = load_promise_touch_map_v1(touch_map_path)
        accepted_slice = next(
            candidate
            for candidate in touch_map["slice_candidates"]
            if candidate["status"] == "accepted"
        )

        suggestions = suggest_checks_for_accepted_slice_candidate(touch_map, accepted_slice, libraries[0])
        self.assertTrue(any(item["check_id"] == "check-repotrace-queue-key-agreement-trace-v1" for item in suggestions))


if __name__ == "__main__":
    unittest.main()
