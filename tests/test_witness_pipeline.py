import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))

from artifact_adapters import (  # noqa: E402
    build_witness_set_v1,
    critique_witness_candidate,
)


class WitnessPipelineTests(unittest.TestCase):
    def _provenance(self) -> dict[str, list[str]]:
        return {
            "source_incident_ids": ["incident-test"],
            "raw_field_refs": ["reporterNotes"],
            "breadcrumb_refs": [],
            "log_refs": [],
            "screenshot_refs": [],
            "verifier_refs": ["tests"],
        }

    def test_critic_rejects_missing_provenance(self) -> None:
        candidate = {
            "witness_type": "system_fact",
            "statement": "runtimeCollection=ROAD_TRIP_MIX",
        }
        critique = critique_witness_candidate(candidate)
        self.assertFalse(critique["accepted"])
        self.assertIn("missing_provenance", critique["reasons"])

    def test_critic_rejects_composite_claim(self) -> None:
        candidate = {
            "witness_type": "system_fact",
            "statement": "screenCollection=ROAD_TRIP_MIX and runtimeCollection=ROAD_TRIP_MIX",
            "provenance": self._provenance(),
        }
        critique = critique_witness_candidate(candidate)
        self.assertFalse(critique["accepted"])
        self.assertIn("composite_claim", critique["reasons"])

    def test_critic_rejects_abstract_claim(self) -> None:
        candidate = {
            "witness_type": "observed_state",
            "statement": "unexpected behavior",
            "provenance": self._provenance(),
        }
        critique = critique_witness_candidate(candidate)
        self.assertFalse(critique["accepted"])
        self.assertIn("too_abstract", critique["reasons"])

    def test_critic_rejects_noisy_log_probe_statement(self) -> None:
        provenance = self._provenance()
        provenance["log_refs"] = ["breadcrumbs[1]"]
        provenance["breadcrumb_refs"] = ["breadcrumbs[1]"]
        candidate = {
            "witness_type": "system_fact",
            "statement": "event=probe.ownerStack.sample",
            "provenance": provenance,
        }
        critique = critique_witness_candidate(candidate)
        self.assertFalse(critique["accepted"])
        self.assertIn("noisy_log_statement", critique["reasons"])

    def test_pipeline_splits_and_keeps_concrete_witnesses(self) -> None:
        raw_path = ROOT / "diagnostics/inbox/incident-20260312-220604.json"
        raw_incident = json.loads(raw_path.read_text())

        witness_set = build_witness_set_v1(
            raw_incident,
            incident_id=raw_incident["id"],
            produced_by="tests",
        )

        self.assertEqual("WitnessSet.v1", witness_set["schema_version"])
        metrics = witness_set["metrics"]
        self.assertEqual(metrics["candidate_count"], metrics["accepted_count"] + metrics["rejected_count"])
        self.assertGreater(metrics["accepted_count"], 0)
        self.assertLessEqual(metrics["unsupported_count"], metrics["rejected_count"])

        statements = {w["statement"] for w in witness_set["witnesses"]}
        self.assertIn("UI shows collection Road Trip Mix", statements)
        self.assertIn("queue preview is 0 tracks.", statements)

        for witness in witness_set["witnesses"]:
            provenance = witness["provenance"]
            self.assertTrue(provenance["source_incident_ids"])
            self.assertTrue(
                provenance["raw_field_refs"]
                or provenance["breadcrumb_refs"]
                or provenance["log_refs"]
                or provenance["screenshot_refs"]
            )
            critique = critique_witness_candidate(witness)
            self.assertTrue(critique["accepted"], msg=f"unexpected rejection: {critique['reasons']}")

    def test_pipeline_filters_noisy_duplicates_and_tracks_metrics(self) -> None:
        raw_incident = {
            "id": "incident-noisy",
            "metadata": {
                "appVersion": "1.0",
            },
            "breadcrumbs": [
                {
                    "category": "log",
                    "timestamp": "2026-03-14T06:59:12Z",
                    "message": "event=probe.ownerStack.sample trigger=begin target=5C021D01-56C9-4C33-8F72-9F5A6528CD7F transitionSeq=3",
                },
                {
                    "category": "log",
                    "timestamp": "2026-03-14T06:59:13Z",
                    "message": "event=probe.ownerStack.sample trigger=begin target=5C021D01-56C9-4C33-8F72-9F5A6528CD7F transitionSeq=3",
                },
            ],
        }

        witness_set = build_witness_set_v1(raw_incident, incident_id="incident-noisy", produced_by="tests")
        metrics = witness_set["metrics"]

        self.assertEqual(metrics["candidate_count"], metrics["accepted_count"] + metrics["rejected_count"])
        self.assertGreater(metrics["rejected_count"], 0)
        self.assertLessEqual(metrics["unsupported_count"], metrics["rejected_count"])

        reasons = [reason for candidate in witness_set["rejected_candidates"] for reason in candidate.get("reasons", [])]
        self.assertIn("noisy_log_statement", reasons)
        self.assertIn("duplicate_statement", reasons)


if __name__ == "__main__":
    unittest.main()
