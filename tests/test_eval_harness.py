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
from eval_harness import (  # noqa: E402
    REQUIRED_METRIC_KEYS,
    REQUIRED_PROFILE_IDS,
    run_evaluation,
)


class EvalHarnessTests(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")

    def _write_profile(self, directory: Path, profile_id: str) -> None:
        scoping_mode = "promise_manual" if profile_id == "promise_manual" else "none"
        payload = {
            "schema_version": "ExperimentProfile.v1",
            "produced_by": "tests",
            "profile_id": profile_id,
            "name": profile_id,
            "status": "active",
            "fixture_refs": ["repotrace-current-incident", "nutriplanner-collapse-case"],
            "scoping_mode": scoping_mode,
            "promise_id": None,
            "slice_key": None,
        }
        self._write_json(directory / f"{profile_id}.json", payload)

    def _run(self, args: list[str], cwd: Path) -> str:
        return subprocess.check_output(args, cwd=cwd, text=True).strip()

    def _promise_card(self, promise_id: str, incident_id: str, fixture_id: str) -> dict:
        return {
            "promise_id": promise_id,
            "statement": f"{promise_id} statement",
            "why_it_exists": "manual promise eval test coverage",
            "actors": ["user", "ui"],
            "assets_or_rights": ["consistency"],
            "protected_state": "state alignment",
            "interaction_families": ["interaction-a"],
            "consistency_boundaries": ["boundary-a"],
            "settlement_horizon": "single transition",
            "representations": ["incident", "retrieval"],
            "admin_or_external_surfaces": ["eval harness"],
            "stress_axes": ["stress-a"],
            "evidence_refs": {
                "source_incident_ids": [incident_id],
                "retrieval_refs": [f"diagnostics/retrieval_results/{incident_id}.json"],
                "witness_refs": [f"diagnostics/evidence/witness_sets/{incident_id}.witness_set.json"],
                "fixture_refs": [f"eval/fixtures/{fixture_id}.yaml"],
                "verifier_refs": ["manual:test"],
            },
            "priority": "high",
            "confidence": 0.75,
            "status": "accepted",
        }

    def _write_promise_bundle(
        self,
        repo_dir: Path,
        *,
        bundle_slug: str,
        incident_id: str,
        promise_id: str,
        broken_loop: bool = False,
    ) -> dict[str, str]:
        frame_id = f"frame-{bundle_slug}"
        task_id = f"task-{bundle_slug}"
        outcome_id = f"outcome-{bundle_slug}"
        interaction_family = "queue lookup"
        consistency_boundary = "screen/runtime/rule alignment"

        frame_path = f"diagnostics/session/promise_frames/{frame_id}.json"
        task_path = f"diagnostics/session/promise_tasks/{task_id}.json"
        outcome_path = f"diagnostics/session/promise_outcomes/{outcome_id}.json"
        coverage_path = f"diagnostics/memory/promise_coverage_ledgers/{promise_id}.coverage_ledger.json"

        frame_payload = {
            "schema_version": "PromiseFrameCheckpoint.v1",
            "produced_by": "tests",
            "frame_id": frame_id,
            "incident_id": incident_id,
            "promise_id": promise_id,
            "interaction_family": interaction_family,
            "consistency_boundary": consistency_boundary,
            "focus_statement": "focus",
            "violation_shape": "shape",
            "touchpoints_remaining": ["touchpoint-a", "touchpoint-b"],
            "pressure_axes_remaining": ["pressure-a"],
            "witness_ids": {
                "support": [f"{incident_id}:support:1"],
                "pressure": [f"{incident_id}:pressure:1"],
                "contradiction": [f"{incident_id}:contradiction:1"],
            },
            "live_anomaly_id": f"anomaly-{bundle_slug}",
            "next_check": {
                "kind": "targeted_log_check",
                "prompt": "run one deterministic check",
            },
            "budget": {
                "checks_remaining": 1,
            },
            "status": "active",
            "updated_at": "2026-03-24T10:00:00Z",
        }

        task_payload = {
            "schema_version": "PromiseTraversalTask.v1",
            "produced_by": "tests",
            "task_id": task_id,
            "promise_id": promise_id,
            "interaction_family": interaction_family,
            "consistency_boundary": consistency_boundary,
            "assigned_frame_id": "frame-mismatch" if broken_loop else frame_id,
            "objective": "run one manual slice",
            "status": "active",
            "budget": {
                "checks_remaining": 1,
                "max_minutes": 20,
            },
            "created_at": "2026-03-24T12:00:00Z",
            "updated_at": "2026-03-24T12:00:00Z",
        }

        outcome_payload = {
            "schema_version": "PromiseScanOutcome.v1",
            "produced_by": "tests",
            "outcome_id": outcome_id,
            "task_id": task_id,
            "frame_id": frame_id,
            "incident_id": incident_id,
            "promise_id": promise_id,
            "interaction_family": interaction_family,
            "consistency_boundary": consistency_boundary,
            "outcome": "anomaly_found",
            "summary": "manual outcome",
            "witness_ids_added": [],
            "anomaly_ids": [f"anomaly-{bundle_slug}"],
            "killed_reason": None,
            "next_action": "follow up",
            "resulting_coverage_status": "anomaly_found",
            "resulting_task_status": "done",
            "created_at": "2026-03-24T12:30:00Z",
        }

        coverage_payload = {
            "schema_version": "PromiseCoverageLedger.v1",
            "produced_by": "tests",
            "ledger_version": 1,
            "coverage": [
                {
                    "promise_id": promise_id,
                    "interaction_family": interaction_family,
                    "consistency_boundary": consistency_boundary,
                    "status": "anomaly_found",
                    "last_session_ref": frame_id,
                    "notes": "covered",
                    "updated_at": "2026-03-24T12:30:00Z",
                }
            ],
        }

        self._write_json(repo_dir / frame_path, frame_payload)
        self._write_json(repo_dir / task_path, task_payload)
        self._write_json(repo_dir / outcome_path, outcome_payload)
        self._write_json(repo_dir / coverage_path, coverage_payload)

        return {
            "promise_frame_checkpoint_path": frame_path,
            "promise_traversal_task_path": task_path,
            "promise_scan_outcome_path": outcome_path,
            "promise_coverage_ledger_path": coverage_path,
        }

    def _init_lineage_repo(
        self,
        repo_dir: Path,
        *,
        broken_loop_fixture: str | None = None,
    ) -> tuple[str, str, dict[str, dict[str, str]]]:
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

        promise_ids = {
            "repotrace-current-incident": "promise-repotrace",
            "nutriplanner-collapse-case": "promise-nutriplanner",
        }
        registry_payload = {
            "schema_version": "PromiseRegistry.v1",
            "produced_by": "tests",
            "registry_version": 1,
            "promises": [
                self._promise_card(promise_ids["repotrace-current-incident"], "incident-eval", "repotrace-current-incident"),
                self._promise_card(promise_ids["nutriplanner-collapse-case"], "incident-eval", "nutriplanner-collapse-case"),
            ],
        }
        registry_path = "diagnostics/memory/promise_registry.json"
        self._write_json(repo_dir / registry_path, registry_payload)

        bundles: dict[str, dict[str, str]] = {}
        for fixture_id, promise_id in promise_ids.items():
            bundle = self._write_promise_bundle(
                repo_dir,
                bundle_slug=fixture_id,
                incident_id="incident-eval",
                promise_id=promise_id,
                broken_loop=fixture_id == broken_loop_fixture,
            )
            bundle["promise_registry_path"] = registry_path
            bundles[fixture_id] = bundle

        self._run(["git", "add", "."], cwd=repo_dir)
        self._run(["git", "commit", "-m", "old retrieval"], cwd=repo_dir)
        old_commit = self._run(["git", "rev-parse", "HEAD"], cwd=repo_dir)

        self._write_json(retrieval_path, retrieval_new)
        self._run(["git", "add", "."], cwd=repo_dir)
        self._run(["git", "commit", "-m", "new retrieval"], cwd=repo_dir)
        new_commit = self._run(["git", "rev-parse", "HEAD"], cwd=repo_dir)

        return old_commit, new_commit, bundles

    def _write_fixture(
        self,
        fixtures_dir: Path,
        *,
        fixture_id: str,
        source_repo: Path,
        reference_commits: list[str],
        promise_paths: dict[str, str],
        omit_promise_key: str | None = None,
    ) -> None:
        lines = [
            "schema_version: FixtureManifest.v1",
            "produced_by: tests",
            f"fixture_id: {fixture_id}",
            "source_repo: tests",
            f"source_repo_path: {source_repo}",
            "source_branch: tests",
            "incident_id: incident-eval",
            "incident_artifact_path: diagnostics/incidents/incident-eval.md",
            "incident_evidence_path: diagnostics/inbox/incident-eval.json",
            "retrieval_artifact_path: diagnostics/retrieval_results/incident-eval.json",
            "reference_commits:",
        ]
        for commit in reference_commits:
            lines.append(f"  - {commit}")

        for key, value in promise_paths.items():
            if key == omit_promise_key:
                continue
            lines.append(f"{key}: {value}")

        fixtures_dir.mkdir(parents=True, exist_ok=True)
        (fixtures_dir / f"{fixture_id}.yaml").write_text("\n".join(lines) + "\n")

    def _prepare_eval_inputs(
        self,
        *,
        broken_loop_fixture: str | None = None,
        omit_promise_key: str | None = None,
        omit_promise_fixture: str | None = None,
    ) -> tuple[Path, Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        temp_root = Path(temp_dir.name)
        profiles_dir = temp_root / "profiles"
        fixtures_dir = temp_root / "fixtures"
        runs_dir = temp_root / "runs"
        source_repo = temp_root / "fixture_repo"

        for profile_id in REQUIRED_PROFILE_IDS:
            self._write_profile(profiles_dir, profile_id)

        old_commit, new_commit, bundles = self._init_lineage_repo(
            source_repo,
            broken_loop_fixture=broken_loop_fixture,
        )

        self._write_fixture(
            fixtures_dir,
            fixture_id="repotrace-current-incident",
            source_repo=source_repo,
            reference_commits=[],
            promise_paths=bundles["repotrace-current-incident"],
            omit_promise_key=omit_promise_key if omit_promise_fixture == "repotrace-current-incident" else None,
        )
        self._write_fixture(
            fixtures_dir,
            fixture_id="nutriplanner-collapse-case",
            source_repo=source_repo,
            reference_commits=[old_commit, new_commit],
            promise_paths=bundles["nutriplanner-collapse-case"],
            omit_promise_key=omit_promise_key if omit_promise_fixture == "nutriplanner-collapse-case" else None,
        )

        return profiles_dir, fixtures_dir, runs_dir

    def test_profile_loading_is_deterministic_and_dedupes_by_profile_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_dir = Path(temp_dir)
            for profile_id in REQUIRED_PROFILE_IDS:
                self._write_profile(profiles_dir, profile_id)

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
                required_profile_ids=REQUIRED_PROFILE_IDS,
            )

            self.assertEqual(
                [
                    "baseline_flat_retrieval",
                    "layered_plus_witnesses",
                    "layered_storage_only",
                    "promise_manual",
                ],
                [p["profile_id"] for p in profiles],
            )

    def test_profile_loading_enforces_required_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_dir = Path(temp_dir)
            for profile_id in (
                "baseline_flat_retrieval",
                "layered_storage_only",
                "layered_plus_witnesses",
            ):
                self._write_profile(profiles_dir, profile_id)

            with self.assertRaises(ValueError):
                load_experiment_profiles_v1(
                    profiles_dir,
                    required_profile_ids=REQUIRED_PROFILE_IDS,
                )

    def test_promise_manual_profile_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_dir = Path(temp_dir)
            for profile_id in REQUIRED_PROFILE_IDS:
                self._write_profile(profiles_dir, profile_id)

            profiles = load_experiment_profiles_v1(
                profiles_dir,
                required_profile_ids=REQUIRED_PROFILE_IDS,
            )
            promise_profile = next(profile for profile in profiles if profile["profile_id"] == "promise_manual")
            self.assertEqual("promise_manual", promise_profile["scoping_mode"])
            self.assertIsNone(promise_profile["promise_id"])
            self.assertIsNone(promise_profile["slice_key"])

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

    def test_fixture_execution_emits_metrics_for_all_profiles_including_promise_manual(self) -> None:
        profiles_dir, fixtures_dir, runs_dir = self._prepare_eval_inputs()

        metrics_path, summary_path, payload = run_evaluation(
            profiles_dir=profiles_dir,
            fixtures_dir=fixtures_dir,
            runs_dir=runs_dir,
            run_id="test-run",
        )

        self.assertTrue(metrics_path.exists())
        self.assertTrue(summary_path.exists())
        self.assertEqual("EvalHarnessRun.v1", payload["schema_version"])
        self.assertEqual(8, len(payload["results"]))

        for result in payload["results"]:
            self.assertIn(result["profile_id"], set(REQUIRED_PROFILE_IDS))
            self.assertIn(result["fixture_id"], {"repotrace-current-incident", "nutriplanner-collapse-case"})

            metrics = result["metrics"]
            for key in REQUIRED_METRIC_KEYS:
                self.assertIn(key, metrics)

            for normalized in result["normalized_attempts"]:
                self.assertTrue(
                    {
                        "attempt_id",
                        "verdict",
                        "candidate_count",
                        "has_discriminating_check",
                        "contradiction_items",
                        "source_shape",
                    }.issubset(set(normalized.keys()))
                )

        promise_manual = [result for result in payload["results"] if result["profile_id"] == "promise_manual"]
        self.assertEqual(2, len(promise_manual))
        for result in promise_manual:
            self.assertEqual("promise_manual", result["scoping_mode"])
            self.assertTrue(result["promise_id"])
            self.assertTrue(result["slice_key"])
            self.assertEqual("promise_manual_artifacts", result["normalized_attempts"][0]["source_shape"])
            self.assertTrue(result["metrics"]["promise_scope_present"])
            self.assertTrue(result["metrics"]["promise_slice_defined"])
            self.assertIn(result["metrics"]["scan_outcome"], {"anomaly_found", "blocked", "survives", "killed", "exhausted"})

    def test_fixture_resolution_infers_promise_id_when_registry_has_multiple_promises(self) -> None:
        profiles_dir, fixtures_dir, runs_dir = self._prepare_eval_inputs()

        _, _, payload = run_evaluation(
            profiles_dir=profiles_dir,
            fixtures_dir=fixtures_dir,
            runs_dir=runs_dir,
            run_id="test-run-promise-id",
        )

        repotrace_result = next(
            result
            for result in payload["results"]
            if result["fixture_id"] == "repotrace-current-incident" and result["profile_id"] == "promise_manual"
        )
        nutriplanner_result = next(
            result
            for result in payload["results"]
            if result["fixture_id"] == "nutriplanner-collapse-case" and result["profile_id"] == "promise_manual"
        )

        self.assertEqual("promise-repotrace", repotrace_result["promise_id"])
        self.assertEqual("promise-nutriplanner", nutriplanner_result["promise_id"])

    def test_semantic_loop_closed_correctness(self) -> None:
        profiles_dir, fixtures_dir, runs_dir = self._prepare_eval_inputs(
            broken_loop_fixture="repotrace-current-incident"
        )

        _, _, payload = run_evaluation(
            profiles_dir=profiles_dir,
            fixtures_dir=fixtures_dir,
            runs_dir=runs_dir,
            run_id="test-run-loop",
        )

        repotrace_result = next(
            result
            for result in payload["results"]
            if result["fixture_id"] == "repotrace-current-incident" and result["profile_id"] == "promise_manual"
        )
        nutriplanner_result = next(
            result
            for result in payload["results"]
            if result["fixture_id"] == "nutriplanner-collapse-case" and result["profile_id"] == "promise_manual"
        )

        self.assertFalse(repotrace_result["metrics"]["semantic_loop_closed"])
        self.assertTrue(nutriplanner_result["metrics"]["semantic_loop_closed"])

    def test_promise_manual_fails_when_required_artifacts_are_missing(self) -> None:
        profiles_dir, fixtures_dir, runs_dir = self._prepare_eval_inputs(
            omit_promise_key="promise_scan_outcome_path",
            omit_promise_fixture="repotrace-current-incident",
        )

        with self.assertRaises(ValueError):
            run_evaluation(
                profiles_dir=profiles_dir,
                fixtures_dir=fixtures_dir,
                runs_dir=runs_dir,
                run_id="test-run-missing",
            )

    def test_non_promise_profiles_remain_compatible(self) -> None:
        profiles_dir, fixtures_dir, runs_dir = self._prepare_eval_inputs()

        _, _, payload = run_evaluation(
            profiles_dir=profiles_dir,
            fixtures_dir=fixtures_dir,
            runs_dir=runs_dir,
            run_id="test-run-compat",
        )

        non_promise = [result for result in payload["results"] if result["profile_id"] != "promise_manual"]
        self.assertEqual(6, len(non_promise))

        for result in non_promise:
            self.assertEqual("none", result["scoping_mode"])
            self.assertIsNone(result["promise_id"])
            self.assertIsNone(result["slice_key"])
            self.assertIsNone(result["metrics"]["coverage_status_after_scan"])
            self.assertIsNone(result["metrics"]["task_completion_status"])
            self.assertIsNone(result["metrics"]["scan_outcome"])
            self.assertFalse(result["metrics"]["promise_scope_present"])
            self.assertFalse(result["metrics"]["semantic_loop_closed"])

        nutriplanner_baseline = next(
            result
            for result in non_promise
            if result["fixture_id"] == "nutriplanner-collapse-case"
            and result["profile_id"] == "baseline_flat_retrieval"
        )
        nutriplanner_storage = next(
            result
            for result in non_promise
            if result["fixture_id"] == "nutriplanner-collapse-case"
            and result["profile_id"] == "layered_storage_only"
        )
        self.assertEqual(1, nutriplanner_baseline["attempt_count"])
        self.assertEqual(2, nutriplanner_storage["attempt_count"])


if __name__ == "__main__":
    unittest.main()
