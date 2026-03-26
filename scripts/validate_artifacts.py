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
    "PromiseTouchMap.v1": [
        "touch_map_id",
        "promise_id",
        "purpose_context",
        "actors",
        "protected_state",
        "mutable_surfaces",
        "interaction_families",
        "consistency_boundaries",
        "pressure_axes",
        "slice_candidates",
        "evidence_refs",
        "created_at",
        "updated_at",
    ],
    "PromiseDerivationWorksheet.v1": [
        "worksheet_id",
        "system_name",
        "purpose",
        "actors",
        "assets_or_rights",
        "transition_families",
        "representations",
        "consistency_boundaries",
        "settlement_horizons",
        "admin_or_external_surfaces",
        "candidate_promises",
        "open_questions",
        "evidence_refs",
        "status",
        "created_at",
        "updated_at",
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
    "PromiseScanOutcome.v1": [
        "outcome_id",
        "task_id",
        "frame_id",
        "incident_id",
        "promise_id",
        "interaction_family",
        "consistency_boundary",
        "outcome",
        "summary",
        "witness_ids_added",
        "anomaly_ids",
        "killed_reason",
        "next_action",
        "resulting_coverage_status",
        "resulting_task_status",
        "created_at",
    ],
    "PromiseWorkPacket.v1": [
        "work_packet_id",
        "incident_id",
        "promise_id",
        "slice",
        "frame_ref",
        "task_ref",
        "touch_map_ref",
        "coverage_ref",
        "check_ids",
        "prior_outcome_refs",
        "objective",
        "current_pressure",
        "budget",
        "status",
        "created_at",
        "updated_at",
    ],
    "CheckCard.v1": [
        "check_id",
        "statement",
        "promise_id",
        "interaction_family",
        "consistency_boundary",
        "objective",
        "check_type",
        "required_inputs",
        "procedure_steps",
        "expected_signals",
        "failure_signals",
        "evidence_outputs",
        "cost",
        "strength",
        "provenance_refs",
        "status",
    ],
    "PromiseCheckLibrary.v1": [
        "library_id",
        "library_version",
        "checks",
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
PROMISE_SCAN_OUTCOME_ALLOWED_OUTCOMES = {"killed", "anomaly_found", "survives", "exhausted", "blocked"}
PROMISE_WORK_PACKET_ALLOWED_STATUSES = {"draft", "ready", "active", "blocked", "completed", "stale"}
PROMISE_TOUCH_SLICE_ALLOWED_STATUSES = {"proposed", "accepted", "deferred", "exhausted"}
PROMISE_DERIVATION_ALLOWED_STATUSES = {"draft", "in_review", "accepted"}
PROMISE_DERIVATION_CANDIDATE_ALLOWED_STATUSES = {"proposed", "accepted", "rejected", "deferred"}
CHECK_CARD_REQUIRED_FIELDS = {
    "check_id",
    "statement",
    "promise_id",
    "interaction_family",
    "consistency_boundary",
    "objective",
    "check_type",
    "required_inputs",
    "procedure_steps",
    "expected_signals",
    "failure_signals",
    "evidence_outputs",
    "cost",
    "strength",
    "provenance_refs",
    "status",
}
CHECK_CARD_REQUIRED_STRING_FIELDS = {
    "check_id",
    "statement",
    "promise_id",
    "interaction_family",
    "consistency_boundary",
    "objective",
    "check_type",
    "cost",
    "strength",
    "status",
}
CHECK_CARD_REQUIRED_LIST_FIELDS = {
    "required_inputs",
    "procedure_steps",
    "expected_signals",
    "failure_signals",
    "evidence_outputs",
    "provenance_refs",
}
CHECK_CARD_ALLOWED_STATUSES = {"draft", "accepted", "deprecated"}
CHECK_CARD_ALLOWED_TYPES = {
    "inspection",
    "trace",
    "replay",
    "differential",
    "instrumentation",
    "minimization",
}


def default_targets() -> list[Path]:
    targets: list[Path] = []
    targets.extend(sorted(Path("diagnostics/evidence/incidents").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/evidence/witness_sets").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/session/retrieval_attempts").glob("*/*.json")))
    targets.extend(sorted(Path("diagnostics/session/latest").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/session/promise_frames").glob("*/*.json")))
    targets.extend(sorted(Path("diagnostics/session/promise_frames/latest").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/session/promise_outcomes").glob("*/*.json")))
    targets.extend(sorted(Path("diagnostics/session/promise_work_packets").glob("*/*.json")))

    memory_claims = Path("diagnostics/memory/claims.json")
    if memory_claims.exists():
        targets.append(memory_claims)
    promise_registry = Path("diagnostics/memory/promise_registry.json")
    if promise_registry.exists():
        targets.append(promise_registry)
    targets.extend(sorted(Path("diagnostics/memory/promise_coverage_ledgers").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/memory/promise_touch_maps").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/memory/promise_derivation_worksheets").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/memory/promise_check_libraries").glob("*.json")))
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

    if schema_version == "PromiseTouchMap.v1":
        for key in ("touch_map_id", "promise_id", "protected_state", "created_at", "updated_at"):
            if not str(payload.get(key, "")).strip():
                errors.append(f"PromiseTouchMap.v1 {key} must be a non-empty string")

        purpose_context = payload.get("purpose_context")
        if isinstance(purpose_context, dict):
            if not purpose_context:
                errors.append("PromiseTouchMap.v1 purpose_context must not be empty when object")
        elif not str(purpose_context or "").strip():
            errors.append("PromiseTouchMap.v1 purpose_context must be a non-empty string or object")

        for key in ("actors", "pressure_axes"):
            if not _non_empty_strings(payload.get(key)):
                errors.append(f"PromiseTouchMap.v1 {key} must be a non-empty array of strings")

        evidence_refs = payload.get("evidence_refs")
        if not isinstance(evidence_refs, dict):
            errors.append("PromiseTouchMap.v1 evidence_refs must be an object")

        mutable_surfaces = payload.get("mutable_surfaces")
        seen_surface_ids: set[str] = set()
        if not isinstance(mutable_surfaces, list) or not mutable_surfaces:
            errors.append("PromiseTouchMap.v1 mutable_surfaces must be a non-empty array")
        else:
            for idx, surface in enumerate(mutable_surfaces, start=1):
                label = f"PromiseTouchMap.v1 mutable_surfaces[{idx}]"
                if not isinstance(surface, dict):
                    errors.append(f"{label} must be an object")
                    continue
                required = {"surface_id", "kind", "ref", "actor_scope", "notes"}
                missing = sorted(required - set(surface.keys()))
                if missing:
                    errors.append(f"{label} missing required keys: {', '.join(missing)}")
                    continue
                for key in sorted(required):
                    if not str(surface.get(key, "")).strip():
                        errors.append(f"{label}.{key} must be a non-empty string")
                surface_id = str(surface.get("surface_id", "")).strip()
                if surface_id:
                    if surface_id in seen_surface_ids:
                        errors.append(f"PromiseTouchMap.v1 duplicate surface_id: {surface_id}")
                    seen_surface_ids.add(surface_id)

        interaction_families = payload.get("interaction_families")
        family_ids: set[str] = set()
        if not isinstance(interaction_families, list) or not interaction_families:
            errors.append("PromiseTouchMap.v1 interaction_families must be a non-empty array")
        else:
            for idx, family in enumerate(interaction_families, start=1):
                label = f"PromiseTouchMap.v1 interaction_families[{idx}]"
                if not isinstance(family, dict):
                    errors.append(f"{label} must be an object")
                    continue
                required = {"family_id", "statement", "surface_ids", "actor_scope", "transition_refs"}
                missing = sorted(required - set(family.keys()))
                if missing:
                    errors.append(f"{label} missing required keys: {', '.join(missing)}")
                    continue
                for key in ("family_id", "statement", "actor_scope"):
                    if not str(family.get(key, "")).strip():
                        errors.append(f"{label}.{key} must be a non-empty string")
                for key in ("surface_ids", "transition_refs"):
                    if not _non_empty_strings(family.get(key)):
                        errors.append(f"{label}.{key} must be a non-empty array of strings")
                family_id = str(family.get("family_id", "")).strip()
                if family_id:
                    if family_id in family_ids:
                        errors.append(f"PromiseTouchMap.v1 duplicate family_id: {family_id}")
                    family_ids.add(family_id)

        consistency_boundaries = payload.get("consistency_boundaries")
        boundary_ids: set[str] = set()
        if not isinstance(consistency_boundaries, list) or not consistency_boundaries:
            errors.append("PromiseTouchMap.v1 consistency_boundaries must be a non-empty array")
        else:
            for idx, boundary in enumerate(consistency_boundaries, start=1):
                label = f"PromiseTouchMap.v1 consistency_boundaries[{idx}]"
                if not isinstance(boundary, dict):
                    errors.append(f"{label} must be an object")
                    continue
                required = {
                    "boundary_id",
                    "statement",
                    "representation_a",
                    "representation_b",
                    "settlement_horizon",
                    "notes",
                }
                missing = sorted(required - set(boundary.keys()))
                if missing:
                    errors.append(f"{label} missing required keys: {', '.join(missing)}")
                    continue
                for key in sorted(required):
                    if not str(boundary.get(key, "")).strip():
                        errors.append(f"{label}.{key} must be a non-empty string")
                boundary_id = str(boundary.get("boundary_id", "")).strip()
                if boundary_id:
                    if boundary_id in boundary_ids:
                        errors.append(f"PromiseTouchMap.v1 duplicate boundary_id: {boundary_id}")
                    boundary_ids.add(boundary_id)

        slice_candidates = payload.get("slice_candidates")
        seen_slice_ids: set[str] = set()
        if not isinstance(slice_candidates, list) or not slice_candidates:
            errors.append("PromiseTouchMap.v1 slice_candidates must be a non-empty array")
        else:
            for idx, candidate in enumerate(slice_candidates, start=1):
                label = f"PromiseTouchMap.v1 slice_candidates[{idx}]"
                if not isinstance(candidate, dict):
                    errors.append(f"{label} must be an object")
                    continue

                required = {
                    "slice_id",
                    "interaction_family",
                    "consistency_boundary",
                    "rationale",
                    "priority",
                    "confidence",
                    "status",
                }
                missing = sorted(required - set(candidate.keys()))
                if missing:
                    errors.append(f"{label} missing required keys: {', '.join(missing)}")
                    continue

                for key in (
                    "slice_id",
                    "interaction_family",
                    "consistency_boundary",
                    "rationale",
                    "priority",
                    "status",
                ):
                    if not str(candidate.get(key, "")).strip():
                        errors.append(f"{label}.{key} must be a non-empty string")

                confidence = candidate.get("confidence")
                if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
                    errors.append(f"{label}.confidence must be a number between 0 and 1")

                status = str(candidate.get("status", "")).strip()
                if status not in PROMISE_TOUCH_SLICE_ALLOWED_STATUSES:
                    errors.append(
                        f"{label}.status must be one of {', '.join(sorted(PROMISE_TOUCH_SLICE_ALLOWED_STATUSES))}"
                    )

                slice_id = str(candidate.get("slice_id", "")).strip()
                if slice_id:
                    if slice_id in seen_slice_ids:
                        errors.append(f"PromiseTouchMap.v1 duplicate slice_id: {slice_id}")
                    seen_slice_ids.add(slice_id)

                family_ref = str(candidate.get("interaction_family", "")).strip()
                if family_ref and family_ids and family_ref not in family_ids:
                    errors.append(f"{label}.interaction_family references unknown family_id: {family_ref}")

                boundary_ref = str(candidate.get("consistency_boundary", "")).strip()
                if boundary_ref and boundary_ids and boundary_ref not in boundary_ids:
                    errors.append(f"{label}.consistency_boundary references unknown boundary_id: {boundary_ref}")

    if schema_version == "PromiseDerivationWorksheet.v1":
        for key in ("worksheet_id", "system_name", "purpose", "status", "created_at", "updated_at"):
            if not str(payload.get(key, "")).strip():
                errors.append(f"PromiseDerivationWorksheet.v1 {key} must be a non-empty string")

        status = str(payload.get("status", "")).strip()
        if status not in PROMISE_DERIVATION_ALLOWED_STATUSES:
            errors.append(
                "PromiseDerivationWorksheet.v1 status must be one of "
                f"{'/'.join(sorted(PROMISE_DERIVATION_ALLOWED_STATUSES))}"
            )

        for key in (
            "actors",
            "assets_or_rights",
            "transition_families",
            "representations",
            "consistency_boundaries",
            "settlement_horizons",
            "admin_or_external_surfaces",
        ):
            if not _non_empty_strings(payload.get(key)):
                errors.append(f"PromiseDerivationWorksheet.v1 {key} must be a non-empty array of strings")

        open_questions = payload.get("open_questions")
        if not isinstance(open_questions, list):
            errors.append("PromiseDerivationWorksheet.v1 open_questions must be an array")
        elif any(not str(item).strip() for item in open_questions):
            errors.append("PromiseDerivationWorksheet.v1 open_questions must contain only non-empty strings")

        if not isinstance(payload.get("evidence_refs"), dict):
            errors.append("PromiseDerivationWorksheet.v1 evidence_refs must be an object")

        transition_families = {str(item).strip() for item in _non_empty_strings(payload.get("transition_families"))}
        consistency_boundaries = {
            str(item).strip() for item in _non_empty_strings(payload.get("consistency_boundaries"))
        }

        candidate_promises = payload.get("candidate_promises")
        if not isinstance(candidate_promises, list) or not candidate_promises:
            errors.append("PromiseDerivationWorksheet.v1 candidate_promises must be a non-empty array")
        else:
            seen_candidate_ids: set[str] = set()
            for idx, candidate in enumerate(candidate_promises, start=1):
                label = f"PromiseDerivationWorksheet.v1 candidate_promises[{idx}]"
                if not isinstance(candidate, dict):
                    errors.append(f"{label} must be an object")
                    continue

                required = {
                    "candidate_id",
                    "statement",
                    "actor_scope",
                    "protected_state",
                    "interaction_families",
                    "consistency_boundaries",
                    "rationale",
                    "priority",
                    "confidence",
                    "status",
                }
                missing = sorted(required - set(candidate.keys()))
                if missing:
                    errors.append(f"{label} missing required keys: {', '.join(missing)}")
                    continue

                for key in (
                    "candidate_id",
                    "statement",
                    "actor_scope",
                    "protected_state",
                    "rationale",
                    "priority",
                    "status",
                ):
                    if not str(candidate.get(key, "")).strip():
                        errors.append(f"{label}.{key} must be a non-empty string")

                interaction_refs = _non_empty_strings(candidate.get("interaction_families"))
                if not interaction_refs:
                    errors.append(f"{label}.interaction_families must be a non-empty array of strings")
                else:
                    for family in interaction_refs:
                        if family not in transition_families:
                            errors.append(
                                f"{label}.interaction_families references unknown transition_family: {family}"
                            )

                boundary_refs = _non_empty_strings(candidate.get("consistency_boundaries"))
                if not boundary_refs:
                    errors.append(f"{label}.consistency_boundaries must be a non-empty array of strings")
                else:
                    for boundary in boundary_refs:
                        if boundary not in consistency_boundaries:
                            errors.append(
                                f"{label}.consistency_boundaries references unknown consistency_boundary: {boundary}"
                            )

                confidence = candidate.get("confidence")
                if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
                    errors.append(f"{label}.confidence must be a number between 0 and 1")

                candidate_status = str(candidate.get("status", "")).strip()
                if candidate_status not in PROMISE_DERIVATION_CANDIDATE_ALLOWED_STATUSES:
                    errors.append(
                        f"{label}.status must be one of "
                        f"{'/'.join(sorted(PROMISE_DERIVATION_CANDIDATE_ALLOWED_STATUSES))}"
                    )

                candidate_id = str(candidate.get("candidate_id", "")).strip()
                if candidate_id:
                    if candidate_id in seen_candidate_ids:
                        errors.append(f"PromiseDerivationWorksheet.v1 duplicate candidate_id: {candidate_id}")
                    seen_candidate_ids.add(candidate_id)

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

    if schema_version == "PromiseScanOutcome.v1":
        outcome = str(payload.get("outcome", "")).strip()
        if outcome not in PROMISE_SCAN_OUTCOME_ALLOWED_OUTCOMES:
            errors.append(
                "PromiseScanOutcome.v1 outcome must be one of "
                f"{'/'.join(sorted(PROMISE_SCAN_OUTCOME_ALLOWED_OUTCOMES))}"
            )

        for key in (
            "outcome_id",
            "task_id",
            "frame_id",
            "incident_id",
            "promise_id",
            "interaction_family",
            "consistency_boundary",
            "summary",
            "next_action",
            "created_at",
        ):
            if not str(payload.get(key, "")).strip():
                errors.append(f"PromiseScanOutcome.v1 {key} must be a non-empty string")

        next_action = str(payload.get("next_action", "")).strip()
        if not next_action:
            errors.append("PromiseScanOutcome.v1 next_action must be non-empty")

        for key in ("witness_ids_added", "anomaly_ids"):
            values = payload.get(key)
            if not isinstance(values, list):
                errors.append(f"PromiseScanOutcome.v1 {key} must be an array")
            elif any(not str(item).strip() for item in values):
                errors.append(f"PromiseScanOutcome.v1 {key} entries must be non-empty strings")

        killed_reason = payload.get("killed_reason")
        if killed_reason is not None and not str(killed_reason).strip():
            errors.append("PromiseScanOutcome.v1 killed_reason must be null or a non-empty string")
        if outcome == "killed" and not str(killed_reason or "").strip():
            errors.append("PromiseScanOutcome.v1 killed outcome requires killed_reason")

        resulting_coverage_status = str(payload.get("resulting_coverage_status", "")).strip()
        if resulting_coverage_status not in PROMISE_COVERAGE_ALLOWED_STATUSES:
            errors.append(
                "PromiseScanOutcome.v1 resulting_coverage_status must be one of "
                f"{'/'.join(sorted(PROMISE_COVERAGE_ALLOWED_STATUSES))}"
            )

        resulting_task_status = str(payload.get("resulting_task_status", "")).strip()
        if resulting_task_status not in PROMISE_TASK_ALLOWED_STATUSES:
            errors.append(
                "PromiseScanOutcome.v1 resulting_task_status must be one of "
                f"{'/'.join(sorted(PROMISE_TASK_ALLOWED_STATUSES))}"
            )

        parent_incident = path.parent.name
        incident_id = str(payload.get("incident_id", "")).strip()
        if parent_incident.startswith("incident-") and incident_id and incident_id != parent_incident:
            errors.append("PromiseScanOutcome.v1 incident_id must match parent incident directory")

    if schema_version == "CheckCard.v1":
        missing = sorted(CHECK_CARD_REQUIRED_FIELDS - set(payload.keys()))
        if missing:
            errors.append(f"CheckCard.v1 missing required keys: {', '.join(missing)}")
        else:
            for key in sorted(CHECK_CARD_REQUIRED_STRING_FIELDS):
                if not str(payload.get(key, "")).strip():
                    errors.append(f"CheckCard.v1 {key} must be a non-empty string")

            for key in sorted(CHECK_CARD_REQUIRED_LIST_FIELDS):
                values = payload.get(key)
                if not isinstance(values, list) or any(not str(item).strip() for item in values):
                    errors.append(f"CheckCard.v1 {key} must be a non-empty array of strings")

            status = str(payload.get("status", "")).strip()
            if status not in CHECK_CARD_ALLOWED_STATUSES:
                errors.append(
                    "CheckCard.v1 status must be one of "
                    f"{'/'.join(sorted(CHECK_CARD_ALLOWED_STATUSES))}"
                )

            check_type = str(payload.get("check_type", "")).strip()
            if check_type not in CHECK_CARD_ALLOWED_TYPES:
                errors.append(
                    "CheckCard.v1 check_type must be one of "
                    f"{'/'.join(sorted(CHECK_CARD_ALLOWED_TYPES))}"
                )

    if schema_version == "PromiseCheckLibrary.v1":
        library_id = str(payload.get("library_id", "")).strip()
        if not library_id:
            errors.append("PromiseCheckLibrary.v1 library_id must be a non-empty string")

        library_version = payload.get("library_version")
        if not isinstance(library_version, int) or library_version < 1:
            errors.append("PromiseCheckLibrary.v1 library_version must be an integer >= 1")

        checks = payload.get("checks")
        if not isinstance(checks, list):
            errors.append("PromiseCheckLibrary.v1 checks must be an array")
        else:
            seen_check_ids: set[str] = set()
            for idx, check in enumerate(checks, start=1):
                label = f"PromiseCheckLibrary.v1 checks[{idx}]"
                if not isinstance(check, dict):
                    errors.append(f"{label} must be an object")
                    continue

                missing = sorted(CHECK_CARD_REQUIRED_FIELDS - set(check.keys()))
                if missing:
                    errors.append(f"{label} missing required keys: {', '.join(missing)}")
                    continue

                for key in sorted(CHECK_CARD_REQUIRED_STRING_FIELDS):
                    if not str(check.get(key, "")).strip():
                        errors.append(f"{label}.{key} must be a non-empty string")

                for key in sorted(CHECK_CARD_REQUIRED_LIST_FIELDS):
                    values = check.get(key)
                    if not isinstance(values, list) or any(not str(item).strip() for item in values):
                        errors.append(f"{label}.{key} must be a non-empty array of strings")

                status = str(check.get("status", "")).strip()
                if status not in CHECK_CARD_ALLOWED_STATUSES:
                    errors.append(
                        f"{label}.status must be one of {'/'.join(sorted(CHECK_CARD_ALLOWED_STATUSES))}"
                    )

                check_type = str(check.get("check_type", "")).strip()
                if check_type not in CHECK_CARD_ALLOWED_TYPES:
                    errors.append(
                        f"{label}.check_type must be one of {'/'.join(sorted(CHECK_CARD_ALLOWED_TYPES))}"
                    )

                check_id = str(check.get("check_id", "")).strip()
                if check_id:
                    if check_id in seen_check_ids:
                        errors.append(f"PromiseCheckLibrary.v1 duplicate check_id: {check_id}")
                    seen_check_ids.add(check_id)

    if schema_version == "PromiseWorkPacket.v1":
        for key in (
            "work_packet_id",
            "incident_id",
            "promise_id",
            "frame_ref",
            "task_ref",
            "touch_map_ref",
            "coverage_ref",
            "objective",
            "created_at",
            "updated_at",
        ):
            if not str(payload.get(key, "")).strip():
                errors.append(f"PromiseWorkPacket.v1 {key} must be a non-empty string")

        status = str(payload.get("status", "")).strip()
        if status not in PROMISE_WORK_PACKET_ALLOWED_STATUSES:
            errors.append(
                "PromiseWorkPacket.v1 status must be one of "
                f"{'/'.join(sorted(PROMISE_WORK_PACKET_ALLOWED_STATUSES))}"
            )

        slice_obj = payload.get("slice")
        if not isinstance(slice_obj, dict):
            errors.append("PromiseWorkPacket.v1 slice must be an object")
        else:
            for key in ("interaction_family", "consistency_boundary"):
                if not str(slice_obj.get(key, "")).strip():
                    errors.append(f"PromiseWorkPacket.v1 slice.{key} must be a non-empty string")

        check_ids = payload.get("check_ids")
        if not isinstance(check_ids, list):
            errors.append("PromiseWorkPacket.v1 check_ids must be an array of strings")
        else:
            normalized_check_ids = [str(item).strip() for item in check_ids]
            if any(not item for item in normalized_check_ids):
                errors.append("PromiseWorkPacket.v1 check_ids entries must be non-empty strings")
            if status != "draft" and not [item for item in normalized_check_ids if item]:
                errors.append("PromiseWorkPacket.v1 check_ids may be empty only when status is draft")

        prior_outcome_refs = payload.get("prior_outcome_refs")
        if not isinstance(prior_outcome_refs, list):
            errors.append("PromiseWorkPacket.v1 prior_outcome_refs must be an array of strings")
        elif any(not str(item).strip() for item in prior_outcome_refs):
            errors.append("PromiseWorkPacket.v1 prior_outcome_refs entries must be non-empty strings")

        current_pressure = payload.get("current_pressure")
        if not isinstance(current_pressure, dict):
            errors.append("PromiseWorkPacket.v1 current_pressure must be an object")
        else:
            if not str(current_pressure.get("focus_statement", "")).strip():
                errors.append("PromiseWorkPacket.v1 current_pressure.focus_statement must be a non-empty string")
            if not str(current_pressure.get("violation_shape", "")).strip():
                errors.append("PromiseWorkPacket.v1 current_pressure.violation_shape must be a non-empty string")

            unresolved_questions = current_pressure.get("unresolved_questions")
            if not isinstance(unresolved_questions, list):
                errors.append("PromiseWorkPacket.v1 current_pressure.unresolved_questions must be an array")
            elif any(not str(item).strip() for item in unresolved_questions):
                errors.append("PromiseWorkPacket.v1 current_pressure.unresolved_questions entries must be non-empty strings")

            if "next_check" not in current_pressure:
                errors.append("PromiseWorkPacket.v1 current_pressure.next_check must be present")
            elif status != "completed" and not str(current_pressure.get("next_check", "")).strip():
                errors.append(
                    "PromiseWorkPacket.v1 current_pressure.next_check must be non-empty unless status is completed"
                )

        if not isinstance(payload.get("budget"), dict):
            errors.append("PromiseWorkPacket.v1 budget must be an object")

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
