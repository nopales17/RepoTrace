import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))

from artifact_adapters import load_experiment_profiles_v1, normalize_retrieval_attempt  # noqa: E402
from eval_harness import REQUIRED_METRIC_KEYS, run_evaluation  # noqa: E402


class EvalHarnessTests(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")

    def _write_profile(self, directory: Path, profile_id: str) -> None:
        payload = {
            "schema_version": "ExperimentProfile.v1",
            "produced_by": "tests",
            "profile_id": profile_id,
            "name": profile_id,
            "status": "active",
            "fixture_refs": ["repotrace-current-incident", "nutriplanner-collapse-case"],
            "scoping_mode": "none",
            "promise_id": None,
            "slice_key": None,
        }
        self._write_json(directory / f"{profile_id}.json", payload)

    def _run(self, args: list[str], cwd: Path) -> str:
        return subprocess.check_output(args, cwd=cwd, text=True).strip()

    def _init_lineage_repo(self, repo_dir: Path) -> tuple[str, str]:
        repo_dir.mkdir(parents=True, exist_ok=True)
        self._run(["git", "init"], cwd=repo_dir)
        self._run(["git", "config", "user.email", "tests@example.com"], cwd=repo_dir)
        self._run(["git", "config", "user.name", "Eval Tests"], cwd=repo_dir)

        incident_payload = {
            "id": "incident-eval",
            "title": "Fixture incident",
            "expectedBehavior": "queue should show four tracks",
            "actualBehavior": "unexpected behavior",
            "reporterNotes": "issue happened",
            "metadata": {"timestamp": "2026-03-24T00:00:00Z"},
            "breadcrumbs": [
                {
                    "category": "pipeline",
                    "timestamp": "2026-03-24T00:00:01Z",
                    "message": "Queue rule lookup: lookupHit=false",
                }
            ],
            "screenshotFilename": "incident-eval.jpg",
        }

        retrieval_old = {
            "incident_id": "incident-eval",
            "generated_at": "2026-03-24T00:00:01Z",
            "retrieval": {
                "verdict": "motif_non_match",
                "candidate_subsystems": ["lookup", "mapping"],
                "candidates": [
                    {
                        "contradicting_evidence": ["runtime key mismatch"],
                        "next_discriminating_check": "inspect lookup key normalization",
                    }
                ],
            },
        }

        retrieval_new = {
            "incident_id": "incident-eval",
            "generated_at": "2026-03-24T00:00:02Z",
            "retrieval": {
                "verdict": "ambiguous",
                "candidate_subsystems": ["lookup"],
                "candidates": [
                    {
                        "contradicting_evidence": [
                            "top-level contradiction",
                            "None: placeholder",
                        ],
                        "next_discriminating_check": "add one narrow instrumentation check",
                    }
                ],
            },
        }

        incident_path = repo_dir / "diagnostics/inbox/incident-eval.json"
        retrieval_path = repo_dir / "diagnostics/retrieval_results/incident-eval.json"

        self._write_json(incident_path, incident_payload)
        self._write_json(retrieval_path, retrieval_old)
        self._run(["git", "add", "."], cwd=repo_dir)
        self._run(["git", "commit", "-m", "old retrieval"], cwd=repo_dir)
        old_commit = self._run(["git", "rev-parse", "HEAD"], cwd=repo_dir)

        self._write_json(retrieval_path, retrieval_new)
        self._run(["git", "add", "."], cwd=repo_dir)
        self._run(["git", "commit", "-m", "new retrieval"], cwd=repo_dir)
        new_commit = self._run(["git", "rev-parse", "HEAD"], cwd=repo_dir)

        return old_commit, new_commit

    def test_profile_loading_is_deterministic_and_dedupes_by_profile_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_dir = Path(temp_dir)
            self._write_profile(profiles_dir, "layered_plus_witnesses")
            self._write_profile(profiles_dir, "baseline_flat_retrieval")
            self._write_profile(profiles_dir, "layered_storage_only")
            # Duplicate by profile_id should be ignored deterministically.
            duplicate = {
                "schema_version": "ExperimentProfile.v1",
                "produced_by": "tests",
                "profile_id": "baseline_flat_retrieval",
                "name": "duplicate",
                "status": "active",
                "fixture_refs": ["repotrace-current-incident"],
            }
            self._write_json(profiles_dir / "zzz_duplicate.json", duplicate)

            profiles = load_experiment_profiles_v1(
                profiles_dir,
                required_profile_ids=[
                    "baseline_flat_retrieval",
                    "layered_storage_only",
                    "layered_plus_witnesses",
                ],
            )

            self.assertEqual(
                ["baseline_flat_retrieval", "layered_plus_witnesses", "layered_storage_only"],
                [p["profile_id"] for p in profiles],
            )

    def test_profile_loading_enforces_required_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_dir = Path(temp_dir)
            self._write_profile(profiles_dir, "baseline_flat_retrieval")
            self._write_profile(profiles_dir, "layered_storage_only")

            with self.assertRaises(ValueError):
                load_experiment_profiles_v1(
                    profiles_dir,
                    required_profile_ids=[
                        "baseline_flat_retrieval",
                        "layered_storage_only",
                        "layered_plus_witnesses",
                    ],
                )

    def test_normalize_retrieval_attempt_supports_legacy_and_v1_shapes(self) -> None:
        legacy_payload = {
            "incident_id": "incident-legacy",
            "generated_at": "2026-03-24T01:00:00Z",
            "retrieval": {
                "verdict": "ambiguous",
                "subsystem_candidates": ["queue", "lookup"],
                "candidates": [
                    {
                        "next_discriminating_check": "inspect queue key",
                        "contradicting_evidence": ["key mismatch"],
                    }
                ],
            },
        }
        normalized_legacy = normalize_retrieval_attempt(legacy_payload)
        self.assertEqual("legacy_retrieval_result", normalized_legacy["source_shape"])
        self.assertEqual(2, normalized_legacy["candidate_count"])
        self.assertTrue(normalized_legacy["has_discriminating_check"])
        self.assertEqual(["key mismatch"], normalized_legacy["contradiction_items"])

        v1_payload = {
            "schema_version": "RetrievalAttempt.v1",
            "retrieval_attempt_id": "incident-v1:run",
            "incident_id": "incident-v1",
            "run_id": "run",
            "generated_at": "2026-03-24T01:00:00Z",
            "verdict": "motif_non_match",
            "candidate_subsystems": ["lookup"],
            "next_discriminating_check": "validate mapping",
            "contradiction_items": ["not aligned"],
        }
        normalized_v1 = normalize_retrieval_attempt(v1_payload)
        self.assertEqual("retrieval_attempt_v1", normalized_v1["source_shape"])
        self.assertEqual("incident-v1:run", normalized_v1["attempt_id"])
        self.assertEqual(1, normalized_v1["candidate_count"])
        self.assertTrue(normalized_v1["has_discriminating_check"])
        self.assertEqual(["not aligned"], normalized_v1["contradiction_items"])

    def test_fixture_execution_emits_structured_metrics_for_all_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profiles_dir = temp_root / "profiles"
            fixtures_dir = temp_root / "fixtures"
            runs_dir = temp_root / "runs"
            source_repo = temp_root / "fixture_repo"

            for profile_id in (
                "baseline_flat_retrieval",
                "layered_storage_only",
                "layered_plus_witnesses",
            ):
                self._write_profile(profiles_dir, profile_id)

            old_commit, new_commit = self._init_lineage_repo(source_repo)

            fixtures_dir.mkdir(parents=True, exist_ok=True)
            (fixtures_dir / "repotrace-current-incident.yaml").write_text(
                "\n".join(
                    [
                        "schema_version: FixtureManifest.v1",
                        "produced_by: tests",
                        "fixture_id: repotrace-current-incident",
                        "source_repo: tests",
                        f"source_repo_path: {source_repo}",
                        "source_branch: tests",
                        "incident_id: incident-eval",
                        "incident_artifact_path: diagnostics/incidents/incident-eval.md",
                        "incident_evidence_path: diagnostics/inbox/incident-eval.json",
                        "retrieval_artifact_path: diagnostics/retrieval_results/incident-eval.json",
                        "reference_commits:",
                    ]
                )
                + "\n"
            )
            (fixtures_dir / "nutriplanner-collapse-case.yaml").write_text(
                "\n".join(
                    [
                        "schema_version: FixtureManifest.v1",
                        "produced_by: tests",
                        "fixture_id: nutriplanner-collapse-case",
                        "source_repo: tests",
                        f"source_repo_path: {source_repo}",
                        "source_branch: tests",
                        "incident_id: incident-eval",
                        "incident_artifact_path: diagnostics/incidents/incident-eval.md",
                        "incident_evidence_path: diagnostics/inbox/incident-eval.json",
                        "retrieval_artifact_path: diagnostics/retrieval_results/incident-eval.json",
                        "reference_commits:",
                        f"  - {old_commit}",
                        f"  - {new_commit}",
                    ]
                )
                + "\n"
            )

            metrics_path, summary_path, payload = run_evaluation(
                profiles_dir=profiles_dir,
                fixtures_dir=fixtures_dir,
                runs_dir=runs_dir,
                run_id="test-run",
            )

            self.assertTrue(metrics_path.exists())
            self.assertTrue(summary_path.exists())

            self.assertEqual("EvalHarnessRun.v1", payload["schema_version"])
            self.assertEqual(6, len(payload["results"]))

            for result in payload["results"]:
                self.assertIn(result["profile_id"], {"baseline_flat_retrieval", "layered_storage_only", "layered_plus_witnesses"})
                self.assertIn(result["fixture_id"], {"repotrace-current-incident", "nutriplanner-collapse-case"})
                self.assertEqual("none", result["scoping_mode"])
                self.assertIsNone(result["promise_id"])
                self.assertIsNone(result["slice_key"])

                metrics = result["metrics"]
                for key in REQUIRED_METRIC_KEYS:
                    self.assertIn(key, metrics)

                for normalized in result["normalized_attempts"]:
                    self.assertTrue({
                        "attempt_id",
                        "verdict",
                        "candidate_count",
                        "has_discriminating_check",
                        "contradiction_items",
                        "source_shape",
                    }.issubset(set(normalized.keys())))

            nutriplanner_baseline = next(
                result
                for result in payload["results"]
                if result["fixture_id"] == "nutriplanner-collapse-case"
                and result["profile_id"] == "baseline_flat_retrieval"
            )
            nutriplanner_storage = next(
                result
                for result in payload["results"]
                if result["fixture_id"] == "nutriplanner-collapse-case"
                and result["profile_id"] == "layered_storage_only"
            )
            self.assertEqual(1, nutriplanner_baseline["attempt_count"])
            self.assertEqual(2, nutriplanner_storage["attempt_count"])


if __name__ == "__main__":
    unittest.main()
