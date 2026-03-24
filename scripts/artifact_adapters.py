import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TypedDict


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


class NormalizedAttempt(TypedDict):
    attempt_id: str
    verdict: str
    candidate_count: int
    has_discriminating_check: bool
    contradiction_items: list[str]
    source_shape: str


def load_experiment_profiles_v1(profiles_dir: Path, required_profile_ids: Iterable[str]) -> list[dict[str, Any]]:
    required_ids = sorted({_to_text(profile_id).strip() for profile_id in required_profile_ids if _to_text(profile_id).strip()})
    if not required_ids:
        raise ValueError("required_profile_ids must include at least one profile id")
    if not profiles_dir.exists():
        raise ValueError(f"profiles directory does not exist: {profiles_dir}")

    deduped_by_profile_id: dict[str, dict[str, Any]] = {}
    for path in sorted(profiles_dir.glob("*.json")):
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            raise ValueError(f"profile manifest must be an object: {path}")

        required_keys = ("schema_version", "produced_by", "profile_id", "name", "status", "fixture_refs")
        missing = [key for key in required_keys if key not in payload]
        if missing:
            raise ValueError(f"{path} missing required keys: {', '.join(missing)}")
        if payload.get("schema_version") != "ExperimentProfile.v1":
            raise ValueError(f"{path} schema_version must be ExperimentProfile.v1")

        profile_id = _to_text(payload.get("profile_id")).strip()
        if not profile_id:
            raise ValueError(f"{path} profile_id must be non-empty")
        if profile_id in deduped_by_profile_id:
            continue

        status = _to_text(payload.get("status")).strip()
        if status not in {"active", "inactive"}:
            raise ValueError(f"{path} status must be active or inactive")

        fixture_refs = payload.get("fixture_refs")
        if not isinstance(fixture_refs, list):
            raise ValueError(f"{path} fixture_refs must be an array")

        normalized = dict(payload)
        normalized["fixture_refs"] = [_to_text(item).strip() for item in fixture_refs if _to_text(item).strip()]
        normalized["scoping_mode"] = _to_text(payload.get("scoping_mode")).strip() or "none"
        normalized["promise_id"] = payload.get("promise_id")
        normalized["slice_key"] = payload.get("slice_key")
        deduped_by_profile_id[profile_id] = normalized

    missing_required = [profile_id for profile_id in required_ids if profile_id not in deduped_by_profile_id]
    if missing_required:
        raise ValueError(f"missing required profiles: {', '.join(missing_required)}")

    return sorted(deduped_by_profile_id.values(), key=lambda profile: _to_text(profile.get("profile_id")))


def _collect_contradiction_items_from_legacy(retrieval: dict[str, Any]) -> list[str]:
    contradictions: list[str] = []
    for candidate in _as_list(retrieval.get("candidates")):
        if not isinstance(candidate, dict):
            continue
        for item in _as_list(candidate.get("contradicting_evidence")):
            text = _to_text(item).strip()
            if text and not text.lower().startswith("none"):
                contradictions.append(text)
    return contradictions


def _collect_contradiction_items_from_v1(payload: dict[str, Any]) -> list[str]:
    contradictions: list[str] = []
    for item in _as_list(payload.get("contradiction_items")):
        text = _to_text(item).strip()
        if text and not text.lower().startswith("none"):
            contradictions.append(text)
    if contradictions:
        return contradictions

    for link in _as_list(payload.get("evidence_links")):
        text = _to_text(link).strip()
        if text.startswith("legacy:contradicting_evidence:"):
            detail = text.split("legacy:contradicting_evidence:", 1)[1].strip()
            if detail and not detail.lower().startswith("none"):
                contradictions.append(detail)
    return contradictions


