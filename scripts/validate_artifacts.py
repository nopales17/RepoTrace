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


def default_targets() -> list[Path]:
    targets: list[Path] = []
    targets.extend(sorted(Path("diagnostics/evidence/incidents").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/evidence/witness_sets").glob("*.json")))
    targets.extend(sorted(Path("diagnostics/session/retrieval_attempts").glob("*/*.json")))
    targets.extend(sorted(Path("diagnostics/session/latest").glob("*.json")))

    memory_claims = Path("diagnostics/memory/claims.json")
    if memory_claims.exists():
        targets.append(memory_claims)

    research_state = Path("research/research_state.yaml")
    if research_state.exists():
        targets.append(research_state)

    targets.extend(sorted(Path("eval/fixtures").glob("*.yaml")))
    targets.extend(sorted(Path("eval/fixtures").glob("*.yml")))
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
