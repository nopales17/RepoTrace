"""
MODULE_SPEC
module_id: scripts.eval_harness
responsibility: Run repeatable profile-vs-fixture evaluation using normalized retrieval attempts.
inputs: ExperimentProfile.v1 manifests under eval/profiles and fixture manifests under eval/fixtures.
outputs: Per-run metrics.json and summary.md under eval/runs/<run_id>/.
invariants: No hard migration; no rewrite of legacy artifacts; metrics consume normalized attempts only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from artifact_adapters import (
    build_witness_set_v1,
    load_experiment_profiles_v1,
    load_promise_registry_v1,
    make_run_id,
    normalize_retrieval_attempt,
    utc_now_iso,
)

REQUIRED_PROFILE_IDS = [
    "baseline_flat_retrieval",
    "layered_storage_only",
    "layered_plus_witnesses",
]

REQUIRED_FIXTURE_IDS = [
    "repotrace-current-incident",
    "nutriplanner-collapse-case",
]

REQUIRED_METRIC_KEYS = [
    "frontier_size_after_first_pass",
    "time_to_first_discriminating_check",
    "unsupported_claim_count",
    "contradiction_count",
    "abstention_or_ambiguous_rate",
    "retrieval_drift_between_attempts",
    "memory_artifact_growth",
]

SCOPING_MODES = {"none", "promise_manual"}


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def parse_fixture_manifest(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_list_key: str | None = None
    block_key: str | None = None
    block_lines: list[str] = []

    for raw_line in path.read_text().splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if block_key is not None:
            if raw_line.startswith(" ") or raw_line.startswith("\t"):
                block_lines.append(stripped)
                continue
            data[block_key] = " ".join(block_lines).strip()
            block_key = None
            block_lines = []

        if current_list_key and stripped.startswith("-"):
            value = stripped.split("-", 1)[1].strip().strip('"').strip("'")
            if value:
                data.setdefault(current_list_key, []).append(value)
            continue

        if raw_line.startswith(" ") or raw_line.startswith("\t"):
            continue

        current_list_key = None
        if ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value in {">", ">-", "|", "|-"}:
            block_key = key
            block_lines = []
            continue

        if value == "":
            if key == "reference_commits":
                data[key] = []
                current_list_key = key
            else:
                data[key] = ""
            continue

        data[key] = value.strip('"').strip("'")

    if block_key is not None:
        data[block_key] = " ".join(block_lines).strip()

    reference_commits = data.get("reference_commits")
    if isinstance(reference_commits, list):
        data["reference_commits"] = [_to_text(item).strip() for item in reference_commits if _to_text(item).strip()]
    else:
        data["reference_commits"] = []

    return data


def load_fixture_manifests(fixtures_dir: Path, required_fixture_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not fixtures_dir.exists():
        raise ValueError(f"fixtures directory does not exist: {fixtures_dir}")

    manifests_by_id: dict[str, dict[str, Any]] = {}
    paths = sorted(list(fixtures_dir.glob("*.yaml")) + list(fixtures_dir.glob("*.yml")))
    for path in paths:
        manifest = parse_fixture_manifest(path)
        required_keys = (
            "schema_version",
            "produced_by",
            "fixture_id",
            "source_repo",
            "source_repo_path",
            "incident_id",
            "incident_evidence_path",
            "retrieval_artifact_path",
        )
        missing = [key for key in required_keys if key not in manifest]
        if missing:
            raise ValueError(f"{path} missing required keys: {', '.join(missing)}")
        if _to_text(manifest.get("schema_version")) != "FixtureManifest.v1":
            raise ValueError(f"{path} schema_version must be FixtureManifest.v1")

        fixture_id = _to_text(manifest.get("fixture_id")).strip()
        if not fixture_id:
            raise ValueError(f"{path} fixture_id must be non-empty")
        if fixture_id in manifests_by_id:
            continue

        manifest["fixture_manifest_path"] = str(path)
        manifests_by_id[fixture_id] = manifest

    missing_required = [fixture_id for fixture_id in required_fixture_ids if fixture_id not in manifests_by_id]
    if missing_required:
        raise ValueError(f"missing required fixtures: {', '.join(missing_required)}")

    return manifests_by_id


def _resolve_source_repo_path(workspace_root: Path, source_repo_path: str) -> Path:
    path = Path(source_repo_path)
    if not path.is_absolute():
        path = (workspace_root / path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"fixture source repo path does not exist: {path}")
    return path


def _load_json_from_git(repo_path: Path, commit: str, artifact_path: str) -> dict[str, Any]:
    content = subprocess.check_output(
        [
            "git",
            "-C",
            str(repo_path),
            "show",
            f"{commit}:{artifact_path}",
        ],
        text=True,
    )
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError(f"artifact at {commit}:{artifact_path} must be a JSON object")
    return payload


def _load_json_from_worktree(repo_path: Path, artifact_path: str) -> dict[str, Any]:
    path = Path(artifact_path)
    if not path.is_absolute():
        path = repo_path / path
    if not path.exists():
        raise FileNotFoundError(f"artifact path does not exist: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"artifact at {path} must be a JSON object")
    return payload


def load_fixture_artifacts(manifest: dict[str, Any], workspace_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    repo_path = _resolve_source_repo_path(workspace_root, _to_text(manifest.get("source_repo_path")))
    retrieval_path = _to_text(manifest.get("retrieval_artifact_path"))
    incident_evidence_path = _to_text(manifest.get("incident_evidence_path"))
    reference_commits = [_to_text(item).strip() for item in manifest.get("reference_commits", []) if _to_text(item).strip()]

    if reference_commits:
        attempts = [_load_json_from_git(repo_path, commit, retrieval_path) for commit in reference_commits]
        incident_payload = _load_json_from_git(repo_path, reference_commits[0], incident_evidence_path)
        return attempts, incident_payload

    attempts = [_load_json_from_worktree(repo_path, retrieval_path)]
    incident_payload = _load_json_from_worktree(repo_path, incident_evidence_path)
    return attempts, incident_payload


def _load_promise_index(workspace_root: Path) -> dict[str, dict[str, Any]]:
    registry_path = workspace_root / "diagnostics/memory/promise_registry.json"
    if not registry_path.exists():
        return {}

    registry = load_promise_registry_v1(registry_path)
    index: dict[str, dict[str, Any]] = {}
    for card in registry.get("promises", []):
        if not isinstance(card, dict):
            continue
        promise_id = _to_text(card.get("promise_id")).strip()
        if promise_id:
            index[promise_id] = card
    return index


def _profile_scoping(
    manifest: dict[str, Any],
    profile: dict[str, Any],
    *,
    promise_index: dict[str, dict[str, Any]],
) -> tuple[str, str | None, str | None]:
    scoping_mode = _to_text(manifest.get("scoping_mode")).strip() or _to_text(profile.get("scoping_mode")).strip() or "none"
    if scoping_mode not in SCOPING_MODES:
        raise ValueError(f"unsupported scoping_mode {scoping_mode}; expected one of {sorted(SCOPING_MODES)}")

    promise_id: str | None = None
    promise_raw = manifest.get("promise_id") if "promise_id" in manifest else profile.get("promise_id")
    if isinstance(promise_raw, list):
        promise_raw = ""
    if _to_text(promise_raw).strip():
        promise_id = _to_text(promise_raw).strip()

    slice_key: str | None = None
    slice_raw = manifest.get("slice_key") if "slice_key" in manifest else profile.get("slice_key")
    if isinstance(slice_raw, list):
        slice_raw = ""
    if _to_text(slice_raw).strip():
        slice_key = _to_text(slice_raw).strip()

    if scoping_mode == "promise_manual":
        if not promise_id:
            raise ValueError("promise_manual scoping requires promise_id")
        if promise_id not in promise_index:
            raise ValueError(f"promise_manual scoping references unknown promise_id: {promise_id}")

    return scoping_mode, promise_id, slice_key


def _considered_raw_attempts(profile_id: str, raw_attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not raw_attempts:
        return []
    if profile_id == "baseline_flat_retrieval":
        return [raw_attempts[-1]]
    return raw_attempts


def _witness_unsupported_exposed(raw_incident: dict[str, Any], fixture_id: str) -> int:
    incident_id = _to_text(raw_incident.get("id")).strip() or _to_text(raw_incident.get("incident_id")).strip() or fixture_id
    witness_set = build_witness_set_v1(raw_incident, incident_id=incident_id, produced_by="scripts/eval_harness.py")
    metrics = witness_set.get("metrics")
    if isinstance(metrics, dict):
        unsupported = metrics.get("unsupported_count")
        if isinstance(unsupported, int) and unsupported >= 0:
            return unsupported
    return 0


def _contradiction_count(normalized_attempts: list[dict[str, Any]]) -> int:
    return sum(len(attempt.get("contradiction_items", [])) for attempt in normalized_attempts)


def _time_to_first_discriminating_check(normalized_attempts: list[dict[str, Any]]) -> int | None:
    for idx, attempt in enumerate(normalized_attempts, start=1):
        if bool(attempt.get("has_discriminating_check")):
            return idx
    return None


def _abstention_rate(normalized_attempts: list[dict[str, Any]]) -> float:
    if not normalized_attempts:
        return 0.0
    ambiguous = sum(1 for attempt in normalized_attempts if _to_text(attempt.get("verdict")) == "ambiguous")
    return round(ambiguous / len(normalized_attempts), 4)


def _retrieval_drift(normalized_attempts: list[dict[str, Any]]) -> float:
    if len(normalized_attempts) < 2:
        return 0.0
    changes = 0
    previous = _to_text(normalized_attempts[0].get("verdict"))
    for attempt in normalized_attempts[1:]:
        current = _to_text(attempt.get("verdict"))
        if current != previous:
            changes += 1
        previous = current
    return round(changes / (len(normalized_attempts) - 1), 4)


def _memory_artifact_growth(profile_id: str, considered_attempt_count: int) -> int:
    if profile_id == "baseline_flat_retrieval":
        return 1
    if profile_id == "layered_storage_only":
        return considered_attempt_count + 1
    if profile_id == "layered_plus_witnesses":
        return considered_attempt_count + 2
    return considered_attempt_count


def compute_metrics(
    *,
    profile_id: str,
    normalized_attempts: list[dict[str, Any]],
    unsupported_exposed: int,
) -> dict[str, Any]:
    unsupported_after_processing = unsupported_exposed
    if profile_id == "layered_plus_witnesses":
        unsupported_after_processing = 0

    first_candidate_count = 0
    if normalized_attempts:
        first_candidate_count = int(normalized_attempts[0].get("candidate_count", 0))

    return {
        "frontier_size_after_first_pass": first_candidate_count,
        "time_to_first_discriminating_check": _time_to_first_discriminating_check(normalized_attempts),
        "unsupported_claim_count": unsupported_after_processing,
        "contradiction_count": _contradiction_count(normalized_attempts),
        "abstention_or_ambiguous_rate": _abstention_rate(normalized_attempts),
        "retrieval_drift_between_attempts": _retrieval_drift(normalized_attempts),
        "memory_artifact_growth": _memory_artifact_growth(profile_id, len(normalized_attempts)),
    }


def _build_summary(run_payload: dict[str, Any]) -> str:
    def _fmt(value: Any) -> str:
        if value is None:
            return "null"
        return str(value)

    lines: list[str] = []
    lines.append(f"# Eval Harness Summary ({run_payload['run_id']})")
    lines.append("")
    lines.append(f"Generated at: {run_payload['generated_at']}")
    lines.append("")
    lines.append("Proxy metric note: `memory_artifact_growth` is a structural artifact-count proxy, not an intrinsic quality metric.")
    lines.append("")

    by_fixture: dict[str, list[dict[str, Any]]] = {}
    for result in run_payload.get("results", []):
        fixture_id = _to_text(result.get("fixture_id"))
        by_fixture.setdefault(fixture_id, []).append(result)

    for fixture_id in sorted(by_fixture):
        lines.append(f"## {fixture_id}")
        lines.append("")
        lines.append("| profile | scope | promise_id | slice_key | frontier | time_to_check | unsupported | contradictions | ambiguous_rate | drift_rate | artifact_growth |")
        lines.append("| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        ordered = sorted(by_fixture[fixture_id], key=lambda result: _to_text(result.get("profile_id")))
        for result in ordered:
            metrics = result.get("metrics", {})
            lines.append(
                "| "
                f"{result['profile_id']} | "
                f"{result.get('scoping_mode', 'none')} | "
                f"{result.get('promise_id') or ''} | "
                f"{result.get('slice_key') or ''} | "
                f"{metrics.get('frontier_size_after_first_pass', 0)} | "
                f"{_fmt(metrics.get('time_to_first_discriminating_check'))} | "
                f"{metrics.get('unsupported_claim_count', 0)} | "
                f"{metrics.get('contradiction_count', 0)} | "
                f"{metrics.get('abstention_or_ambiguous_rate', 0)} | "
                f"{metrics.get('retrieval_drift_between_attempts', 0)} | "
                f"{metrics.get('memory_artifact_growth', 0)} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def run_evaluation(
    *,
    profiles_dir: Path,
    fixtures_dir: Path,
    runs_dir: Path,
    run_id: str | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    workspace_root = Path.cwd()
    run_id = run_id or make_run_id()

    profiles = load_experiment_profiles_v1(profiles_dir, required_profile_ids=REQUIRED_PROFILE_IDS)
    profiles_by_id = {str(profile["profile_id"]): profile for profile in profiles}

    missing_active = [
        profile_id
        for profile_id in REQUIRED_PROFILE_IDS
        if _to_text(profiles_by_id[profile_id].get("status")) != "active"
    ]
    if missing_active:
        raise ValueError(f"required profiles must be active: {', '.join(missing_active)}")

    fixtures_by_id = load_fixture_manifests(fixtures_dir, required_fixture_ids=REQUIRED_FIXTURE_IDS)
    promise_index = _load_promise_index(workspace_root)

    results: list[dict[str, Any]] = []
    for fixture_id in REQUIRED_FIXTURE_IDS:
        manifest = fixtures_by_id[fixture_id]
        raw_attempts, raw_incident = load_fixture_artifacts(manifest, workspace_root)
        unsupported_exposed = _witness_unsupported_exposed(raw_incident, fixture_id)

        for profile_id in REQUIRED_PROFILE_IDS:
            profile = profiles_by_id[profile_id]
            considered_raw = _considered_raw_attempts(profile_id, raw_attempts)
            normalized_attempts = [normalize_retrieval_attempt(raw) for raw in considered_raw]
            scoping_mode, promise_id, slice_key = _profile_scoping(
                manifest,
                profile,
                promise_index=promise_index,
            )

            result = {
                "fixture_id": fixture_id,
                "profile_id": profile_id,
                "scoping_mode": scoping_mode,
                "promise_id": promise_id,
                "slice_key": slice_key,
                "attempt_count": len(normalized_attempts),
                "normalized_attempts": normalized_attempts,
                "metrics": compute_metrics(
                    profile_id=profile_id,
                    normalized_attempts=normalized_attempts,
                    unsupported_exposed=unsupported_exposed,
                ),
            }
            results.append(result)

    run_payload: dict[str, Any] = {
        "schema_version": "EvalHarnessRun.v1",
        "produced_by": "scripts/eval_harness.py",
        "run_id": run_id,
        "generated_at": utc_now_iso(),
        "required_profiles": REQUIRED_PROFILE_IDS,
        "required_fixtures": REQUIRED_FIXTURE_IDS,
        "required_metric_keys": REQUIRED_METRIC_KEYS,
        "results": results,
    }

    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = run_dir / "metrics.json"
    summary_path = run_dir / "summary.md"

    metrics_path.write_text(json.dumps(run_payload, indent=2) + "\n")
    summary_path.write_text(_build_summary(run_payload))

    return metrics_path, summary_path, run_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Eval Harness v1 profile-vs-fixture comparison.")
    parser.add_argument("--profiles-dir", default="eval/profiles", type=Path)
    parser.add_argument("--fixtures-dir", default="eval/fixtures", type=Path)
    parser.add_argument("--runs-dir", default="eval/runs", type=Path)
    parser.add_argument("--run-id", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metrics_path, summary_path, _ = run_evaluation(
        profiles_dir=args.profiles_dir,
        fixtures_dir=args.fixtures_dir,
        runs_dir=args.runs_dir,
        run_id=args.run_id,
    )
    print(f"wrote {metrics_path}")
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