def normalize_retrieval_attempt(raw_attempt: dict[str, Any]) -> NormalizedAttempt:
    if not isinstance(raw_attempt, dict):
        return {
            "attempt_id": "attempt:invalid-shape",
            "verdict": "ambiguous",
            "candidate_count": 0,
            "has_discriminating_check": False,
            "contradiction_items": [],
            "source_shape": "invalid",
        }

    if raw_attempt.get("schema_version") == "RetrievalAttempt.v1":
        attempt_id = _first_non_empty(
            [
                _to_text(raw_attempt.get("retrieval_attempt_id")),
                _to_text(raw_attempt.get("attempt_id")),
                f"{_to_text(raw_attempt.get('incident_id'))}:{_to_text(raw_attempt.get('run_id'))}",
            ]
        ) or "attempt:v1-unknown"
        candidate_subsystems = [_to_text(item).strip() for item in _as_list(raw_attempt.get("candidate_subsystems")) if _to_text(item).strip()]
        return {
            "attempt_id": attempt_id,
            "verdict": _to_text(raw_attempt.get("verdict")) or "ambiguous",
            "candidate_count": len(candidate_subsystems),
            "has_discriminating_check": bool(_to_text(raw_attempt.get("next_discriminating_check")).strip()),
            "contradiction_items": _collect_contradiction_items_from_v1(raw_attempt),
            "source_shape": "retrieval_attempt_v1",
        }

    retrieval = raw_attempt.get("retrieval")
    if isinstance(retrieval, dict):
        candidate_subsystems = retrieval.get("candidate_subsystems")
        if not isinstance(candidate_subsystems, list):
            candidate_subsystems = retrieval.get("subsystem_candidates")
        candidate_list = [_to_text(item).strip() for item in _as_list(candidate_subsystems) if _to_text(item).strip()]
        has_discriminating_check = any(
            _to_text(candidate.get("next_discriminating_check")).strip()
            for candidate in _as_list(retrieval.get("candidates"))
            if isinstance(candidate, dict)
        )
        legacy_attempt_id = _first_non_empty(
            [
                _to_text(raw_attempt.get("attempt_id")),
                _to_text(raw_attempt.get("retrieval_attempt_id")),
                f"{_to_text(raw_attempt.get('incident_id'))}:{_to_text(raw_attempt.get('generated_at'))}",
                _to_text(raw_attempt.get("incident_id")),
            ]
        ) or "attempt:legacy-unknown"
        return {
            "attempt_id": legacy_attempt_id,
            "verdict": _to_text(retrieval.get("verdict")) or "ambiguous",
            "candidate_count": len(candidate_list),
            "has_discriminating_check": has_discriminating_check,
            "contradiction_items": _collect_contradiction_items_from_legacy(retrieval),
            "source_shape": "legacy_retrieval_result",
        }

    candidate_subsystems = [_to_text(item).strip() for item in _as_list(raw_attempt.get("candidate_subsystems")) if _to_text(item).strip()]
    fallback_attempt_id = _first_non_empty(
        [
            _to_text(raw_attempt.get("attempt_id")),
            _to_text(raw_attempt.get("retrieval_attempt_id")),
            _to_text(raw_attempt.get("incident_id")),
        ]
    ) or "attempt:unknown-shape"
    return {
        "attempt_id": fallback_attempt_id,
        "verdict": _to_text(raw_attempt.get("verdict")) or "ambiguous",
        "candidate_count": len(candidate_subsystems),
        "has_discriminating_check": bool(_to_text(raw_attempt.get("next_discriminating_check")).strip()),
        "contradiction_items": _collect_contradiction_items_from_v1(raw_attempt),
        "source_shape": "attempt_like",
    }


WITNESS_TYPES = {
    "observed_state",
    "missing_event",
    "unexpected_transition",
    "environment_fact",
    "ui_fact",
    "system_fact",
}

ENV_METADATA_KEYS = {
    "appVersion",
    "buildNumber",
    "osVersion",
    "deviceModel",
}

UI_METADATA_KEYS = {"screenName"}

