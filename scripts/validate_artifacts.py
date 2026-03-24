import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_BY_SCHEMA: dict[str, list[str]] = {
    "Incident.v1": [
        "incident_id",
        "append_only",
        "witness_set",
        "witness_ids",
    ],
    "WitnessSet.v1": [
        "incident_id",
        "metrics",
        "witnesses",
    ],
    "RetrievalAttempt.v1": [
        "retrieval_attempt_id",
        "incident_id",
        "run_id",
        "generated_at",
        "verdict",
    ],
    "InvestigationSession.v1": [
        "session_id",
        "incident_id",
        "lineage_version",
        "latest_retrieval_attempt_id",
        "retrieval_attempt_ids",
        "latest_attempt_path",
        "updated_at",
    ],
    "Feedback.v1": [
        "feedback_id",
        "incident_id",
        "retrieval_attempt_id",
        "verdict_assessment",
        "notes",
    ],
    "ExperimentProfile.v1": [
        "profile_id",
        "name",
        "status",
        "fixture_refs",
    ],
    "ResearchState.v1": [
        "architecture_version",
        "mechanistic_bet",
        "current_invariants",
        "known_fractures",
        "active_questions",
        "deferred_features",
        "evaluation_fixtures",
        "next_actions",
    ],
    "FixtureManifest.v1": [
        "fixture_id",
        "source_repo",
        "source_branch",
        "incident_id",
        "incident_artifact_path",
        "retrieval_artifact_path",
        "reference_commits",
        "why_this_case_matters",
    ],
    "DurableMemory.v1": [
        "source",
        "claims",
    ],
    "PromiseRegistry.v1": [
        "registry_version",
        "promises",
    ],
    "PromiseSchema.v1": [
        "promise",
    ],
    "PromiseFrameCheckpoint.v1": [
        "frame_id",
        "incident_id",
        "promise_id",
        "interaction_family",
        "consistency_boundary",
        "focus_statement",
        "violation_shape",
        "touchpoints_remaining",
        "pressure_axes_remaining",
        "witness_ids",
        "live_anomaly_id",
        "next_check",
        "budget",
        "status",
    ],
    "PromiseCoverageLedger.v1": [
        "ledger_version",
        "coverage",
    ],
    "PromiseTraversalTask.v1": [
        "task_id",
        "promise_id",
        "interaction_family",
        "consistency_boundary",
        "assigned_frame_id",
        "objective",
        "status",
        "budget",
        "created_at",
        "updated_at",
    ],
}

VALID_VERDICTS = {"motif_match", "motif_non_match", "ambiguous"}
VALID_WITNESS_TYPES = {
    "observed_state",
    "missing_event",
    "unexpected_transition",
    "environment_fact",
    "ui_fact",
    "system_fact",
}
ABSTRACT_PHRASES = {
    "unexpected behavior",
    "something is wrong",
    "something wrong",
    "it broke",
    "not working",
    "doesnt work",
    "doesn't work",
    "broken",
    "bad state",
    "issue happened",
    "problem happened",
}
UNSUPPORTED_REJECTION_REASONS = {
    "empty_statement",
    "unsupported_witness_type",
    "missing_provenance",
    "missing_source_incident_ids",
    "unanchored_provenance",
    "composite_claim",
    "too_abstract",
    "noisy_log_statement",
}
PROMISE_REQUIRED_FIELDS = {
    "promise_id",
    "statement",
    "why_it_exists",
    "actors",
    "assets_or_rights",
    "protected_state",
    "interaction_families",
    "consistency_boundaries",
    "settlement_horizon",
    "representations",
    "admin_or_external_surfaces",
    "stress_axes",
    "evidence_refs",
    "priority",
    "confidence",
    "status",
}
PROMISE_ALLOWED_STATUSES = {"hypothesized", "accepted", "formalized"}
PROMISE_FRAME_ALLOWED_STATUSES = {"active", "blocked", "anomaly_found", "killed", "survives", "exhausted"}
PROMISE_FRAME_WITNESS_BUCKETS = ("support", "pressure", "contradiction")
PROMISE_FRAME_NEXT_CHECK_REQUIRED_FIELDS = ("kind", "prompt")
PROMISE_COVERAGE_REQUIRED_FIELDS = {
    "promise_id",
    "interaction_family",
    "consistency_boundary",
    "status",
    "last_session_ref",
    "notes",
    "updated_at",
}
PROMISE_COVERAGE_ALLOWED_STATUSES = {"unseen", "mapped", "scanned", "anomaly_found", "killed", "survives"}
PROMISE_TASK_REQUIRED_FIELDS = {
    "task_id",
    "promise_id",
    "interaction_family",
    "consistency_boundary",
    "assigned_frame_id",
    "objective",
    "status",
    "budget",
    "created_at",
    "updated_at",
}
PROMISE_TASK_ALLOWED_STATUSES = {"queued", "active", "blocked", "done"}


