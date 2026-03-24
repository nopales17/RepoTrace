import json
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


def default_targets() -> list[Path]:
    targets: list[Path] = []
    targets.extend(sorted(Path("diagnostics/evidence/incidents").glob("*.json")))
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


def validate_special_cases(path: Path, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_version = payload.get("schema_version")

    if schema_version == "Incident.v1":
        if payload.get("append_only") is not True:
            errors.append("Incident.v1 append_only must be true")
        witness_set = payload.get("witness_set")
        if not isinstance(witness_set, dict) or witness_set.get("schema_version") != "WitnessSet.v1":
            errors.append("Incident.v1 witness_set must be a WitnessSet.v1 object")

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
