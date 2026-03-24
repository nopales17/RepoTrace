import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def parse_legacy_incident_markdown(path: Path) -> dict[str, Any]:
    text = path.read_text()
    lines = text.splitlines()

    def section(header: str) -> list[str]:
        marker = f"## {header}"
        if marker not in lines:
            return []
        start = lines.index(marker) + 1
        end = len(lines)
        for idx in range(start, len(lines)):
            if lines[idx].startswith("## "):
                end = idx
                break
        return [line for line in lines[start:end] if line.strip()]

    title = "\n".join(section("Title")).strip()
    expected = "\n".join(section("Expected")).strip()
    actual = "\n".join(section("Actual")).strip()
    notes = "\n".join(section("Notes")).strip()
    metadata_lines = section("Metadata")
    breadcrumb_lines = section("Breadcrumbs")
    screenshot_lines = section("Screenshot")

    header_line = lines[0] if lines else f"# {path.stem}"
    incident_id = header_line.replace("#", "").strip() or path.stem

    return {
        "schema_version": "IncidentView.v1",
        "produced_by": "scripts/artifact_adapters.py",
        "incident_id": incident_id,
        "source_markdown_path": str(path),
        "title": title,
        "expected_behavior": expected,
        "actual_behavior": actual,
        "notes": notes,
        "metadata_lines": metadata_lines,
        "breadcrumb_lines": breadcrumb_lines,
        "screenshot_line": screenshot_lines[0] if screenshot_lines else "",
    }


def _build_witness_set(raw_incident: dict[str, Any], incident_id: str, produced_by: str) -> dict[str, Any]:
    witnesses: list[dict[str, Any]] = []

    def add_witness(kind: str, content: str, source_field: str, ts: str | None = None, idx: int | None = None) -> None:
        suffix = f"{idx:04d}" if idx is not None else f"{len(witnesses) + 1:04d}"
        witness_id = f"{incident_id}:{kind}:{suffix}"
        witness = {
            "witness_id": witness_id,
            "kind": kind,
            "content": content,
            "source_field": source_field,
        }
        if ts:
            witness["timestamp"] = ts
        witnesses.append(witness)

    add_witness("expected", _to_text(raw_incident.get("expectedBehavior")), "expectedBehavior")
    add_witness("actual", _to_text(raw_incident.get("actualBehavior")), "actualBehavior")
    add_witness("notes", _to_text(raw_incident.get("reporterNotes")), "reporterNotes")

    for idx, breadcrumb in enumerate(_as_list(raw_incident.get("breadcrumbs")), start=1):
        if not isinstance(breadcrumb, dict):
            continue
        ts = _to_text(breadcrumb.get("timestamp"))
        category = _to_text(breadcrumb.get("category"))
        message = _to_text(breadcrumb.get("message"))
        content = f"[{ts}] ({category}) {message}"
        add_witness("breadcrumb", content, "breadcrumbs", ts=ts, idx=idx)

    return {
        "schema_version": "WitnessSet.v1",
        "produced_by": produced_by,
        "incident_id": incident_id,
        "witnesses": witnesses,
    }


def adapt_raw_incident_to_v1(
    raw_incident: dict[str, Any],
    *,
    produced_by: str,
    source_path: str,
) -> dict[str, Any]:
    incident_id = _to_text(raw_incident.get("id"))
    metadata = raw_incident.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    witness_set = _build_witness_set(raw_incident, incident_id, produced_by)

    return {
        "schema_version": "Incident.v1",
        "produced_by": produced_by,
        "incident_id": incident_id,
        "append_only": True,
        "collected_at": _to_text(metadata.get("timestamp")) or utc_now_iso(),
        "source": {
            "source_kind": "raw_incident_json",
            "source_path": source_path,
        },
        "title": _to_text(raw_incident.get("title")),
        "expected_behavior": _to_text(raw_incident.get("expectedBehavior")),
        "actual_behavior": _to_text(raw_incident.get("actualBehavior")),
        "reporter_notes": _to_text(raw_incident.get("reporterNotes")),
        "metadata": metadata,
        "screenshot_filename": raw_incident.get("screenshotFilename"),
        "witness_set": witness_set,
        "witness_ids": [w.get("witness_id") for w in witness_set["witnesses"] if isinstance(w, dict)],
    }


def _first_non_empty(values: list[str]) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _extract_discriminating_check(retrieval: dict[str, Any]) -> str | None:
    for candidate in _as_list(retrieval.get("candidates")):
        if not isinstance(candidate, dict):
            continue
        check = _to_text(candidate.get("next_discriminating_check"))
        if check:
            return check
    return None


def _extract_gap_description(retrieval: dict[str, Any]) -> str:
    gaps: list[str] = []
    for candidate in _as_list(retrieval.get("candidates")):
        if not isinstance(candidate, dict):
            continue
        missing = candidate.get("missing_evidence")
        if isinstance(missing, list):
            gaps.extend([_to_text(item) for item in missing if _to_text(item)])
    rationale = _to_text(retrieval.get("rationale"))
    if rationale:
        gaps.append(f"legacy-rationale: {rationale}")

    if gaps:
        return "; ".join(gaps)

    return "Legacy retrieval payload did not include an explicit discriminating check; gap requires follow-up instrumentation."


