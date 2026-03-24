"""
MODULE_SPEC
module_id: scripts.eval_harness
responsibility: Run repeatable profile-vs-fixture evaluation using normalized retrieval attempts and manual promise artifacts.
inputs: ExperimentProfile.v1 manifests under eval/profiles and fixture manifests under eval/fixtures.
outputs: Per-run metrics.json and summary.md under eval/runs/<run_id>/.
invariants: No hard migration; no rewrite of legacy artifacts; retrieval profiles consume normalized attempts; promise_manual consumes explicit promise artifacts.
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
    load_promise_coverage_ledger_v1,
    load_promise_frame_checkpoint_v1,
    load_promise_registry_v1,
    load_promise_scan_outcome_v1,
    load_promise_traversal_task_v1,
    make_run_id,
    normalize_retrieval_attempt,
    utc_now_iso,
)

REQUIRED_PROFILE_IDS = [
    "baseline_flat_retrieval",
    "layered_storage_only",
    "layered_plus_witnesses",
    "promise_manual",
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
    "promise_scope_present",
    "promise_slice_defined",
    "coverage_status_after_scan",
    "task_completion_status",
    "scan_outcome",
    "anomaly_count",
    "semantic_loop_closed",
]

SCOPING_MODES = {"none", "promise_manual"}
PROMISE_OUTCOME_TO_VERDICT = {
    "anomaly_found": "motif_match",
    "survives": "motif_non_match",
    "killed": "motif_non_match",
    "blocked": "ambiguous",
    "exhausted": "ambiguous",
}
PROMISE_MANUAL_PATH_KEYS = {
    "promise_registry_path",
    "promise_registry_entry_path",
    "promise_frame_checkpoint_path",
    "promise_traversal_task_path",
    "promise_scan_outcome_path",
    "promise_coverage_ledger_path",
}
PROMISE_MANUAL_REQUIRED_PATH_KEYS = (
    "promise_frame_checkpoint_path",
    "promise_traversal_task_path",
    "promise_scan_outcome_path",
    "promise_coverage_ledger_path",
)


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


def _profile_setting(manifest: dict[str, Any], profile: dict[str, Any], key: str) -> Any:
    if key in manifest:
        return manifest.get(key)
    return profile.get(key)


def _profile_scoping(manifest: dict[str, Any], profile: dict[str, Any]) -> tuple[str, str | None, str | None]:
    scoping_mode = _to_text(profile.get("scoping_mode")).strip() or _to_text(manifest.get("scoping_mode")).strip() or "none"
    if scoping_mode not in SCOPING_MODES:
        raise ValueError(f"unsupported scoping_mode {scoping_mode}; expected one of {sorted(SCOPING_MODES)}")

    promise_id: str | None = None
    promise_raw = _profile_setting(manifest, profile, "promise_id")
    if isinstance(promise_raw, list):
        promise_raw = ""
    if _to_text(promise_raw).strip():
        promise_id = _to_text(promise_raw).strip()

    slice_key: str | None = None
    slice_raw = _profile_setting(manifest, profile, "slice_key")
    if isinstance(slice_raw, list):
        slice_raw = ""
    if _to_text(slice_raw).strip():
        slice_key = _to_text(slice_raw).strip()

    return scoping_mode, promise_id, slice_key


def _resolve_artifact_path(
    *,
    workspace_root: Path,
    repo_path: Path,
    raw_path: str,
    field_name: str,
) -> Path:
    path = Path(raw_path)
    candidates: list[Path] = []
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.append((repo_path / path).resolve())
        candidates.append((workspace_root / path).resolve())

    for candidate in candidates:
        if candidate.exists():
            return candidate

    if path.is_absolute():
        raise FileNotFoundError(f"{field_name} path does not exist: {path}")
    raise FileNotFoundError(
        f"{field_name} path does not exist under source repo or workspace: {raw_path}"
    )


def _load_json_object(path: Path, field_name: str) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{field_name} must point to a JSON object: {path}")
    return payload


def _load_promise_registry_entry(path: Path) -> dict[str, Any]:
    payload = _load_json_object(path, "promise_registry_entry_path")
    schema_version = _to_text(payload.get("schema_version")).strip()

    if schema_version == "PromiseSchema.v1":
        promise = payload.get("promise")
        if not isinstance(promise, dict):
            raise ValueError(f"promise_registry_entry_path PromiseSchema.v1 must include promise object: {path}")
        return dict(promise)

    if schema_version == "PromiseRegistry.v1":
        registry = load_promise_registry_v1(path)
        promises = registry.get("promises", [])
        if len(promises) != 1:
            raise ValueError(
                f"promise_registry_entry_path points to registry with {len(promises)} promises; expected exactly 1"
            )
        promise = promises[0]
        if not isinstance(promise, dict):
            raise ValueError(f"promise_registry_entry_path registry entry must be an object: {path}")
        return dict(promise)

    if _to_text(payload.get("promise_id")).strip():
        return dict(payload)

    raise ValueError(
        f"promise_registry_entry_path must be PromiseSchema.v1, single-entry PromiseRegistry.v1, or a promise card: {path}"
    )


def _resolve_slice_from_artifacts(
    frame: dict[str, Any],
    task: dict[str, Any],
    outcome: dict[str, Any],
) -> tuple[str, str]:
    interaction_family = (
        _to_text(outcome.get("interaction_family")).strip()
        or _to_text(task.get("interaction_family")).strip()
        or _to_text(frame.get("interaction_family")).strip()
    )
    consistency_boundary = (
        _to_text(outcome.get("consistency_boundary")).strip()
        or _to_text(task.get("consistency_boundary")).strip()
        or _to_text(frame.get("consistency_boundary")).strip()
    )
    return interaction_family, consistency_boundary


def _find_coverage_cell(
    coverage_ledger: dict[str, Any],
    *,
    promise_id: str,
    interaction_family: str,
    consistency_boundary: str,
) -> dict[str, Any] | None:
    coverage = coverage_ledger.get("coverage")
    if not isinstance(coverage, list):
        return None

    for cell in coverage:
        if not isinstance(cell, dict):
            continue
        if _to_text(cell.get("promise_id")).strip() != promise_id:
            continue
        if _to_text(cell.get("interaction_family")).strip() != interaction_family:
            continue
        if _to_text(cell.get("consistency_boundary")).strip() != consistency_boundary:
            continue
        return cell

    return None


def _load_fixture_promise_manual_context(
    *,
    manifest: dict[str, Any],
    profile: dict[str, Any],
    workspace_root: Path,
    explicit_promise_id: str | None,
    explicit_slice_key: str | None,
) -> dict[str, Any]:
    repo_path = _resolve_source_repo_path(workspace_root, _to_text(manifest.get("source_repo_path")))

    raw_paths: dict[str, str] = {}
    for key in PROMISE_MANUAL_PATH_KEYS:
        raw_value = _profile_setting(manifest, profile, key)
        raw_paths[key] = _to_text(raw_value).strip()

    missing_required = [key for key in PROMISE_MANUAL_REQUIRED_PATH_KEYS if not raw_paths.get(key)]
    if missing_required:
        raise ValueError(
            "promise_manual fixture missing required promise artifact paths: "
            + ", ".join(sorted(missing_required))
        )

    if not raw_paths.get("promise_registry_path") and not raw_paths.get("promise_registry_entry_path"):
        raise ValueError("promise_manual requires promise_registry_path or promise_registry_entry_path")

    resolved_paths: dict[str, Path] = {}
    for key, raw_path in raw_paths.items():
        if not raw_path:
            continue
        resolved_paths[key] = _resolve_artifact_path(
            workspace_root=workspace_root,
            repo_path=repo_path,
            raw_path=raw_path,
            field_name=key,
        )

    registry_payload: dict[str, Any] | None = None
    registry_cards: dict[str, dict[str, Any]] = {}
    if "promise_registry_path" in resolved_paths:
        registry_payload = load_promise_registry_v1(resolved_paths["promise_registry_path"])
        for card in registry_payload.get("promises", []):
            if not isinstance(card, dict):
                continue
            promise_id = _to_text(card.get("promise_id")).strip()
            if promise_id:
                registry_cards[promise_id] = card

    registry_entry: dict[str, Any] | None = None
    if "promise_registry_entry_path" in resolved_paths:
        registry_entry = _load_promise_registry_entry(resolved_paths["promise_registry_entry_path"])

    frame = load_promise_frame_checkpoint_v1(resolved_paths["promise_frame_checkpoint_path"])
    task = load_promise_traversal_task_v1(resolved_paths["promise_traversal_task_path"])
    outcome = load_promise_scan_outcome_v1(resolved_paths["promise_scan_outcome_path"])
    coverage_ledger = load_promise_coverage_ledger_v1(resolved_paths["promise_coverage_ledger_path"])

    candidate_promise_ids: set[str] = set()
    for candidate in (
        explicit_promise_id,
        _to_text(frame.get("promise_id")).strip(),
        _to_text(task.get("promise_id")).strip(),
        _to_text(outcome.get("promise_id")).strip(),
        _to_text(registry_entry.get("promise_id")).strip() if isinstance(registry_entry, dict) else "",
    ):
        if candidate:
            candidate_promise_ids.add(candidate)

    if len(registry_cards) == 1:
        candidate_promise_ids.add(next(iter(registry_cards.keys())))

    if explicit_promise_id:
        resolved_promise_id = explicit_promise_id
        conflicting = [candidate for candidate in candidate_promise_ids if candidate and candidate != explicit_promise_id]
        if conflicting:
            raise ValueError(
                "promise_manual artifacts conflict with explicit promise_id: "
                + ", ".join(sorted(conflicting))
            )
    else:
        if len(candidate_promise_ids) != 1:
            raise ValueError(
                "promise_manual requires promise_id unless artifacts imply exactly one promise; "
                f"found {len(candidate_promise_ids)} candidates"
            )
        resolved_promise_id = next(iter(candidate_promise_ids))

    if registry_entry is not None:
        registry_entry_id = _to_text(registry_entry.get("promise_id")).strip()
        if registry_entry_id and registry_entry_id != resolved_promise_id:
            raise ValueError(
                f"promise_registry_entry_path promise_id {registry_entry_id} does not match resolved promise_id {resolved_promise_id}"
            )

    promise_card = registry_entry
    if promise_card is None and registry_cards:
        promise_card = registry_cards.get(resolved_promise_id)
        if promise_card is None:
            raise ValueError(
                f"promise_registry_path does not include resolved promise_id: {resolved_promise_id}"
            )

    interaction_family, consistency_boundary = _resolve_slice_from_artifacts(frame, task, outcome)
    if not interaction_family or not consistency_boundary:
        raise ValueError(
            "promise_manual requires interaction_family and consistency_boundary across frame/task/outcome artifacts"
        )

    coverage_cell = _find_coverage_cell(
        coverage_ledger,
        promise_id=resolved_promise_id,
        interaction_family=interaction_family,
        consistency_boundary=consistency_boundary,
    )
    if coverage_cell is None:
        raise ValueError(
            "promise_manual coverage ledger is missing slice cell for "
            f"{resolved_promise_id} | {interaction_family} | {consistency_boundary}"
        )

    resolved_slice_key = explicit_slice_key or f"{interaction_family}::{consistency_boundary}"

    artifact_count = 5
    if "promise_registry_path" in resolved_paths:
        artifact_count += 1
    if "promise_registry_entry_path" in resolved_paths:
        artifact_count += 1

    return {
        "promise_id": resolved_promise_id,
        "slice_key": resolved_slice_key,
        "promise_card": promise_card,
        "frame": frame,
        "task": task,
        "outcome": outcome,
        "coverage_cell": coverage_cell,
        "artifact_count": artifact_count,
    }


def _semantic_loop_closed(context: dict[str, Any]) -> bool:
    frame = context["frame"]
    task = context["task"]
    outcome = context["outcome"]
    coverage_cell = context["coverage_cell"]
    promise_id = _to_text(context.get("promise_id")).strip()

    key_tuple = (
        _to_text(frame.get("interaction_family")).strip(),
        _to_text(frame.get("consistency_boundary")).strip(),
    )
    task_key_tuple = (
        _to_text(task.get("interaction_family")).strip(),
        _to_text(task.get("consistency_boundary")).strip(),
    )
    outcome_key_tuple = (
        _to_text(outcome.get("interaction_family")).strip(),
        _to_text(outcome.get("consistency_boundary")).strip(),
    )
    coverage_key_tuple = (
        _to_text(coverage_cell.get("interaction_family")).strip(),
        _to_text(coverage_cell.get("consistency_boundary")).strip(),
    )

    if not promise_id:
        return False

    return all(
        [
            _to_text(frame.get("promise_id")).strip() == promise_id,
            _to_text(task.get("promise_id")).strip() == promise_id,
            _to_text(outcome.get("promise_id")).strip() == promise_id,
            _to_text(coverage_cell.get("promise_id")).strip() == promise_id,
            _to_text(task.get("assigned_frame_id")).strip() == _to_text(frame.get("frame_id")).strip(),
            _to_text(outcome.get("frame_id")).strip() == _to_text(frame.get("frame_id")).strip(),
            _to_text(outcome.get("task_id")).strip() == _to_text(task.get("task_id")).strip(),
            key_tuple == task_key_tuple,
            key_tuple == outcome_key_tuple,
            key_tuple == coverage_key_tuple,
            _to_text(outcome.get("resulting_coverage_status")).strip() == _to_text(coverage_cell.get("status")).strip(),
            _to_text(outcome.get("resulting_task_status")).strip() in {"queued", "active", "blocked", "done"},
        ]
    )


def _promise_manual_normalized_attempt(context: dict[str, Any]) -> dict[str, Any]:
    frame = context["frame"]
    outcome = context["outcome"]

    witness_ids = frame.get("witness_ids")
    contradiction_items: list[str] = []
    if isinstance(witness_ids, dict):
        contradiction_items = [_to_text(item).strip() for item in witness_ids.get("contradiction", []) if _to_text(item).strip()]

    touchpoints = frame.get("touchpoints_remaining") if isinstance(frame.get("touchpoints_remaining"), list) else []
    pressure_axes = frame.get("pressure_axes_remaining") if isinstance(frame.get("pressure_axes_remaining"), list) else []
    frontier_size = len(touchpoints) + len(pressure_axes)

    raw_outcome = _to_text(outcome.get("outcome")).strip()
    verdict = PROMISE_OUTCOME_TO_VERDICT.get(raw_outcome, "ambiguous")

    next_check = frame.get("next_check")
    has_discriminating_check = False
    if isinstance(next_check, dict):
        has_discriminating_check = bool(_to_text(next_check.get("prompt")).strip())

    return {
        "attempt_id": _to_text(outcome.get("outcome_id")).strip() or _to_text(outcome.get("task_id")).strip() or "promise-manual",
        "verdict": verdict,
        "candidate_count": frontier_size,
        "has_discriminating_check": has_discriminating_check,
        "contradiction_items": contradiction_items,
        "source_shape": "promise_manual_artifacts",
    }


def _default_promise_process_metrics(*, promise_id: str | None, slice_key: str | None) -> dict[str, Any]:
    return {
        "promise_scope_present": bool(promise_id),
        "promise_slice_defined": bool(slice_key),
        "coverage_status_after_scan": None,
        "task_completion_status": None,
        "scan_outcome": None,
        "anomaly_count": 0,
        "semantic_loop_closed": False,
    }


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
    promise_id: str | None,
    slice_key: str | None,
) -> dict[str, Any]:
    unsupported_after_processing = unsupported_exposed
    if profile_id == "layered_plus_witnesses":
        unsupported_after_processing = 0

    first_candidate_count = 0
    if normalized_attempts:
        first_candidate_count = int(normalized_attempts[0].get("candidate_count", 0))

    metrics = {
        "frontier_size_after_first_pass": first_candidate_count,
        "time_to_first_discriminating_check": _time_to_first_discriminating_check(normalized_attempts),
        "unsupported_claim_count": unsupported_after_processing,
        "contradiction_count": _contradiction_count(normalized_attempts),
        "abstention_or_ambiguous_rate": _abstention_rate(normalized_attempts),
        "retrieval_drift_between_attempts": _retrieval_drift(normalized_attempts),
        "memory_artifact_growth": _memory_artifact_growth(profile_id, len(normalized_attempts)),
    }
    metrics.update(_default_promise_process_metrics(promise_id=promise_id, slice_key=slice_key))
    return metrics


def compute_promise_manual_metrics(context: dict[str, Any]) -> dict[str, Any]:
    frame = context["frame"]
    task = context["task"]
    outcome = context["outcome"]
    coverage_cell = context["coverage_cell"]

    touchpoints = frame.get("touchpoints_remaining") if isinstance(frame.get("touchpoints_remaining"), list) else []
    pressure_axes = frame.get("pressure_axes_remaining") if isinstance(frame.get("pressure_axes_remaining"), list) else []
    frontier_size = len(touchpoints) + len(pressure_axes)

    witness_ids = frame.get("witness_ids")
    contradictions = []
    if isinstance(witness_ids, dict):
        contradictions = [_to_text(item).strip() for item in witness_ids.get("contradiction", []) if _to_text(item).strip()]

    next_check = frame.get("next_check")
    has_discriminating_check = False
    if isinstance(next_check, dict):
        has_discriminating_check = bool(_to_text(next_check.get("prompt")).strip())

    scan_outcome = _to_text(outcome.get("outcome")).strip()
    abstention_rate = 1.0 if scan_outcome in {"blocked", "exhausted"} else 0.0

    task_completion_status = _to_text(outcome.get("resulting_task_status")).strip() or _to_text(task.get("status")).strip()

    return {
        "frontier_size_after_first_pass": frontier_size,
        "time_to_first_discriminating_check": 1 if has_discriminating_check else None,
        "unsupported_claim_count": 0,
        "contradiction_count": len(contradictions),
        "abstention_or_ambiguous_rate": abstention_rate,
        "retrieval_drift_between_attempts": 0.0,
        "memory_artifact_growth": int(context.get("artifact_count", 5)),
        "promise_scope_present": bool(context.get("promise_card")) and bool(context.get("promise_id")),
        "promise_slice_defined": bool(context.get("slice_key")),
        "coverage_status_after_scan": _to_text(coverage_cell.get("status")).strip() or None,
        "task_completion_status": task_completion_status or None,
        "scan_outcome": scan_outcome or None,
        "anomaly_count": len([item for item in outcome.get("anomaly_ids", []) if _to_text(item).strip()]),
        "semantic_loop_closed": _semantic_loop_closed(context),
    }


def _build_summary(run_payload: dict[str, Any]) -> str:
    def _fmt(value: Any) -> str:
        if value is None:
            return "null"
        return str(value)

    profile_order = {profile_id: idx for idx, profile_id in enumerate(REQUIRED_PROFILE_IDS)}

    lines: list[str] = []
    lines.append(f"# Eval Harness Summary ({run_payload['run_id']})")
    lines.append("")
    lines.append(f"Generated at: {run_payload['generated_at']}")
    lines.append("")
    lines.append("What is measured:")
    lines.append("- `baseline_flat_retrieval`, `layered_storage_only`, and `layered_plus_witnesses` are computed from retrieval lineage snapshots.")
    lines.append("- `promise_manual` is computed only from manual promise artifacts (registry + frame + task + scan outcome + coverage ledger).")
    lines.append("")
    lines.append("What is not measured:")
    lines.append("- No autonomous promise traversal, task generation, scheduler behavior, or predictive routing is measured.")
    lines.append("- `memory_artifact_growth` and retrieval-style rates remain structural proxies, not intrinsic correctness scores.")
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

        fixture_results = sorted(
            by_fixture[fixture_id],
            key=lambda result: profile_order.get(_to_text(result.get("profile_id")), 999),
        )
        by_profile = {str(result["profile_id"]): result for result in fixture_results}

        for result in fixture_results:
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

        promise_manual = by_profile.get("promise_manual")
        if promise_manual:
            pm_metrics = promise_manual.get("metrics", {})
            lines.append("Promise-manual process metrics:")
            lines.append("")
            lines.append("| scope_present | slice_defined | coverage_status_after_scan | task_completion_status | scan_outcome | anomaly_count | semantic_loop_closed |")
            lines.append("| --- | --- | --- | --- | --- | ---: | --- |")
            lines.append(
                "| "
                f"{pm_metrics.get('promise_scope_present', False)} | "
                f"{pm_metrics.get('promise_slice_defined', False)} | "
                f"{_fmt(pm_metrics.get('coverage_status_after_scan'))} | "
                f"{_fmt(pm_metrics.get('task_completion_status'))} | "
                f"{_fmt(pm_metrics.get('scan_outcome'))} | "
                f"{pm_metrics.get('anomaly_count', 0)} | "
                f"{pm_metrics.get('semantic_loop_closed', False)} |"
            )
            lines.append("")

            lines.append("promise_manual comparison against retrieval profiles:")
            for retrieval_profile in (
                "baseline_flat_retrieval",
                "layered_storage_only",
                "layered_plus_witnesses",
            ):
                other = by_profile.get(retrieval_profile)
                if not other:
                    continue
                other_metrics = other.get("metrics", {})
                lines.append(
                    "- "
                    f"vs `{retrieval_profile}`: frontier {pm_metrics.get('frontier_size_after_first_pass', 0)} vs {other_metrics.get('frontier_size_after_first_pass', 0)}, "
                    f"contradictions {pm_metrics.get('contradiction_count', 0)} vs {other_metrics.get('contradiction_count', 0)}, "
                    f"ambiguous_rate {pm_metrics.get('abstention_or_ambiguous_rate', 0)} vs {other_metrics.get('abstention_or_ambiguous_rate', 0)}."
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

    results: list[dict[str, Any]] = []
    for fixture_id in REQUIRED_FIXTURE_IDS:
        manifest = fixtures_by_id[fixture_id]
        raw_attempts, raw_incident = load_fixture_artifacts(manifest, workspace_root)
        unsupported_exposed = _witness_unsupported_exposed(raw_incident, fixture_id)

        for profile_id in REQUIRED_PROFILE_IDS:
            profile = profiles_by_id[profile_id]
            scoping_mode, scoped_promise_id, scoped_slice_key = _profile_scoping(manifest, profile)

            if profile_id == "promise_manual":
                if scoping_mode != "promise_manual":
                    raise ValueError("promise_manual profile must run with scoping_mode=promise_manual")

                context = _load_fixture_promise_manual_context(
                    manifest=manifest,
                    profile=profile,
                    workspace_root=workspace_root,
                    explicit_promise_id=scoped_promise_id,
                    explicit_slice_key=scoped_slice_key,
                )
                normalized_attempts = [_promise_manual_normalized_attempt(context)]
                metrics = compute_promise_manual_metrics(context)
                result_promise_id = _to_text(context.get("promise_id")).strip() or None
                result_slice_key = _to_text(context.get("slice_key")).strip() or None
            else:
                considered_raw = _considered_raw_attempts(profile_id, raw_attempts)
                normalized_attempts = [normalize_retrieval_attempt(raw) for raw in considered_raw]
                metrics = compute_metrics(
                    profile_id=profile_id,
                    normalized_attempts=normalized_attempts,
                    unsupported_exposed=unsupported_exposed,
                    promise_id=scoped_promise_id,
                    slice_key=scoped_slice_key,
                )
                result_promise_id = scoped_promise_id
                result_slice_key = scoped_slice_key

            result = {
                "fixture_id": fixture_id,
                "profile_id": profile_id,
                "scoping_mode": scoping_mode,
                "promise_id": result_promise_id,
                "slice_key": result_slice_key,
                "attempt_count": len(normalized_attempts),
                "normalized_attempts": normalized_attempts,
                "metrics": metrics,
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