def default_targets() -> list[Path]:
    targets: list[Path] = []
    targets.extend(sorted(Path("diagnostics/evidence/incidents").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/evidence/witness_sets").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/session/retrieval_attempts").glob("*/*.json")))
    targets.extend(sorted(Path("diagnostics/session/latest").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/session/promise_frames").glob("*/*.json")))
    targets.extend(sorted(Path("diagnostics/session/promise_frames/latest").glob("*.json")))

    memory_claims = Path("diagnostics/memory/claims.json")
    if memory_claims.exists():
        targets.append(memory_claims)
    promise_registry = Path("diagnostics/memory/promise_registry.json")
    if promise_registry.exists():
        targets.append(promise_registry)
    targets.extend(sorted(Path("diagnostics/memory/promise_coverage_ledgers").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/session/promise_tasks").glob("*.json")))

    research_state = Path("research/research_state.yaml")
    if research_state.exists():
        targets.append(research_state)

    targets.extend(sorted(Path("eval/fixtures").glob("*.yaml")))
    targets.extend(sorted(Path("eval/fixtures").glob("*.yml")))
    targets.extend(sorted(Path("eval/profiles").glob("*.json")))
    return targets


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw_line.startswith(" ") or raw_line.startswith("\t"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        payload[key.strip()] = value.strip().strip('"').strip("'")
    return payload


def load_payload(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            raise ValueError("JSON artifact must be an object")
        return payload

    if path.suffix in {".yaml", ".yml"}:
        payload = parse_simple_yaml(path)
        if not isinstance(payload, dict):
            raise ValueError("YAML artifact must be a mapping")
        return payload

    raise ValueError(f"unsupported file type: {path.suffix}")


def check_required(payload: dict[str, Any], required: list[str]) -> list[str]:
    missing: list[str] = []
    for key in required:
        if key not in payload:
            missing.append(key)
    return missing


def _non_empty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _has_provenance_anchor(provenance: dict[str, Any]) -> bool:
    for key in ("raw_field_refs", "breadcrumb_refs", "log_refs", "screenshot_refs"):
        if _non_empty_strings(provenance.get(key)):
            return True
    return False


def _is_composite_statement(statement: str) -> bool:
    lowered = statement.lower()
    if statement.count("=") > 1:
        return True
    if ";" in statement:
        return True
    if " and " in lowered or " but " in lowered or " while " in lowered:
        return True
    if statement.count(",") >= 2:
        return True
    return False


def _is_abstract_statement(statement: str) -> bool:
    lowered = statement.lower().strip()
    if not lowered:
        return True
    if lowered in ABSTRACT_PHRASES:
        return True
    has_concrete_token = bool(re.search(r"(\b\d+(\.\d+)?\b|=|[A-Z]{2,}|incident-\d{8})", statement))
    if not has_concrete_token:
        if len(lowered.split()) < 4:
            return True
        if any(phrase in lowered for phrase in ("issue", "problem", "wrong", "broken", "unexpected")):
            return True
    return False


def _validate_witness_set(payload: dict[str, Any], errors: list[str], *, label: str) -> None:
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        errors.append(f"{label} metrics must be an object")
        return

    metric_names = ("candidate_count", "accepted_count", "rejected_count", "unsupported_count")
    for name in metric_names:
        value = metrics.get(name)
        if not isinstance(value, int) or value < 0:
            errors.append(f"{label} metrics.{name} must be a non-negative integer")

    candidate_count = metrics.get("candidate_count")
    accepted_count = metrics.get("accepted_count")
    rejected_count = metrics.get("rejected_count")
    unsupported_count = metrics.get("unsupported_count")
    if isinstance(candidate_count, int) and isinstance(accepted_count, int) and isinstance(rejected_count, int):
        if candidate_count != accepted_count + rejected_count:
            errors.append(f"{label} candidate_count must equal accepted_count + rejected_count")
    if isinstance(unsupported_count, int) and isinstance(rejected_count, int) and unsupported_count > rejected_count:
        errors.append(f"{label} metrics.unsupported_count must be <= metrics.rejected_count")

    witnesses = payload.get("witnesses")
    if not isinstance(witnesses, list):
        errors.append(f"{label} witnesses must be an array")
        return

    if isinstance(accepted_count, int) and accepted_count != len(witnesses):
        errors.append(f"{label} metrics.accepted_count must match witness array length")

    rejected_candidates = payload.get("rejected_candidates")
    if isinstance(rejected_count, int) and isinstance(rejected_candidates, list) and rejected_count != len(rejected_candidates):
        errors.append(f"{label} metrics.rejected_count must match rejected_candidates length")
    if isinstance(unsupported_count, int) and isinstance(rejected_candidates, list):
        derived_unsupported = sum(
            1
            for rejected in rejected_candidates
            if isinstance(rejected, dict)
            and any(
                str(reason) in UNSUPPORTED_REJECTION_REASONS
                for reason in _non_empty_strings(rejected.get("reasons"))
            )
        )
        if unsupported_count != derived_unsupported:
            errors.append(
                f"{label} metrics.unsupported_count must match rejected candidates with supportability failures"
            )

    for idx, witness in enumerate(witnesses, start=1):
        if not isinstance(witness, dict):
            errors.append(f"{label} witness[{idx}] must be an object")
            continue

        witness_type = witness.get("witness_type")
        if witness_type not in VALID_WITNESS_TYPES:
            errors.append(f"{label} witness[{idx}] has unsupported witness_type")

        statement = witness.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            errors.append(f"{label} witness[{idx}] statement must be non-empty")
            continue
        if _is_composite_statement(statement):
            errors.append(f"{label} witness[{idx}] statement must be a single claim")
        if _is_abstract_statement(statement):
            errors.append(f"{label} witness[{idx}] statement is too abstract")

        provenance = witness.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{label} witness[{idx}] provenance must be an object")
            continue
        required_keys = (
            "source_incident_ids",
            "raw_field_refs",
            "breadcrumb_refs",
            "log_refs",
            "screenshot_refs",
            "verifier_refs",
        )
        for key in required_keys:
            if key not in provenance:
                errors.append(f"{label} witness[{idx}] missing provenance.{key}")

        if not _non_empty_strings(provenance.get("source_incident_ids")):
            errors.append(f"{label} witness[{idx}] provenance.source_incident_ids must be non-empty")
        if not _non_empty_strings(provenance.get("verifier_refs")):
            errors.append(f"{label} witness[{idx}] provenance.verifier_refs must be non-empty")
        if not _has_provenance_anchor(provenance):
            errors.append(f"{label} witness[{idx}] provenance must include at least one anchor reference")


def validate_special_cases(path: Path, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_version = payload.get("schema_version")

    if schema_version == "Incident.v1":
        if payload.get("append_only") is not True:
            errors.append("Incident.v1 append_only must be true")
        witness_set = payload.get("witness_set")
        if not isinstance(witness_set, dict) or witness_set.get("schema_version") != "WitnessSet.v1":
            errors.append("Incident.v1 witness_set must be a WitnessSet.v1 object")
        elif isinstance(witness_set, dict):
            _validate_witness_set(witness_set, errors, label="Incident.v1 witness_set")

    if schema_version == "WitnessSet.v1":
        _validate_witness_set(payload, errors, label="WitnessSet.v1")

    if schema_version == "RetrievalAttempt.v1":
        verdict = payload.get("verdict")
        if verdict not in VALID_VERDICTS:
            errors.append("RetrievalAttempt.v1 verdict must be one of motif_match/motif_non_match/ambiguous")
        if not payload.get("next_discriminating_check") and not payload.get("gap_description"):
            errors.append("RetrievalAttempt.v1 requires next_discriminating_check or gap_description")

    if schema_version == "InvestigationSession.v1":
        if payload.get("lineage_version") in (None, 0):
            errors.append("InvestigationSession.v1 lineage_version must be >= 1")

    if schema_version == "DurableMemory.v1":
        source = payload.get("source")
        if not isinstance(source, dict):
            errors.append("DurableMemory.v1 source must be an object")

    if schema_version == "ExperimentProfile.v1":
        scoping_mode = payload.get("scoping_mode")
        if scoping_mode is not None and scoping_mode not in {"none", "promise_manual"}:
            errors.append("ExperimentProfile.v1 scoping_mode must be none or promise_manual")

    if schema_version == "PromiseRegistry.v1":
        registry_version = payload.get("registry_version")
        if not isinstance(registry_version, int) or registry_version < 1:
            errors.append("PromiseRegistry.v1 registry_version must be an integer >= 1")

        promises = payload.get("promises")
        if not isinstance(promises, list):
            errors.append("PromiseRegistry.v1 promises must be an array")
        else:
            seen_promise_ids: set[str] = set()
            for idx, promise in enumerate(promises, start=1):
                label = f"PromiseRegistry.v1 promises[{idx}]"
                if not isinstance(promise, dict):
                    errors.append(f"{label} must be an object")
                    continue

                missing = sorted(PROMISE_REQUIRED_FIELDS - set(promise.keys()))
                if missing:
                    errors.append(f"{label} missing required keys: {', '.join(missing)}")
                    continue

                promise_id = str(promise.get("promise_id", "")).strip()
                if not promise_id:
                    errors.append(f"{label}.promise_id must be non-empty")
                elif promise_id in seen_promise_ids:
                    errors.append(f"{label} duplicate promise_id: {promise_id}")
                else:
                    seen_promise_ids.add(promise_id)

                status = str(promise.get("status", "")).strip()
                if status not in PROMISE_ALLOWED_STATUSES:
                    errors.append(
                        f"{label}.status must be one of {', '.join(sorted(PROMISE_ALLOWED_STATUSES))}"
                    )

                confidence = promise.get("confidence")
                if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
                    errors.append(f"{label}.confidence must be a number between 0 and 1")

                for array_key in (
                    "actors",
                    "assets_or_rights",
                    "interaction_families",
                    "consistency_boundaries",
                    "representations",
                    "admin_or_external_surfaces",
                    "stress_axes",
                ):
                    if not _non_empty_strings(promise.get(array_key)):
                        errors.append(f"{label}.{array_key} must be a non-empty array of strings")

                evidence_refs = promise.get("evidence_refs")
                if not isinstance(evidence_refs, dict):
                    errors.append(f"{label}.evidence_refs must be an object")
                else:
                    for ref_key in ("source_incident_ids", "retrieval_refs", "witness_refs", "fixture_refs", "verifier_refs"):
                        if not _non_empty_strings(evidence_refs.get(ref_key)):
                            errors.append(
                                f"{label}.evidence_refs.{ref_key} must be a non-empty array of strings"
                            )

    if schema_version == "PromiseSchema.v1":
        promise = payload.get("promise")
        if not isinstance(promise, dict):
            errors.append("PromiseSchema.v1 promise must be an object")
        else:
            missing = sorted(PROMISE_REQUIRED_FIELDS - set(promise.keys()))
            if missing:
                errors.append(f"PromiseSchema.v1 promise missing required keys: {', '.join(missing)}")

    if schema_version == "PromiseFrameCheckpoint.v1":
        status = str(payload.get("status", "")).strip()
        if status not in PROMISE_FRAME_ALLOWED_STATUSES:
            errors.append(
                "PromiseFrameCheckpoint.v1 status must be one of active/blocked/anomaly_found/killed/survives/exhausted"
            )

        for list_key in ("touchpoints_remaining", "pressure_axes_remaining"):
            values = payload.get(list_key)
            if not isinstance(values, list):
                errors.append(f"PromiseFrameCheckpoint.v1 {list_key} must be an array")
            elif any(not str(item).strip() for item in values):
                errors.append(f"PromiseFrameCheckpoint.v1 {list_key} entries must be non-empty strings")

        witness_ids = payload.get("witness_ids")
        if not isinstance(witness_ids, dict):
            errors.append("PromiseFrameCheckpoint.v1 witness_ids must be an object")
        else:
            for bucket in PROMISE_FRAME_WITNESS_BUCKETS:
                values = witness_ids.get(bucket)
                if not isinstance(values, list):
                    errors.append(f"PromiseFrameCheckpoint.v1 witness_ids.{bucket} must be an array")
                elif any(not str(item).strip() for item in values):
                    errors.append(
                        f"PromiseFrameCheckpoint.v1 witness_ids.{bucket} entries must be non-empty strings"
                    )

        next_check = payload.get("next_check")
        if not isinstance(next_check, dict):
            errors.append("PromiseFrameCheckpoint.v1 next_check must be an object")
        elif not next_check:
            errors.append("PromiseFrameCheckpoint.v1 next_check must not be empty")
        else:
            for field in PROMISE_FRAME_NEXT_CHECK_REQUIRED_FIELDS:
                if not str(next_check.get(field, "")).strip():
                    errors.append(
                        f"PromiseFrameCheckpoint.v1 next_check.{field} must be a non-empty string"
                    )

        budget = payload.get("budget")
        if not isinstance(budget, dict):
            errors.append("PromiseFrameCheckpoint.v1 budget must be an object")
        else:
            checks_remaining = budget.get("checks_remaining")
            if not isinstance(checks_remaining, int) or checks_remaining < 0:
                errors.append("PromiseFrameCheckpoint.v1 budget.checks_remaining must be an integer >= 0")

    if schema_version == "PromiseCoverageLedger.v1":
        ledger_version = payload.get("ledger_version")
        if not isinstance(ledger_version, int) or ledger_version < 1:
            errors.append("PromiseCoverageLedger.v1 ledger_version must be an integer >= 1")

        coverage = payload.get("coverage")
        if not isinstance(coverage, list):
            errors.append("PromiseCoverageLedger.v1 coverage must be an array")
        else:
            seen_keys: set[tuple[str, str, str]] = set()
            for idx, cell in enumerate(coverage, start=1):
                label = f"PromiseCoverageLedger.v1 coverage[{idx}]"
                if not isinstance(cell, dict):
                    errors.append(f"{label} must be an object")
                    continue

                missing = sorted(PROMISE_COVERAGE_REQUIRED_FIELDS - set(cell.keys()))
                if missing:
                    errors.append(f"{label} missing required keys: {', '.join(missing)}")
                    continue

                promise_id = str(cell.get("promise_id", "")).strip()
                interaction_family = str(cell.get("interaction_family", "")).strip()
                consistency_boundary = str(cell.get("consistency_boundary", "")).strip()
                coverage_key = (promise_id, interaction_family, consistency_boundary)
                if not all(coverage_key):
                    errors.append(
                        f"{label} promise_id/interaction_family/consistency_boundary must be non-empty"
                    )
                elif coverage_key in seen_keys:
                    errors.append(
                        "PromiseCoverageLedger.v1 duplicate coverage key: "
                        f"{promise_id} | {interaction_family} | {consistency_boundary}"
                    )
                else:
                    seen_keys.add(coverage_key)

                status = str(cell.get("status", "")).strip()
                if status not in PROMISE_COVERAGE_ALLOWED_STATUSES:
                    errors.append(
                        f"{label}.status must be one of {', '.join(sorted(PROMISE_COVERAGE_ALLOWED_STATUSES))}"
                    )

                if not isinstance(cell.get("notes"), str):
                    errors.append(f"{label}.notes must be a string")
                if not str(cell.get("last_session_ref", "")).strip():
                    errors.append(f"{label}.last_session_ref must be non-empty")
                if not str(cell.get("updated_at", "")).strip():
                    errors.append(f"{label}.updated_at must be non-empty")

    if schema_version == "PromiseTraversalTask.v1":
        missing = sorted(PROMISE_TASK_REQUIRED_FIELDS - set(payload.keys()))
        if missing:
            errors.append(f"PromiseTraversalTask.v1 missing required keys: {', '.join(missing)}")
        else:
            status = str(payload.get("status", "")).strip()
            if status not in PROMISE_TASK_ALLOWED_STATUSES:
                errors.append(
                    "PromiseTraversalTask.v1 status must be one of "
                    f"{'/'.join(sorted(PROMISE_TASK_ALLOWED_STATUSES))}"
                )

            for key in (
                "task_id",
                "promise_id",
                "interaction_family",
                "consistency_boundary",
                "assigned_frame_id",
                "objective",
                "created_at",
                "updated_at",
            ):
                if not str(payload.get(key, "")).strip():
                    errors.append(f"PromiseTraversalTask.v1 {key} must be a non-empty string")

            if not isinstance(payload.get("budget"), dict):
                errors.append("PromiseTraversalTask.v1 budget must be an object")

    if path.name == "research_state.yaml" and schema_version != "ResearchState.v1":
        errors.append("research_state.yaml must have schema_version ResearchState.v1")

    return errors


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"file does not exist: {path}"]

    try:
        payload = load_payload(path)
    except Exception as exc:  # noqa: BLE001
        return [f"{path}: failed to load ({exc})"]

    if "schema_version" not in payload:
        errors.append("missing schema_version")
    if "produced_by" not in payload:
        errors.append("missing produced_by")

    schema_version = payload.get("schema_version")
    required = REQUIRED_BY_SCHEMA.get(schema_version)
    if required:
        missing = check_required(payload, required)
        if missing:
            errors.append(f"missing required keys for {schema_version}: {', '.join(missing)}")

    errors.extend(validate_special_cases(path, payload))

    return [f"{path}: {err}" for err in errors]


def main() -> int:
    targets: list[Path]
    if len(sys.argv) > 1:
        targets = [Path(arg) for arg in sys.argv[1:]]
    else:
        targets = default_targets()

    all_errors: list[str] = []
    for target in targets:
        all_errors.extend(validate_file(target))

    if all_errors:
        for err in all_errors:
            print(err)
        return 1

    print(f"validated {len(targets)} artifact(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