def _extract_motif_ids(retrieval: dict[str, Any]) -> list[str]:
    motif_ids: list[str] = []
    for candidate in _as_list(retrieval.get("candidates")):
        if not isinstance(candidate, dict):
            continue
        motif_id = _to_text(candidate.get("motif_id"))
        if motif_id:
            motif_ids.append(motif_id)
    return motif_ids


def _extract_evidence_links(retrieval: dict[str, Any]) -> list[str]:
    links: list[str] = []
    for candidate in _as_list(retrieval.get("candidates")):
        if not isinstance(candidate, dict):
            continue
        for key in ("supporting_evidence", "contradicting_evidence", "missing_evidence"):
            for item in _as_list(candidate.get(key)):
                text = _to_text(item)
                if text:
                    links.append(f"legacy:{key}:{text}")
    if not links and _to_text(retrieval.get("rationale")):
        links.append(f"legacy:rationale:{_to_text(retrieval.get('rationale'))}")
    return links


def adapt_legacy_retrieval_to_v1(
    payload: dict[str, Any],
    *,
    produced_by: str,
    source_path: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    if payload.get("schema_version") == "RetrievalAttempt.v1":
        return payload

    run_id = run_id or make_run_id()
    incident_id = _to_text(payload.get("incident_id"))
    retrieval = payload.get("retrieval")
    if not isinstance(retrieval, dict):
        retrieval = {}

    verdict = _to_text(retrieval.get("verdict"))
    candidate_subsystems = retrieval.get("candidate_subsystems")
    if not isinstance(candidate_subsystems, list):
        candidate_subsystems = retrieval.get("subsystem_candidates")
    if not isinstance(candidate_subsystems, list):
        candidate_subsystems = []

    discriminating_check = _extract_discriminating_check(retrieval)
    gap_description = ""
    if not discriminating_check:
        gap_description = _extract_gap_description(retrieval)

    attempt_id = f"{incident_id}:{run_id}"

    attempt: dict[str, Any] = {
        "schema_version": "RetrievalAttempt.v1",
        "produced_by": produced_by,
        "retrieval_attempt_id": attempt_id,
        "incident_id": incident_id,
        "run_id": run_id,
        "generated_at": _first_non_empty([
            _to_text(payload.get("generated_at")),
            utc_now_iso(),
        ]),
        "verdict": verdict,
        "candidate_subsystems": [_to_text(item) for item in candidate_subsystems if _to_text(item)],
        "motif_ids": _extract_motif_ids(retrieval),
        "evidence_links": _extract_evidence_links(retrieval),
        "source": {
            "source_kind": "legacy_retrieval_result",
            "source_path": source_path,
        },
        "legacy_summary": {
            "triage_policy_mode": _to_text(retrieval.get("triage_policy_mode")),
            "next_action_mode": _to_text(retrieval.get("next_action_mode")),
            "confidence": retrieval.get("confidence"),
        },
    }

    if discriminating_check:
        attempt["next_discriminating_check"] = discriminating_check
    else:
        attempt["gap_description"] = gap_description

    if "next_discriminating_check" not in attempt and "gap_description" not in attempt:
        attempt["gap_description"] = _extract_gap_description(retrieval)

    return attempt


def build_investigation_session_v1(
    *,
    incident_id: str,
    latest_attempt_id: str,
    attempt_ids: list[str],
    produced_by: str,
    latest_attempt_path: str,
) -> dict[str, Any]:
    return {
        "schema_version": "InvestigationSession.v1",
        "produced_by": produced_by,
        "session_id": f"session:{incident_id}",
        "incident_id": incident_id,
        "lineage_version": len(attempt_ids),
        "latest_retrieval_attempt_id": latest_attempt_id,
        "retrieval_attempt_ids": attempt_ids,
        "latest_attempt_path": latest_attempt_path,
        "updated_at": utc_now_iso(),
    }


def read_durable_memory_from_legacy_claims(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    claims = payload.get("claims")
    if not isinstance(claims, list):
        claims = []

    durable_claims: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_id = _to_text(claim.get("id"))
        durable_claims.append(
            {
                "claim_id": claim_id,
                "status": _to_text(claim.get("status")),
                "statement": _to_text(claim.get("statement")),
                "subsystem": _to_text(claim.get("subsystem")),
                "motif_id": _to_text(claim.get("motif_id")),
                "provenance": {
                    "source_incident_ids": [],
                    "retrieval_attempt_ids": [],
                    "witness_ids": [],
                    "commit_refs": [],
                    "verifier_refs": [f"legacy-claims:{claim_id}"],
                },
            }
        )

    return {
        "schema_version": "DurableMemory.v1",
        "produced_by": "scripts/artifact_adapters.py",
        "source": {
            "source_kind": "legacy_claims_json",
            "source_path": str(path),
        },
        "generated_at": utc_now_iso(),
        "claims": durable_claims,
    }
