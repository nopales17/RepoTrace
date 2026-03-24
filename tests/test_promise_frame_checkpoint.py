import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))

from artifact_adapters import (  # noqa: E402
    load_promise_frame_checkpoint_v1,
    load_promise_frames_for_incident_v1,
    validate_promise_frame_checkpoint,
)


class PromiseFrameCheckpointTests(unittest.TestCase):
    def _valid_checkpoint(self, frame_id: str = "frame-test", incident_id: str = "incident-test") -> dict:
        return {
            "schema_version": "PromiseFrameCheckpoint.v1",
            "produced_by": "tests",
            "frame_id": frame_id,
            "incident_id": incident_id,
            "promise_id": "promise-test",
            "interaction_family": "queue lookup",
            "consistency_boundary": "screen/runtime/rule key agreement",
            "focus_statement": "Rule lookup misses under aligned selection.",
            "violation_shape": "lookup_miss_under_aligned_selection",
            "touchpoints_remaining": ["queue-rule lookup", "lookup-key normalization"],
            "pressure_axes_remaining": ["lookup miss"],
            "witness_ids": {
                "support": [f"{incident_id}:missing_event:0001"],
                "pressure": [f"{incident_id}:system_fact:0002"],
                "contradiction": [f"{incident_id}:ui_fact:0003"],
            },
            "live_anomaly_id": "anomaly-test",
            "next_check": {
                "kind": "targeted_log_check",
                "prompt": "Capture normalized lookup key and table resolution path.",
            },
            "budget": {
                "checks_remaining": 2,
            },
            "status": "active",
        }

    def _write_checkpoint(self, path: Path, checkpoint: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(checkpoint, indent=2) + "\n")

    def test_required_field_validation(self) -> None:
        checkpoint = self._valid_checkpoint()
        del checkpoint["promise_id"]

        errors = validate_promise_frame_checkpoint(checkpoint, context="checkpoint")
        self.assertTrue(errors)
        self.assertIn("missing required keys", errors[0])

    def test_status_validation(self) -> None:
        checkpoint = self._valid_checkpoint()
        checkpoint["status"] = "paused"

        errors = validate_promise_frame_checkpoint(checkpoint, context="checkpoint")
        self.assertTrue(any("status must be one of" in error for error in errors))

    def test_deterministic_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incident_id = "incident-test"
            self._write_checkpoint(
                root / incident_id / "z-last.json",
                self._valid_checkpoint(frame_id="frame-z", incident_id=incident_id),
            )
            self._write_checkpoint(
                root / incident_id / "a-first.json",
                self._valid_checkpoint(frame_id="frame-a", incident_id=incident_id),
            )

            loaded = load_promise_frames_for_incident_v1(root, incident_id)
            self.assertEqual(["frame-a", "frame-z"], [frame["frame_id"] for frame in loaded])

    def test_rejects_malformed_witness_ids_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "checkpoint.json"
            checkpoint = self._valid_checkpoint()
            checkpoint["witness_ids"]["support"] = "incident-test:missing_event:0001"
            self._write_checkpoint(path, checkpoint)

            with self.assertRaises(ValueError):
                load_promise_frame_checkpoint_v1(path)

    def test_rejects_missing_or_empty_next_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.json"
            missing_checkpoint = self._valid_checkpoint(frame_id="frame-missing")
            del missing_checkpoint["next_check"]
            self._write_checkpoint(missing_path, missing_checkpoint)

            with self.assertRaises(ValueError):
                load_promise_frame_checkpoint_v1(missing_path)

            empty_path = Path(temp_dir) / "empty.json"
            empty_checkpoint = self._valid_checkpoint(frame_id="frame-empty")
            empty_checkpoint["next_check"] = {}
            self._write_checkpoint(empty_path, empty_checkpoint)

            with self.assertRaises(ValueError):
                load_promise_frame_checkpoint_v1(empty_path)

    def test_example_frames_load(self) -> None:
        repotrace_path = (
            ROOT
            / "diagnostics/session/promise_frames/incident-20260312-220604"
            / "frame-repotrace-queue-preview-20260324T101500Z.json"
        )
        nutriplanner_path = (
            ROOT
            / "diagnostics/session/promise_frames/incident-20260313-235921"
            / "frame-nutriplanner-collapse-20260324T101900Z.json"
        )

        repotrace_frame = load_promise_frame_checkpoint_v1(repotrace_path)
        nutriplanner_frame = load_promise_frame_checkpoint_v1(nutriplanner_path)

        self.assertEqual(
            "promise-repotrace-queue-preview-reflects-selected-collection",
            repotrace_frame["promise_id"],
        )
        self.assertEqual(
            "promise-nutriplanner-collapse-boundary-lockstep",
            nutriplanner_frame["promise_id"],
        )
        self.assertEqual("active", repotrace_frame["status"])
        self.assertEqual("anomaly_found", nutriplanner_frame["status"])


if __name__ == "__main__":
    unittest.main()
