"""
MODULE_SPEC
module_id: scripts.save_retrieval_result
responsibility: Persist retrieval outputs with run-versioned session lineage while preserving legacy retrieval view compatibility.
inputs: Retrieval JSON via stdin or file path.
outputs: Versioned RetrievalAttempt.v1 artifact under diagnostics/session/retrieval_attempts/<incident>/<run_id>.json; latest InvestigationSession.v1 view under diagnostics/session/latest/<incident>.json; compatibility write under diagnostics/retrieval_results/<incident>.json.
invariants: No retrieval lineage modeled as a single overwritable per-incident file; each attempt has verdict and discriminating check or gap description; compatibility output does not replace authoritative session lineage.
experiment_toggles: REPO_TRACE_WRITE_LEGACY_RETRIEVAL_VIEW=1 (default on)
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

from artifact_adapters import (
    adapt_legacy_retrieval_to_v1,
    build_investigation_session_v1,
    make_run_id,
)

VALID_VERDICTS = {"motif_match", "motif_non_match", "ambiguous"}


def validate_input_payload(payload: dict[str, Any]) -> None:
    incident_id = payload.get("incident_id")
    if not isinstance(incident_id, str) or not incident_id:
        print("retrieval payload must include non-empty string incident_id")
        raise SystemExit(1)

    if payload.get("schema_version") == "RetrievalAttempt.v1":
        verdict = payload.get("verdict")
        if verdict not in VALID_VERDICTS:
            print("RetrievalAttempt.v1 verdict must be one of: motif_match, motif_non_match, ambiguous")
            raise SystemExit(1)
        if not payload.get("next_discriminating_check") and not payload.get("gap_description"):
            print("RetrievalAttempt.v1 must include next_discriminating_check or gap_description")
            raise SystemExit(1)
        return

    retrieval = payload.get("retrieval")
    if not isinstance(retrieval, dict):
        print("legacy retrieval payload must include object retrieval")
        raise SystemExit(1)

    verdict = retrieval.get("verdict")
    if verdict not in VALID_VERDICTS:
        print("retrieval.verdict must be one of: motif_match, motif_non_match, ambiguous")
        raise SystemExit(1)


def load_payload() -> dict[str, Any]:
    if len(sys.argv) > 2:
        print("usage: python scripts/save_retrieval_result.py [path/to/retrieval_result.json]")
        raise SystemExit(1)

    if len(sys.argv) == 2:
        src = Path(sys.argv[1])
        if not src.exists():
            print(f"input file does not exist: {src}")
            raise SystemExit(1)
        return json.loads(src.read_text())

    raw = sys.stdin.read().strip()
    if not raw:
        print("provide retrieval JSON via file argument or stdin")
        raise SystemExit(1)
    return json.loads(raw)


def write_attempt_and_session(attempt: dict[str, Any]) -> tuple[Path, Path]:
    incident_id = attempt["incident_id"]
    run_id = attempt.get("run_id") or make_run_id()
    attempt["run_id"] = run_id

    attempts_dir = Path("diagnostics/session/retrieval_attempts") / incident_id
    attempts_dir.mkdir(parents=True, exist_ok=True)

    attempt_file = attempts_dir / f"{run_id}.json"
    attempt_file.write_text(json.dumps(attempt, indent=2) + "\n")

    attempt_files = sorted(attempts_dir.glob("*.json"))
    attempt_ids: list[str] = []
    for path in attempt_files:
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        retrieval_attempt_id = payload.get("retrieval_attempt_id")
        if isinstance(retrieval_attempt_id, str) and retrieval_attempt_id:
            attempt_ids.append(retrieval_attempt_id)

    latest_dir = Path("diagnostics/session/latest")
    latest_dir.mkdir(parents=True, exist_ok=True)

    latest_session = build_investigation_session_v1(
        incident_id=incident_id,
        latest_attempt_id=attempt.get("retrieval_attempt_id", f"{incident_id}:{run_id}"),
        attempt_ids=attempt_ids,
        produced_by="scripts/save_retrieval_result.py",
        latest_attempt_path=str(attempt_file),
    )
    latest_file = latest_dir / f"{incident_id}.json"
    latest_file.write_text(json.dumps(latest_session, indent=2) + "\n")

    return attempt_file, latest_file


def write_legacy_view(payload: dict[str, Any]) -> Path:
    out_dir = Path("diagnostics/retrieval_results")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{payload['incident_id']}.json"
    out_file.write_text(json.dumps(payload, indent=2) + "\n")
    return out_file


def main() -> None:
    payload = load_payload()
    validate_input_payload(payload)

    run_id = make_run_id()
    source_path = sys.argv[1] if len(sys.argv) == 2 else "stdin"

    attempt_v1 = adapt_legacy_retrieval_to_v1(
        payload,
        produced_by="scripts/save_retrieval_result.py",
        source_path=source_path,
        run_id=run_id,
    )

    attempt_file, latest_file = write_attempt_and_session(attempt_v1)
    write_legacy = os.getenv("REPO_TRACE_WRITE_LEGACY_RETRIEVAL_VIEW", "1") != "0"
    legacy_file: Path | None = None
    if write_legacy:
        legacy_file = write_legacy_view(payload)
    else:
        print("skipped legacy retrieval view write (REPO_TRACE_WRITE_LEGACY_RETRIEVAL_VIEW=0)")

    print(f"wrote {attempt_file}")
    print(f"wrote {latest_file}")
    if legacy_file:
        print(f"wrote {legacy_file}")


if __name__ == "__main__":
    main()
