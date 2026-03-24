import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))

from artifact_adapters import (  # noqa: E402
    assemble_promise_work_packet,
    load_promise_check_library_v1,
    load_promise_coverage_ledger_v1,
    load_promise_frame_checkpoint_v1,
    load_promise_scan_outcome_v1,
    load_promise_touch_map_v1,
    load_promise_traversal_task_v1,
    load_promise_work_packet_v1,
    load_promise_work_packets_for_incident_v1,
    validate_promise_work_packet_v1,
)


class PromiseWorkPacketTests(unittest.TestCase):
    def _repotrace_packet_path(self) -> Path:
        return (
            ROOT
            / "diagnostics/session/promise_work_packets/incident-20260312-220604"
            / "packet-repotrace-queue-lookup-20260324T130500Z.json"
        )

    def _nutriplanner_packet_path(self) -> Path:
        return (
            ROOT
            / "diagnostics/session/promise_work_packets/incident-20260313-235921"
            / "packet-nutriplanner-collapse-lockstep-20260324T130900Z.json"
        )

    def _valid_packet(self) -> dict:
        return json.loads(self._repotrace_packet_path().read_text())

    def test_required_field_validation(self) -> None:
        packet = self._valid_packet()
        del packet["objective"]

        errors = validate_promise_work_packet_v1(packet, context="work_packet")
        self.assertTrue(errors)
        self.assertIn("missing required keys", errors[0])

    def test_status_validation(self) -> None:
        packet = self._valid_packet()
        packet["status"] = "paused"

        errors = validate_promise_work_packet_v1(packet, context="work_packet")
        self.assertTrue(any("status must be one of" in error for error in errors))

    def test_deterministic_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incident_id = "incident-20260312-220604"
            incident_dir = root / incident_id
            incident_dir.mkdir(parents=True, exist_ok=True)

            packet_z = self._valid_packet()
            packet_z["work_packet_id"] = "packet-z"
            packet_z["created_at"] = "2026-03-24T13:10:00Z"
            packet_z["updated_at"] = "2026-03-24T13:10:00Z"

            packet_a = self._valid_packet()
            packet_a["work_packet_id"] = "packet-a"
            packet_a["created_at"] = "2026-03-24T13:11:00Z"
            packet_a["updated_at"] = "2026-03-24T13:11:00Z"

            (incident_dir / "z.json").write_text(json.dumps(packet_z, indent=2) + "\n")
            (incident_dir / "a.json").write_text(json.dumps(packet_a, indent=2) + "\n")

            loaded = load_promise_work_packets_for_incident_v1(root, incident_id)
            self.assertEqual(["packet-a", "packet-z"], [item["work_packet_id"] for item in loaded])

    def test_packet_assembly(self) -> None:
        registry = json.loads((ROOT / "diagnostics/memory/promise_registry.json").read_text())
        promise = next(
            card
            for card in registry["promises"]
            if card["promise_id"] == "promise-repotrace-queue-preview-reflects-selected-collection"
        )

        touch_map = load_promise_touch_map_v1(
            ROOT
            / "diagnostics/memory/promise_touch_maps"
            / "promise-repotrace-queue-preview-reflects-selected-collection.touch_map.json"
        )
        accepted_slice = next(
            candidate
            for candidate in touch_map["slice_candidates"]
            if candidate["status"] == "accepted"
        )

        frame = load_promise_frame_checkpoint_v1(
            ROOT
            / "diagnostics/session/promise_frames/incident-20260312-220604"
            / "frame-repotrace-queue-preview-20260324T101500Z.json"
        )
        task = load_promise_traversal_task_v1(
            ROOT / "diagnostics/session/promise_tasks/task-repotrace-queue-lookup-scan.json"
        )

        ledger = load_promise_coverage_ledger_v1(
            ROOT
            / "diagnostics/memory/promise_coverage_ledgers"
            / "promise-repotrace-queue-preview-reflects-selected-collection.coverage_ledger.json"
        )
        coverage = next(
            cell
            for cell in ledger["coverage"]
            if cell["interaction_family"] == "queue lookup"
            and cell["consistency_boundary"] == "screenCollection/runtimeCollection/ruleCollection agreement"
        )

        check_library = load_promise_check_library_v1(
            ROOT / "diagnostics/memory/promise_check_libraries/promise-check-library.seed.v1.json"
        )

        outcome = load_promise_scan_outcome_v1(
            ROOT
            / "diagnostics/session/promise_outcomes/incident-20260312-220604"
            / "outcome-repotrace-queue-lookup-20260324T123500Z.json"
        )

        packet = assemble_promise_work_packet(
            work_packet_id="packet-assembled-test",
            incident_id="incident-20260312-220604",
            promise=promise,
            touch_map=touch_map,
            accepted_slice=accepted_slice,
            frame=frame,
            task=task,
            coverage=coverage,
            candidate_checks=check_library["checks"],
            prior_outcomes=[outcome],
            frame_ref="diagnostics/session/promise_frames/incident-20260312-220604/frame-repotrace-queue-preview-20260324T101500Z.json",
            task_ref="diagnostics/session/promise_tasks/task-repotrace-queue-lookup-scan.json",
            touch_map_ref="diagnostics/memory/promise_touch_maps/promise-repotrace-queue-preview-reflects-selected-collection.touch_map.json",
            coverage_ref=(
                "diagnostics/memory/promise_coverage_ledgers/"
                "promise-repotrace-queue-preview-reflects-selected-collection.coverage_ledger.json"
                "#promise-repotrace-queue-preview-reflects-selected-collection"
                "|queue lookup|screenCollection/runtimeCollection/ruleCollection agreement"
            ),
            prior_outcome_refs=[
                "diagnostics/session/promise_outcomes/incident-20260312-220604/"
                "outcome-repotrace-queue-lookup-20260324T123500Z.json"
            ],
            unresolved_questions=["Is divergence introduced before lookupHit is evaluated?"],
            status="ready",
            created_at="2026-03-24T13:20:00Z",
            updated_at="2026-03-24T13:20:00Z",
        )

        self.assertEqual("PromiseWorkPacket.v1", packet["schema_version"])
        self.assertEqual("packet-assembled-test", packet["work_packet_id"])
        self.assertEqual(["check-repotrace-queue-key-agreement-trace-v1"], packet["check_ids"])

    def test_rejects_promise_mismatch_across_refs(self) -> None:
        packet = self._valid_packet()
        packet["task_ref"] = "diagnostics/session/promise_tasks/task-nutriplanner-collapse-seam-scan.json"

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "packet.json"
            path.write_text(json.dumps(packet, indent=2) + "\n")

            with self.assertRaises(ValueError):
                load_promise_work_packet_v1(path)

    def test_rejects_slice_mismatch_across_refs(self) -> None:
        packet = self._valid_packet()
        packet["coverage_ref"] = (
            "diagnostics/memory/promise_coverage_ledgers/"
            "promise-repotrace-queue-preview-reflects-selected-collection.coverage_ledger.json"
            "#promise-repotrace-queue-preview-reflects-selected-collection"
            "|pick collection|queue rule lookup key normalization"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "packet.json"
            path.write_text(json.dumps(packet, indent=2) + "\n")

            with self.assertRaises(ValueError):
                load_promise_work_packet_v1(path)

    def test_rejects_incompatible_check_ids(self) -> None:
        packet = self._valid_packet()
        packet["check_ids"] = ["check-nutriplanner-collapse-delta-trace-v1"]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "packet.json"
            path.write_text(json.dumps(packet, indent=2) + "\n")

            with self.assertRaises(ValueError):
                load_promise_work_packet_v1(path)

    def test_example_artifact_loading(self) -> None:
        repotrace = load_promise_work_packet_v1(self._repotrace_packet_path())
        nutriplanner = load_promise_work_packet_v1(self._nutriplanner_packet_path())

        self.assertEqual("blocked", repotrace["status"])
        self.assertEqual("completed", nutriplanner["status"])
        self.assertEqual(
            ["check-repotrace-queue-key-agreement-trace-v1"],
            repotrace["check_ids"],
        )
        self.assertEqual(
            ["check-nutriplanner-collapse-delta-trace-v1"],
            nutriplanner["check_ids"],
        )


if __name__ == "__main__":
    unittest.main()
