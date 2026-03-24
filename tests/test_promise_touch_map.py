import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))

from artifact_adapters import (  # noqa: E402
    derive_manual_task_stubs_from_touch_map,
    load_promise_touch_map_v1,
    load_promise_touch_maps_from_dir_v1,
    validate_promise_touch_map_v1,
)


class PromiseTouchMapTests(unittest.TestCase):
    def _valid_touch_map(self, touch_map_id: str = "touch-map-test") -> dict:
        return {
            "schema_version": "PromiseTouchMap.v1",
            "produced_by": "tests",
            "touch_map_id": touch_map_id,
            "promise_id": "promise-test",
            "purpose_context": {
                "fixture_ref": "eval/fixtures/test.yaml",
                "objective": "decompose promise"
            },
            "actors": ["user", "ui", "runtime"],
            "protected_state": "state remains consistent",
            "mutable_surfaces": [
                {
                    "surface_id": "surface-ui",
                    "kind": "ui_state",
                    "ref": "ui.selected",
                    "actor_scope": "user + ui",
                    "notes": "selection source"
                },
                {
                    "surface_id": "surface-runtime",
                    "kind": "runtime_lookup",
                    "ref": "runtime.lookup",
                    "actor_scope": "runtime",
                    "notes": "lookup sink"
                }
            ],
            "interaction_families": [
                {
                    "family_id": "family-a",
                    "statement": "resolve selection into runtime key",
                    "surface_ids": ["surface-ui", "surface-runtime"],
                    "actor_scope": "ui + runtime",
                    "transition_refs": ["select -> lookup"]
                }
            ],
            "consistency_boundaries": [
                {
                    "boundary_id": "boundary-a",
                    "statement": "ui key equals runtime key",
                    "representation_a": "ui.selected",
                    "representation_b": "runtime.lookupKey",
                    "settlement_horizon": "selection to first lookup",
                    "notes": "primary key boundary"
                }
            ],
            "pressure_axes": ["lookup miss"],
            "slice_candidates": [
                {
                    "slice_id": "slice-a",
                    "interaction_family": "family-a",
                    "consistency_boundary": "boundary-a",
                    "rationale": "directly checks mismatch source",
                    "priority": "high",
                    "confidence": 0.8,
                    "status": "accepted"
                },
                {
                    "slice_id": "slice-b",
                    "interaction_family": "family-a",
                    "consistency_boundary": "boundary-a",
                    "rationale": "follow-up only",
                    "priority": "medium",
                    "confidence": 0.5,
                    "status": "proposed"
                }
            ],
            "evidence_refs": {
                "source_incident_ids": ["incident-test"]
            },
            "created_at": "2026-03-24T00:00:00Z",
            "updated_at": "2026-03-24T00:00:00Z"
        }

    def _write_touch_map(self, path: Path, touch_map: dict) -> None:
        path.write_text(json.dumps(touch_map, indent=2) + "\n")

    def test_required_field_validation(self) -> None:
        touch_map = self._valid_touch_map()
        del touch_map["promise_id"]

        errors = validate_promise_touch_map_v1(touch_map, context="touch_map")
        self.assertTrue(errors)
        self.assertIn("missing required keys", errors[0])

    def test_rejects_duplicate_family_boundary_and_slice_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "touch_map.json"

            touch_map = self._valid_touch_map()
            touch_map["interaction_families"].append(dict(touch_map["interaction_families"][0]))
            touch_map["consistency_boundaries"].append(dict(touch_map["consistency_boundaries"][0]))
            touch_map["slice_candidates"].append(dict(touch_map["slice_candidates"][0]))
            self._write_touch_map(path, touch_map)

            with self.assertRaises(ValueError):
                load_promise_touch_map_v1(path)

    def test_rejects_slice_reference_to_missing_family_or_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "touch_map.json"

            touch_map = self._valid_touch_map()
            touch_map["slice_candidates"][0]["interaction_family"] = "family-missing"
            touch_map["slice_candidates"][0]["consistency_boundary"] = "boundary-missing"
            self._write_touch_map(path, touch_map)

            with self.assertRaises(ValueError):
                load_promise_touch_map_v1(path)

    def test_deterministic_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "touch_map.json"

            touch_map = self._valid_touch_map()
            touch_map["mutable_surfaces"] = [
                {
                    "surface_id": "surface-z",
                    "kind": "runtime_lookup",
                    "ref": "runtime.z",
                    "actor_scope": "runtime",
                    "notes": "z"
                },
                {
                    "surface_id": "surface-a",
                    "kind": "ui_state",
                    "ref": "ui.a",
                    "actor_scope": "ui",
                    "notes": "a"
                }
            ]
            touch_map["interaction_families"] = [
                {
                    "family_id": "family-z",
                    "statement": "z",
                    "surface_ids": ["surface-z"],
                    "actor_scope": "runtime",
                    "transition_refs": ["z"]
                },
                {
                    "family_id": "family-a",
                    "statement": "a",
                    "surface_ids": ["surface-a"],
                    "actor_scope": "ui",
                    "transition_refs": ["a"]
                }
            ]
            touch_map["consistency_boundaries"] = [
                {
                    "boundary_id": "boundary-z",
                    "statement": "z",
                    "representation_a": "a",
                    "representation_b": "b",
                    "settlement_horizon": "z",
                    "notes": "z"
                },
                {
                    "boundary_id": "boundary-a",
                    "statement": "a",
                    "representation_a": "a",
                    "representation_b": "b",
                    "settlement_horizon": "a",
                    "notes": "a"
                }
            ]
            touch_map["slice_candidates"] = [
                {
                    "slice_id": "slice-z",
                    "interaction_family": "family-z",
                    "consistency_boundary": "boundary-z",
                    "rationale": "z",
                    "priority": "low",
                    "confidence": 0.4,
                    "status": "deferred"
                },
                {
                    "slice_id": "slice-a",
                    "interaction_family": "family-a",
                    "consistency_boundary": "boundary-a",
                    "rationale": "a",
                    "priority": "high",
                    "confidence": 0.9,
                    "status": "accepted"
                }
            ]
            self._write_touch_map(path, touch_map)

            loaded = load_promise_touch_map_v1(path)
            self.assertEqual(["surface-a", "surface-z"], [x["surface_id"] for x in loaded["mutable_surfaces"]])
            self.assertEqual(["family-a", "family-z"], [x["family_id"] for x in loaded["interaction_families"]])
            self.assertEqual(["boundary-a", "boundary-z"], [x["boundary_id"] for x in loaded["consistency_boundaries"]])
            self.assertEqual(["slice-a", "slice-z"], [x["slice_id"] for x in loaded["slice_candidates"]])

    def test_accepted_slice_derives_manual_task_stub(self) -> None:
        touch_map = self._valid_touch_map()

        stubs = derive_manual_task_stubs_from_touch_map(
            touch_map,
            produced_by="tests",
            assigned_frame_id="frame-manual",
            created_at="2026-03-24T12:00:00Z",
        )

        self.assertEqual(1, len(stubs))
        stub = stubs[0]
        self.assertEqual("PromiseTraversalTask.v1", stub["schema_version"])
        self.assertEqual("promise-test", stub["promise_id"])
        self.assertEqual("queued", stub["status"])
        self.assertEqual("frame-manual", stub["assigned_frame_id"])
        self.assertEqual("slice-a", stub["source_slice_id"])
        self.assertEqual("resolve selection into runtime key", stub["interaction_family"])
        self.assertEqual("ui key equals runtime key", stub["consistency_boundary"])

    def test_example_artifacts_load(self) -> None:
        touch_maps_dir = ROOT / "diagnostics/memory/promise_touch_maps"
        loaded = load_promise_touch_maps_from_dir_v1(touch_maps_dir)

        self.assertEqual(2, len(loaded))
        promise_ids = {touch_map["promise_id"] for touch_map in loaded}
        self.assertIn("promise-repotrace-queue-preview-reflects-selected-collection", promise_ids)
        self.assertIn("promise-nutriplanner-collapse-boundary-lockstep", promise_ids)


if __name__ == "__main__":
    unittest.main()