LOG_PRIORITY_KEYS = {
    "event",
    "direction",
    "target",
    "next",
    "trigger",
    "lookupHit",
    "runtimeInputKey",
    "lookupKey",
    "collectionCode",
    "queuedTrackCount",
    "expectedQueuedTrackCount",
    "actualQueuedTrackCount",
    "screenCollection",
    "runtimeCollection",
    "ruleCollection",
    "RuleQueuedTrackCount",
    "firstChildToDetailDeltaY",
    "belowBoundaryDeltaY",
    "detailVisibleHeight",
    "detailRegionHeight",
    "phaseDirection",
    "transitionSeq",
    "elapsed",
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

UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _normalize_statement(value: str) -> str:
    text = " ".join(value.strip().split())
    return text.strip(" ,;")


def _split_claim_clauses(text: str) -> list[str]:
    normalized = _normalize_statement(text)
    if not normalized:
        return []

    clauses: list[str] = [normalized]
    split_patterns = [
        r"\s+but\s+",
        r"\s+while\s+",
        r"\s+and\s+",
        r";\s*",
    ]
    for pattern in split_patterns:
        next_clauses: list[str] = []
        for clause in clauses:
            next_clauses.extend([piece for piece in re.split(pattern, clause) if _normalize_statement(piece)])
        clauses = next_clauses

    final_clauses: list[str] = []
    for clause in clauses:
        if clause.count("=") > 1 and "," in clause:
            final_clauses.extend([_normalize_statement(piece) for piece in clause.split(",") if _normalize_statement(piece)])
        else:
            final_clauses.append(_normalize_statement(clause))
    return [clause for clause in final_clauses if clause]


def _extract_key_value_pairs(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for key, value in re.findall(r"([A-Za-z][A-Za-z0-9_]+)=([^,\s]+)", text):
        pairs.append((key, value))
    return pairs


def _is_log_breadcrumb(category: str, message: str) -> bool:
    lowered_category = category.lower()
    lowered_message = message.lower()
    return lowered_category.startswith("log") or "event=" in lowered_message or "seq=" in lowered_message


def _is_priority_log_key(key: str) -> bool:
    if key in LOG_PRIORITY_KEYS:
        return True
    lowered = key.lower()
    return lowered.endswith("deltay") or lowered.endswith("count") or lowered.endswith("height")


def _classify_witness_type(statement: str, source_field: str, category: str = "") -> str:
    text = statement.lower()
    source = source_field.lower()
    cat = category.lower()

    if source.startswith("metadata.") and source_field.split(".", 1)[1] in ENV_METADATA_KEYS:
        return "environment_fact"
    if source.startswith("metadata.") and source_field.split(".", 1)[1] in UI_METADATA_KEYS:
        return "ui_fact"
    if source == "screenshotfilename":
        return "ui_fact"

    if "should " in text or "expected" in text:
        return "missing_event"
    if "mismatch" in text or "unexpected" in text:
        return "unexpected_transition"
    if cat == "bug":
        return "unexpected_transition"
    if cat == "observation":
        if "ui" in text or "display" in text or "screen" in text:
            return "ui_fact"
        return "observed_state"
    if cat in {"pipeline", "context", "navigation", "action"}:
        if "ui" in text or "screen" in text:
            return "ui_fact"
        return "system_fact"

    if "osversion" in text or "devicemodel" in text or "appversion" in text:
        return "environment_fact"
    if "ui" in text or "screen" in text or "displayed" in text:
        return "ui_fact"
    if "rule" in text or "runtime" in text or "lookup" in text:
        return "system_fact"
    return "observed_state"


def _empty_provenance() -> dict[str, list[str]]:
    return {
        "source_incident_ids": [],
        "raw_field_refs": [],
        "breadcrumb_refs": [],
        "log_refs": [],
        "screenshot_refs": [],
        "verifier_refs": [],
    }


def _has_anchor_refs(provenance: dict[str, Any]) -> bool:
    for key in ("raw_field_refs", "breadcrumb_refs", "log_refs", "screenshot_refs"):
        if [_to_text(item) for item in _as_list(provenance.get(key)) if _to_text(item)]:
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

    has_concrete_token = bool(
        re.search(
            r"(\b\d+(\.\d+)?\b|=|[A-Z]{2,}|incident-\d{8})",
            statement,
        )
    )
    if not has_concrete_token:
        if len(lowered.split()) < 4:
            return True
        if any(phrase in lowered for phrase in ("issue", "problem", "wrong", "broken", "unexpected")):
            return True
    return False


def _parse_single_key_value(statement: str) -> tuple[str, str] | None:
    if statement.count("=") != 1:
        return None
    key, value = statement.split("=", 1)
    key = _normalize_statement(key)
    value = _normalize_statement(value)
    if not key or not value or " " in key:
        return None
    return key, value


def _is_noisy_log_statement(statement: str, provenance: dict[str, Any]) -> bool:
    if not [_to_text(item) for item in _as_list(provenance.get("log_refs")) if _to_text(item)]:
        return False

    parsed = _parse_single_key_value(statement)
    if not parsed:
        return False

    key, value = parsed
    lowered_key = key.lower()
    lowered_value = value.lower()

    if lowered_key == "event" and ("probe." in lowered_value or lowered_value.endswith(".sample")):
        return True
    if lowered_key == "trigger" and lowered_value in {"begin", "end", "displaylink"}:
        return True
    if lowered_key in {"target", "next"} and bool(UUID_PATTERN.fullmatch(value)):
        return True
    return False


def critique_witness_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []

    statement = _normalize_statement(_to_text(candidate.get("statement")))
    if not statement:
        reasons.append("empty_statement")

    witness_type = _to_text(candidate.get("witness_type"))
    if witness_type not in WITNESS_TYPES:
        reasons.append("unsupported_witness_type")

    provenance = candidate.get("provenance")
    if not isinstance(provenance, dict):
        reasons.append("missing_provenance")
        provenance = _empty_provenance()

    source_incident_ids = [_to_text(item) for item in _as_list(provenance.get("source_incident_ids")) if _to_text(item)]
    if not source_incident_ids:
        reasons.append("missing_source_incident_ids")
    if not _has_anchor_refs(provenance):
        reasons.append("unanchored_provenance")

    if statement and _is_composite_statement(statement):
        reasons.append("composite_claim")
    if statement and _is_abstract_statement(statement):
        reasons.append("too_abstract")
    if statement and _is_noisy_log_statement(statement, provenance):
        reasons.append("noisy_log_statement")

    return {
        "accepted": not reasons,
        "reasons": reasons,
    }


def propose_witness_candidates(raw_incident: dict[str, Any], incident_id: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seq = 0

    def add_candidate(
        *,
        statement: str,
        source_field: str,
        witness_type: str | None = None,
        breadcrumb_ref: str = "",
        is_log: bool = False,
        screenshot_ref: str = "",
        timestamp: str = "",
        verifier_ref: str,
        category: str = "",
    ) -> None:
        nonlocal seq
        normalized_statement = _normalize_statement(statement)
        if not normalized_statement:
            return

        seq += 1
        provenance = _empty_provenance()
        if incident_id:
            provenance["source_incident_ids"].append(incident_id)
        if source_field:
            provenance["raw_field_refs"].append(source_field)
        if breadcrumb_ref:
            provenance["breadcrumb_refs"].append(breadcrumb_ref)
        if is_log and breadcrumb_ref:
            provenance["log_refs"].append(breadcrumb_ref)
        if screenshot_ref:
            provenance["screenshot_refs"].append(screenshot_ref)
        provenance["verifier_refs"].append(verifier_ref)

        final_type = witness_type or _classify_witness_type(normalized_statement, source_field, category=category)
        candidate: dict[str, Any] = {
            "candidate_id": f"{incident_id}:candidate:{seq:04d}",
            "witness_type": final_type,
            "statement": normalized_statement,
            "provenance": provenance,
            "source_field": source_field,
        }
        if timestamp:
            candidate["timestamp"] = timestamp
        candidates.append(candidate)

    expected = _to_text(raw_incident.get("expectedBehavior")).strip()
    for clause in _split_claim_clauses(expected):
        add_candidate(
            statement=clause,
            source_field="expectedBehavior",
            witness_type="missing_event",
            verifier_ref="witness_proposer:expectedBehavior",
        )

    actual = _to_text(raw_incident.get("actualBehavior")).strip()
    for clause in _split_claim_clauses(actual):
        add_candidate(
            statement=clause,
            source_field="actualBehavior",
            verifier_ref="witness_proposer:actualBehavior",
        )

    notes = _to_text(raw_incident.get("reporterNotes")).strip()
    note_pairs = _extract_key_value_pairs(notes)
    if note_pairs:
        for key, value in note_pairs:
            add_candidate(
                statement=f"{key}={value}",
                source_field="reporterNotes",
                verifier_ref="witness_proposer:reporterNotes.kv",
            )
    else:
        for clause in _split_claim_clauses(notes):
            add_candidate(
                statement=clause,
                source_field="reporterNotes",
                verifier_ref="witness_proposer:reporterNotes",
            )

    metadata = raw_incident.get("metadata")
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            text = _to_text(value).strip()
            if not text:
                continue
            add_candidate(
                statement=f"{key}={text}",
                source_field=f"metadata.{key}",
                verifier_ref="witness_proposer:metadata",
            )

    screenshot_filename = _to_text(raw_incident.get("screenshotFilename")).strip()
    if screenshot_filename:
        add_candidate(
            statement=f"screenshot={screenshot_filename}",
            source_field="screenshotFilename",
            witness_type="ui_fact",
            screenshot_ref=screenshot_filename,
            verifier_ref="witness_proposer:screenshot",
        )

    for idx, breadcrumb in enumerate(_as_list(raw_incident.get("breadcrumbs")), start=1):
        if not isinstance(breadcrumb, dict):
            continue
        category = _to_text(breadcrumb.get("category")).strip()
        message = _to_text(breadcrumb.get("message")).strip()
        timestamp = _to_text(breadcrumb.get("timestamp")).strip()
        if not message:
            continue

        source_field = f"breadcrumbs[{idx}]"
        breadcrumb_ref = source_field
        is_log = _is_log_breadcrumb(category, message)
        if is_log:
            kv_pairs = _extract_key_value_pairs(message)
            priority_pairs = [(key, value) for key, value in kv_pairs if _is_priority_log_key(key)]
            if priority_pairs:
                kept = priority_pairs[:6]
                for key, value in kept:
                    add_candidate(
                        statement=f"{key}={value}",
                        source_field=source_field,
                        witness_type="system_fact",
                        breadcrumb_ref=breadcrumb_ref,
                        is_log=True,
                        timestamp=timestamp,
                        verifier_ref="witness_proposer:breadcrumb.log",
                        category=category,
                    )
                continue

        raw_clauses = _split_claim_clauses(message)
        if not raw_clauses:
            continue

        key_value_clauses = _extract_key_value_pairs(message)
        if len(key_value_clauses) > 1:
            prefix = _normalize_statement(message.split(":", 1)[0]) if ":" in message else ""
            for key, value in key_value_clauses:
                statement = f"{prefix}: {key}={value}" if prefix else f"{key}={value}"
                add_candidate(
                    statement=statement,
                    source_field=source_field,
                    breadcrumb_ref=breadcrumb_ref,
                    is_log=is_log,
                    timestamp=timestamp,
                    verifier_ref="witness_proposer:breadcrumb.kv",
                    category=category,
                )
            continue

        for clause in raw_clauses:
            add_candidate(
                statement=clause,
                source_field=source_field,
                breadcrumb_ref=breadcrumb_ref,
                is_log=is_log,
                timestamp=timestamp,
                verifier_ref="witness_proposer:breadcrumb.text",
                category=category,
            )

    if incident_id:
        add_candidate(
            statement=f"incident_id={incident_id}",
            source_field="id",
            witness_type="system_fact",
            verifier_ref="witness_proposer:incident_id",
        )

    return candidates


def build_witness_set_v1(raw_incident: dict[str, Any], incident_id: str, produced_by: str) -> dict[str, Any]:
    candidates = propose_witness_candidates(raw_incident, incident_id)
    witnesses: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, Any]] = []
    fallback_added = False
    seen_statement_keys: set[tuple[str, str]] = set()

    for candidate in candidates:
        critique = critique_witness_candidate(candidate)
        witness_type = _to_text(candidate.get("witness_type"))
        statement = _normalize_statement(_to_text(candidate.get("statement")))
        statement_key = (witness_type, statement.lower())

        if critique["accepted"] and statement_key in seen_statement_keys:
            critique = {
                "accepted": False,
                "reasons": ["duplicate_statement"],
            }

        if not critique["accepted"]:
            rejected_candidates.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "statement": candidate.get("statement"),
                    "witness_type": candidate.get("witness_type"),
                    "reasons": critique["reasons"],
                }
            )
            continue
        seen_statement_keys.add(statement_key)

        witness_index = len(witnesses) + 1
        statement = _to_text(candidate.get("statement"))
        source_field = _to_text(candidate.get("source_field"))
        provenance = candidate.get("provenance")
        if not isinstance(provenance, dict):
            provenance = _empty_provenance()

        witness: dict[str, Any] = {
            "witness_id": f"{incident_id}:{witness_type}:{witness_index:04d}",
            "witness_type": witness_type,
            "statement": statement,
            "provenance": provenance,
            # Legacy aliases retained to avoid hard migration.
            "kind": witness_type,
            "content": statement,
            "source_field": source_field,
        }
        if _to_text(candidate.get("timestamp")):
            witness["timestamp"] = _to_text(candidate.get("timestamp"))
        witnesses.append(witness)

    if not witnesses:
        fallback_added = True
        fallback_witness = {
            "witness_id": f"{incident_id}:system_fact:0001",
            "witness_type": "system_fact",
            "statement": f"incident_id={incident_id}",
            "provenance": {
                "source_incident_ids": [incident_id] if incident_id else [],
                "raw_field_refs": ["id"],
                "breadcrumb_refs": [],
                "log_refs": [],
                "screenshot_refs": [],
                "verifier_refs": ["witness_critic:fallback"],
            },
            "kind": "system_fact",
            "content": f"incident_id={incident_id}",
            "source_field": "id",
        }
        witnesses.append(fallback_witness)

    # Metrics semantics:
    # - candidate_count counts critic-evaluated candidates (+fallback injection when needed)
    # - accepted_count/rejected_count partition candidate_count
    # - unsupported_count is the subset of rejected candidates with supportability failures
    candidate_count = len(candidates) + (1 if fallback_added else 0)
    unsupported_count = sum(
        1
        for rejected in rejected_candidates
        if any(
            _to_text(reason) in UNSUPPORTED_REJECTION_REASONS
            for reason in _as_list(rejected.get("reasons"))
        )
    )

    return {
        "schema_version": "WitnessSet.v1",
        "produced_by": produced_by,
        "incident_id": incident_id,
        "metrics": {
            "candidate_count": candidate_count,
            "accepted_count": len(witnesses),
            "rejected_count": len(rejected_candidates),
            "unsupported_count": unsupported_count,
        },
        "witnesses": witnesses,
        "rejected_candidates": rejected_candidates,
    }


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
    return build_witness_set_v1(raw_incident, incident_id, produced_by)


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
