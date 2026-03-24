import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))

from artifact_adapters import (  # noqa: E402
    load_promise_coverage_ledger_v1,
    load_promise_tasks_from_dir_v1,
    load_promise_traversal_task_v1,
    update_coverage_cell_from_frame_outcome,
    validate_promise_coverage_cell,
    validate_promise_traversal_task,
)


class PromiseCoverageLedgerTests(unittest.TestCase):
    def _valid_cell(
        self,
        *,
        interaction_family: str = "queue lookup",
        consistency_boundary: str = "screen/runtime/rule key agreement",
        status: str = "mapped",
    ) -> dict:
        return {
            "promise_id": "promise-test",
            "interaction_family": interaction_family,
            "consistency_boundary": consistency_boundary,
            "status": status,
            "last_session_ref": "frame-test-1",
            "notes": "seed",
            "updated_at": "2026-03-24T12:00:00Z",
        }

    def _write_ledger(self, path: Path, coverage: list[dict]) -> None:
        payload = {
            "schema_version": "PromiseCoverageLedger.v1",
            "produced_by": "tests",
            "ledger_version": 1,
            "generated_at": "2026-03-24T12:00:00Z",
            "coverage": coverage,
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")

    def _valid_frame_outcome(self, *, status: str = "anomaly_found") -> dict:
        return {
            "frame_id": "frame-test-2",
            "promise_id": "promise-test",
            "interaction_family": "queue lookup",
            "consistency_boundary": "screen/runtime/rule key agreement",
            "status": status,
            "updated_at": "2026-03-24T12:30:00Z",
        }

    def test_required_field_validation(self) -> None:
        cell = self._valid_cell()
        del cell["promise_id"]

        errors = validate_promise_coverage_cell(cell, context="cell")
        self.assertTrue(errors)
        self.assertIn("missing required keys", errors[0])

    def test_status_validation(self) -> None:
        cell = self._valid_cell(status="paused")

        errors = validate_promise_coverage_cell(cell, context="cell")
        self.assertTrue(any("status must be one of" in error for error in errors))

    def test_rejects_duplicate_coverage_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "coverage_ledger.json"
            self._write_ledger(
                path,
                coverage=[
                    self._valid_cell(status="mapped"),
                    self._valid_cell(status="scanned"),
                ],
            )

            with self.assertRaises(ValueError):
                load_promise_coverage_ledger_v1(path)

    def test_deterministic_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "coverage_ledger.json"
            self._write_ledger(
                path,
                coverage=[
                    self._valid_cell(
                        interaction_family="z-last",
                        consistency_boundary="z-boundary",
                        status="mapped",
                    ),
                    self._valid_cell(
                        interaction_family="a-first",
                        consistency_boundary="a-boundary",
                        status="mapped",
                    ),
                ],
            )

            loaded = load_promise_coverage_ledger_v1(path)
            self.assertEqual(
                ["a-first", "z-last"],
                [cell["interaction_family"] for cell in loaded["coverage"]],
            )

    def test_frame_outcome_updates_coverage_cell(self) -> None:
        ledger = {
            "schema_version": "PromiseCoverageLedger.v1",
            "produced_by": "tests",
            "ledger_version": 1,
            "coverage": [
                self._valid_cell(status="mapped"),
            ],
        }

        after_scan = update_coverage_cell_from_frame_outcome(
            ledger,
            self._valid_frame_outcome(status="active"),
            notes="scan pass",
        )
        self.assertEqual("scanned", after_scan["coverage"][0]["status"])
        self.assertEqual("frame-test-2", after_scan["coverage"][0]["last_session_ref"])
        self.assertEqual("scan pass", after_scan["coverage"][0]["notes"])

        after_anomaly = update_coverage_cell_from_frame_outcome(
            after_scan,
            self._valid_frame_outcome(status="anomaly_found"),
        )
        self.assertEqual("anomaly_found", after_anomaly["coverage"][0]["status"])

        no_downgrade = update_coverage_cell_from_frame_outcome(
            after_anomaly,
            self._valid_frame_outcome(status="active"),
        )
        self.assertEqual("anomaly_found", no_downgrade["coverage"][0]["status"])

    def test_example_ledgers_load(self) -> None:
        repotrace_path = (
            ROOT
            / "diagnostics/memory/promise_coverage_ledgers"
            / "promise-repotrace-queue-preview-reflects-selected-collection.coverage_ledger.json"
        )
        nutriplanner_path = (
            ROOT
            / "diagnostics/memory/promise_coverage_ledgers"
            / "promise-nutriplanner-collapse-boundary-lockstep.coverage_ledger.json"
        )

        repotrace_ledger = load_promise_coverage_ledger_v1(repotrace_path)
        nutriplanner_ledger = load_promise_coverage_ledger_v1(nutriplanner_path)

        self.assertEqual("PromiseCoverageLedger.v1", repotrace_ledger["schema_version"])
        self.assertEqual("PromiseCoverageLedger.v1", nutriplanner_ledger["schema_version"])
        self.assertEqual(3, len(repotrace_ledger["coverage"]))
        self.assertEqual(3, len(nutriplanner_ledger["coverage"]))


class PromiseTraversalTaskTests(unittest.TestCase):
    def _valid_task(self, task_id: str = "task-test") -> dict:
        return {
            "schema_version": "PromiseTraversalTask.v1",
            "produced_by": "tests",
            "task_id": task_id,
            "promise_id": "promise-test",
            "interaction_family": "queue lookup",
            "consistency_boundary": "screen/runtime/rule key agreement",
            "assigned_frame_id": "frame-test",
            "objective": "Collect one deterministic boundary trace.",
            "status": "queued",
            "budget": {
                "checks_remaining": 1,
            },
            "created_at": "2026-03-24T12:00:00Z",
            "updated_at": "2026-03-24T12:00:00Z",
        }

    def test_task_required_field_validation(self) -> None:
        task = self._valid_task()
        del task["objective"]

        errors = validate_promise_traversal_task(task, context="task")
        self.assertTrue(errors)
        self.assertIn("missing required keys", errors[0])

    def test_task_status_validation(self) -> None:
        task = self._valid_task()
        task["status"] = "paused"

        errors = validate_promise_traversal_task(task, context="task")
        self.assertTrue(any("status must be one of" in error for error in errors))

    def test_task_loading(self) -> None:
        repotrace_task = ROOT / "diagnostics/session/promise_tasks/task-repotrace-queue-lookup-scan.json"
        nutriplanner_task = ROOT / "diagnostics/session/promise_tasks/task-nutriplanner-collapse-seam-scan.json"

        loaded_repotrace = load_promise_traversal_task_v1(repotrace_task)
        loaded_nutriplanner = load_promise_traversal_task_v1(nutriplanner_task)

        self.assertEqual("active", loaded_repotrace["status"])
        self.assertEqual("queued", loaded_nutriplanner["status"])

    def test_directory_loading_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_dir = Path(temp_dir)
            task_z = self._valid_task(task_id="task-z")
            task_a = self._valid_task(task_id="task-a")

            (tasks_dir / "z.json").write_text(json.dumps(task_z, indent=2) + "\n")
            (tasks_dir / "a.json").write_text(json.dumps(task_a, indent=2) + "\n")

            loaded = load_promise_tasks_from_dir_v1(tasks_dir)
            self.assertEqual(["task-a", "task-z"], [task["task_id"] for task in loaded])


if __name__ == "__main__":
    unittest.main()
