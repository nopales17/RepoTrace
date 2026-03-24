import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))

from artifact_adapters import (  # noqa: E402
    apply_promise_scan_outcome_statuses,
    load_promise_scan_outcome_v1,
    load_promise_scan_outcomes_for_incident_v1,
    validate_promise_scan_outcome,
)


class PromiseScanOutcomeTests(unittest.TestCase):
    def _valid_scan_outcome(
        self,
        *,
        outcome_id: str = "outcome-test",
        outcome: str = "anomaly_found",
        next_action: str = "Run one follow-up ordering check.",
        resulting_coverage_status: str = "anomaly_found",
        resulting_task_status: str = "done",
    ) -> dict:
        return {
            "schema_version": "PromiseScanOutcome.v1",
            "produced_by": "tests",
            "outcome_id": outcome_id,
            "task_id": "task-test",
            "frame_id": "frame-test",
            "incident_id": "incident-test",
            "promise_id": "promise-test",
            "interaction_family": "queue lookup",
            "consistency_boundary": "screen/runtime/rule key agreement",
            "outcome": outcome,
            "summary": "Probe completed for one deterministic slice.",
            "witness_ids_added": [],
            "anomaly_ids": [],
            "killed_reason": None,
            "next_action": next_action,
            "resulting_coverage_status": resulting_coverage_status,
            "resulting_task_status": resulting_task_status,
            "created_at": "2026-03-24T12:00:00Z",
        }

    def _valid_coverage_cell(self) -> dict:
        return {
            "promise_id": "promise-test",
            "interaction_family": "queue lookup",
            "consistency_boundary": "screen/runtime/rule key agreement",
            "status": "mapped",
            "last_session_ref": "frame-test",
            "notes": "seed",
            "updated_at": "2026-03-24T12:00:00Z",
        }

    def _valid_task(self) -> dict:
        return {
            "schema_version": "PromiseTraversalTask.v1",
            "produced_by": "tests",
            "task_id": "task-test",
            "promise_id": "promise-test",
            "interaction_family": "queue lookup",
            "consistency_boundary": "screen/runtime/rule key agreement",
            "assigned_frame_id": "frame-test",
            "objective": "Run one deterministic boundary probe.",
            "status": "active",
            "budget": {
                "checks_remaining": 1,
            },
            "created_at": "2026-03-24T12:00:00Z",
            "updated_at": "2026-03-24T12:00:00Z",
        }

    def _write_outcome(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")

    def test_required_field_validation(self) -> None:
        payload = self._valid_scan_outcome()
        del payload["summary"]

        errors = validate_promise_scan_outcome(payload, context="scan_outcome")
        self.assertTrue(errors)
        self.assertIn("missing required keys", errors[0])

    def test_outcome_enum_validation(self) -> None:
        payload = self._valid_scan_outcome(outcome="paused")

        errors = validate_promise_scan_outcome(payload, context="scan_outcome")
        self.assertTrue(any("outcome must be one of" in error for error in errors))

    def test_rejects_missing_or_empty_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing-next-action.json"
            missing = self._valid_scan_outcome(outcome_id="outcome-missing-next-action")
            del missing["next_action"]
            self._write_outcome(missing_path, missing)

            with self.assertRaises(ValueError):
                load_promise_scan_outcome_v1(missing_path)

            empty_path = Path(temp_dir) / "empty-next-action.json"
            empty = self._valid_scan_outcome(
                outcome_id="outcome-empty-next-action",
                next_action="   ",
            )
            self._write_outcome(empty_path, empty)

            with self.assertRaises(ValueError):
                load_promise_scan_outcome_v1(empty_path)

    def test_rejects_invalid_resulting_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bad_coverage_path = Path(temp_dir) / "bad-coverage.json"
            bad_coverage = self._valid_scan_outcome(outcome_id="outcome-bad-coverage")
            bad_coverage["resulting_coverage_status"] = "paused"
            self._write_outcome(bad_coverage_path, bad_coverage)

            with self.assertRaises(ValueError):
                load_promise_scan_outcome_v1(bad_coverage_path)

            bad_task_path = Path(temp_dir) / "bad-task.json"
            bad_task = self._valid_scan_outcome(outcome_id="outcome-bad-task")
            bad_task["resulting_task_status"] = "paused"
            self._write_outcome(bad_task_path, bad_task)

            with self.assertRaises(ValueError):
                load_promise_scan_outcome_v1(bad_task_path)

    def test_deterministic_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incident_id = "incident-test"
            self._write_outcome(
                root / incident_id / "z-last.json",
                self._valid_scan_outcome(outcome_id="outcome-z"),
            )
            self._write_outcome(
                root / incident_id / "a-first.json",
                self._valid_scan_outcome(outcome_id="outcome-a"),
            )

            loaded = load_promise_scan_outcomes_for_incident_v1(root, incident_id)
            self.assertEqual(["outcome-a", "outcome-z"], [item["outcome_id"] for item in loaded])

    def test_apply_outcome_updates_statuses_only(self) -> None:
        coverage_cell = self._valid_coverage_cell()
        task = self._valid_task()
        scan_outcome = self._valid_scan_outcome(
            resulting_coverage_status="anomaly_found",
            resulting_task_status="done",
        )

        updated_cell, updated_task = apply_promise_scan_outcome_statuses(
            coverage_cell,
            task,
            scan_outcome,
        )

        self.assertEqual("anomaly_found", updated_cell["status"])
        self.assertEqual("done", updated_task["status"])
        self.assertEqual("frame-test", updated_cell["last_session_ref"])
        self.assertEqual("Run one deterministic boundary probe.", updated_task["objective"])

    def test_apply_outcome_rejects_malformed_linkage(self) -> None:
        coverage_cell = self._valid_coverage_cell()
        task = self._valid_task()
        scan_outcome = self._valid_scan_outcome()
        scan_outcome["promise_id"] = "promise-other"

        with self.assertRaises(ValueError):
            apply_promise_scan_outcome_statuses(coverage_cell, task, scan_outcome)

    def test_example_outcomes_load(self) -> None:
        repotrace_path = (
            ROOT
            / "diagnostics/session/promise_outcomes/incident-20260312-220604"
            / "outcome-repotrace-queue-lookup-20260324T123500Z.json"
        )
        nutriplanner_path = (
            ROOT
            / "diagnostics/session/promise_outcomes/incident-20260313-235921"
            / "outcome-nutriplanner-collapse-seam-20260324T124100Z.json"
        )

        repotrace_outcome = load_promise_scan_outcome_v1(repotrace_path)
        nutriplanner_outcome = load_promise_scan_outcome_v1(nutriplanner_path)

        self.assertEqual("blocked", repotrace_outcome["outcome"])
        self.assertEqual("anomaly_found", nutriplanner_outcome["outcome"])
        self.assertEqual("blocked", repotrace_outcome["resulting_task_status"])
        self.assertEqual("done", nutriplanner_outcome["resulting_task_status"])


if __name__ == "__main__":
    unittest.main()
