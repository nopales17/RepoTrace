import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TypedDict

REPO_ROOT = Path(__file__).resolve().parent.parent


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


PROMISE_REQUIRED_FIELDS = (
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
)

PROMISE_REQUIRED_LIST_FIELDS = (
    "actors",
    "assets_or_rights",
    "interaction_families",
    "consistency_boundaries",
    "representations",
    "admin_or_external_surfaces",
    "stress_axes",
)

PROMISE_REQUIRED_STRING_FIELDS = (
    "promise_id",
    "statement",
    "why_it_exists",
    "protected_state",
    "settlement_horizon",
    "priority",
    "status",
)

PROMISE_ALLOWED_STATUSES = {"hypothesized", "accepted", "formalized"}


def _normalize_string_list(value: Any) -> list[str]:
    return [_to_text(item).strip() for item in _as_list(value) if _to_text(item).strip()]


def validate_promise_card(card: dict[str, Any], *, context: str = "promise") -> list[str]:
    if not isinstance(card, dict):
        return [f"{context} must be an object"]

    errors: list[str] = []
    missing = [field for field in PROMISE_REQUIRED_FIELDS if field not in card]
    if missing:
        errors.append(f"{context} missing required keys: {', '.join(missing)}")
        return errors

    for field in PROMISE_REQUIRED_STRING_FIELDS:
        if not _to_text(card.get(field)).strip():
            errors.append(f"{context}.{field} must be a non-empty string")

    for field in PROMISE_REQUIRED_LIST_FIELDS:
        if not _normalize_string_list(card.get(field)):
            errors.append(f"{context}.{field} must be a non-empty array of strings")

    confidence = card.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
        errors.append(f"{context}.confidence must be a number between 0 and 1")

    status = _to_text(card.get("status")).strip()
    if status not in PROMISE_ALLOWED_STATUSES:
        errors.append(
            f"{context}.status must be one of {', '.join(sorted(PROMISE_ALLOWED_STATUSES))}"
        )

    evidence_refs = card.get("evidence_refs")
    if not isinstance(evidence_refs, dict):
        errors.append(f"{context}.evidence_refs must be an object")
    else:
        required_refs = ("source_incident_ids", "retrieval_refs", "witness_refs", "fixture_refs", "verifier_refs")
        for ref_key in required_refs:
            if not _normalize_string_list(evidence_refs.get(ref_key)):
                errors.append(f"{context}.evidence_refs.{ref_key} must be a non-empty array of strings")

    return errors


def load_promise_registry_v1(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"promise registry must be an object: {path}")

    required_top_level = ("schema_version", "produced_by", "registry_version", "promises")
    missing = [key for key in required_top_level if key not in payload]
    if missing:
        raise ValueError(f"{path} missing required keys: {', '.join(missing)}")
    if payload.get("schema_version") != "PromiseRegistry.v1":
        raise ValueError(f"{path} schema_version must be PromiseRegistry.v1")

    registry_version = payload.get("registry_version")
    if not isinstance(registry_version, int) or registry_version < 1:
        raise ValueError(f"{path} registry_version must be an integer >= 1")

    promises = payload.get("promises")
    if not isinstance(promises, list):
        raise ValueError(f"{path} promises must be an array")

    normalized_promises: list[dict[str, Any]] = []
    seen_promise_ids: set[str] = set()
    for idx, raw_card in enumerate(promises, start=1):
        if not isinstance(raw_card, dict):
            raise ValueError(f"{path} promises[{idx}] must be an object")

        errors = validate_promise_card(raw_card, context=f"promises[{idx}]")
        if errors:
            raise ValueError(f"{path} invalid promise card: {'; '.join(errors)}")

        promise_id = _to_text(raw_card.get("promise_id")).strip()
        if promise_id in seen_promise_ids:
            raise ValueError(f"{path} duplicate promise_id: {promise_id}")
        seen_promise_ids.add(promise_id)

        normalized_card = dict(raw_card)
        for field in PROMISE_REQUIRED_LIST_FIELDS:
            normalized_card[field] = _normalize_string_list(raw_card.get(field))
        normalized_card["status"] = _to_text(raw_card.get("status")).strip()
        normalized_card["priority"] = _to_text(raw_card.get("priority")).strip()
        normalized_card["confidence"] = float(raw_card.get("confidence"))

        raw_refs = raw_card.get("evidence_refs")
        evidence_refs: dict[str, Any] = {}
        if isinstance(raw_refs, dict):
            for key, value in raw_refs.items():
                evidence_refs[_to_text(key)] = _normalize_string_list(value)
        normalized_card["evidence_refs"] = evidence_refs
        normalized_promises.append(normalized_card)

    normalized_promises.sort(key=lambda card: _to_text(card.get("promise_id")))

    normalized_payload = dict(payload)
    normalized_payload["promises"] = normalized_promises
    return normalized_payload


PROMISE_TOUCH_MAP_REQUIRED_FIELDS = (
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
)

PROMISE_TOUCH_MAP_REQUIRED_STRING_FIELDS = (
    "touch_map_id",
    "promise_id",
    "protected_state",
    "created_at",
    "updated_at",
)

PROMISE_TOUCH_SURFACE_REQUIRED_FIELDS = (
    "surface_id",
    "kind",
    "ref",
    "actor_scope",
    "notes",
)

PROMISE_TOUCH_INTERACTION_FAMILY_REQUIRED_FIELDS = (
    "family_id",
    "statement",
    "surface_ids",
    "actor_scope",
    "transition_refs",
)

PROMISE_TOUCH_CONSISTENCY_BOUNDARY_REQUIRED_FIELDS = (
    "boundary_id",
    "statement",
    "representation_a",
    "representation_b",
    "settlement_horizon",
    "notes",
)

PROMISE_TOUCH_SLICE_CANDIDATE_REQUIRED_FIELDS = (
    "slice_id",
    "interaction_family",
    "consistency_boundary",
    "rationale",
    "priority",
    "confidence",
    "status",
)

PROMISE_TOUCH_SLICE_ALLOWED_STATUSES = {"proposed", "accepted", "deferred", "exhausted"}


def _ensure_non_empty_string_fields(
    payload: dict[str, Any],
    *,
    fields: tuple[str, ...],
    context: str,
    errors: list[str],
) -> None:
    for field in fields:
        if not _to_text(payload.get(field)).strip():
            errors.append(f"{context}.{field} must be a non-empty string")


def validate_promise_touch_map_v1(
    touch_map: dict[str, Any], *, context: str = "promise_touch_map"
) -> list[str]:
    if not isinstance(touch_map, dict):
        return [f"{context} must be an object"]

    errors: list[str] = []
    missing = [field for field in PROMISE_TOUCH_MAP_REQUIRED_FIELDS if field not in touch_map]
    if missing:
        errors.append(f"{context} missing required keys: {', '.join(missing)}")
        return errors

    _ensure_non_empty_string_fields(
        touch_map,
        fields=PROMISE_TOUCH_MAP_REQUIRED_STRING_FIELDS,
        context=context,
        errors=errors,
    )

    purpose_context = touch_map.get("purpose_context")
    if isinstance(purpose_context, dict):
        if not purpose_context:
            errors.append(f"{context}.purpose_context must not be empty")
    elif not _to_text(purpose_context).strip():
        errors.append(f"{context}.purpose_context must be a non-empty string or object")

    actors = _normalize_string_list(touch_map.get("actors"))
    if not actors:
        errors.append(f"{context}.actors must be a non-empty array of strings")

    pressure_axes = _normalize_string_list(touch_map.get("pressure_axes"))
    if not pressure_axes:
        errors.append(f"{context}.pressure_axes must be a non-empty array of strings")

    evidence_refs = touch_map.get("evidence_refs")
    if not isinstance(evidence_refs, dict):
        errors.append(f"{context}.evidence_refs must be an object")

    mutable_surfaces = touch_map.get("mutable_surfaces")
    if not isinstance(mutable_surfaces, list) or not mutable_surfaces:
        errors.append(f"{context}.mutable_surfaces must be a non-empty array")
    else:
        seen_surface_ids: set[str] = set()
        for idx, raw_surface in enumerate(mutable_surfaces, start=1):
            entry_context = f"{context}.mutable_surfaces[{idx}]"
            if not isinstance(raw_surface, dict):
                errors.append(f"{entry_context} must be an object")
                continue
            missing_fields = [field for field in PROMISE_TOUCH_SURFACE_REQUIRED_FIELDS if field not in raw_surface]
            if missing_fields:
                errors.append(f"{entry_context} missing required keys: {', '.join(missing_fields)}")
                continue
            _ensure_non_empty_string_fields(
                raw_surface,
                fields=PROMISE_TOUCH_SURFACE_REQUIRED_FIELDS,
                context=entry_context,
                errors=errors,
            )
            surface_id = _to_text(raw_surface.get("surface_id")).strip()
            if surface_id:
                if surface_id in seen_surface_ids:
                    errors.append(f"{context}.mutable_surfaces duplicate surface_id: {surface_id}")
                seen_surface_ids.add(surface_id)

    interaction_families = touch_map.get("interaction_families")
    family_ids: set[str] = set()
    if not isinstance(interaction_families, list) or not interaction_families:
        errors.append(f"{context}.interaction_families must be a non-empty array")
    else:
        for idx, raw_family in enumerate(interaction_families, start=1):
            entry_context = f"{context}.interaction_families[{idx}]"
            if not isinstance(raw_family, dict):
                errors.append(f"{entry_context} must be an object")
                continue

            missing_fields = [
                field for field in PROMISE_TOUCH_INTERACTION_FAMILY_REQUIRED_FIELDS if field not in raw_family
            ]
            if missing_fields:
                errors.append(f"{entry_context} missing required keys: {', '.join(missing_fields)}")
                continue

            _ensure_non_empty_string_fields(
                raw_family,
                fields=("family_id", "statement", "actor_scope"),
                context=entry_context,
                errors=errors,
            )

            surface_ids = _normalize_string_list(raw_family.get("surface_ids"))
            if not surface_ids:
                errors.append(f"{entry_context}.surface_ids must be a non-empty array of strings")

            transition_refs = _normalize_string_list(raw_family.get("transition_refs"))
            if not transition_refs:
                errors.append(f"{entry_context}.transition_refs must be a non-empty array of strings")

            family_id = _to_text(raw_family.get("family_id")).strip()
            if family_id:
                if family_id in family_ids:
                    errors.append(f"{context}.interaction_families duplicate family_id: {family_id}")
                family_ids.add(family_id)

    consistency_boundaries = touch_map.get("consistency_boundaries")
    boundary_ids: set[str] = set()
    if not isinstance(consistency_boundaries, list) or not consistency_boundaries:
        errors.append(f"{context}.consistency_boundaries must be a non-empty array")
    else:
        for idx, raw_boundary in enumerate(consistency_boundaries, start=1):
            entry_context = f"{context}.consistency_boundaries[{idx}]"
            if not isinstance(raw_boundary, dict):
                errors.append(f"{entry_context} must be an object")
                continue

            missing_fields = [
                field
                for field in PROMISE_TOUCH_CONSISTENCY_BOUNDARY_REQUIRED_FIELDS
                if field not in raw_boundary
            ]
            if missing_fields:
                errors.append(f"{entry_context} missing required keys: {', '.join(missing_fields)}")
                continue

            _ensure_non_empty_string_fields(
                raw_boundary,
                fields=PROMISE_TOUCH_CONSISTENCY_BOUNDARY_REQUIRED_FIELDS,
                context=entry_context,
                errors=errors,
            )

            boundary_id = _to_text(raw_boundary.get("boundary_id")).strip()
            if boundary_id:
                if boundary_id in boundary_ids:
                    errors.append(f"{context}.consistency_boundaries duplicate boundary_id: {boundary_id}")
                boundary_ids.add(boundary_id)

    slice_candidates = touch_map.get("slice_candidates")
    if not isinstance(slice_candidates, list) or not slice_candidates:
        errors.append(f"{context}.slice_candidates must be a non-empty array")
    else:
        seen_slice_ids: set[str] = set()
        for idx, raw_slice in enumerate(slice_candidates, start=1):
            entry_context = f"{context}.slice_candidates[{idx}]"
            if not isinstance(raw_slice, dict):
                errors.append(f"{entry_context} must be an object")
                continue

            missing_fields = [field for field in PROMISE_TOUCH_SLICE_CANDIDATE_REQUIRED_FIELDS if field not in raw_slice]
            if missing_fields:
                errors.append(f"{entry_context} missing required keys: {', '.join(missing_fields)}")
                continue

            _ensure_non_empty_string_fields(
                raw_slice,
                fields=(
                    "slice_id",
                    "interaction_family",
                    "consistency_boundary",
                    "rationale",
                    "priority",
                    "status",
                ),
                context=entry_context,
                errors=errors,
            )

            confidence = raw_slice.get("confidence")
            if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
                errors.append(f"{entry_context}.confidence must be a number between 0 and 1")

            slice_status = _to_text(raw_slice.get("status")).strip()
            if slice_status not in PROMISE_TOUCH_SLICE_ALLOWED_STATUSES:
                errors.append(
                    f"{entry_context}.status must be one of "
                    f"{', '.join(sorted(PROMISE_TOUCH_SLICE_ALLOWED_STATUSES))}"
                )

            slice_id = _to_text(raw_slice.get("slice_id")).strip()
            if slice_id:
                if slice_id in seen_slice_ids:
                    errors.append(f"{context}.slice_candidates duplicate slice_id: {slice_id}")
                seen_slice_ids.add(slice_id)

            family_ref = _to_text(raw_slice.get("interaction_family")).strip()
            if family_ref and family_ids and family_ref not in family_ids:
                errors.append(
                    f"{entry_context}.interaction_family references unknown family_id: {family_ref}"
                )

            boundary_ref = _to_text(raw_slice.get("consistency_boundary")).strip()
            if boundary_ref and boundary_ids and boundary_ref not in boundary_ids:
                errors.append(
                    f"{entry_context}.consistency_boundary references unknown boundary_id: {boundary_ref}"
                )

    return errors


def _normalize_touch_map_purpose_context(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            normalized[_to_text(key)] = value[key]
        return normalized
    return _to_text(value).strip()


def _normalize_touch_map_evidence_refs(raw_refs: Any) -> dict[str, Any]:
    if not isinstance(raw_refs, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key in sorted(raw_refs):
        value = raw_refs[key]
        if isinstance(value, list):
            normalized[_to_text(key)] = _normalize_string_list(value)
            continue
        normalized[_to_text(key)] = value
    return normalized


def load_promise_touch_map_v1(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"promise touch map must be an object: {path}")

    required_top_level = ("schema_version", "produced_by", *PROMISE_TOUCH_MAP_REQUIRED_FIELDS)
    missing = [key for key in required_top_level if key not in payload]
    if missing:
        raise ValueError(f"{path} missing required keys: {', '.join(missing)}")
    if payload.get("schema_version") != "PromiseTouchMap.v1":
        raise ValueError(f"{path} schema_version must be PromiseTouchMap.v1")

    errors = validate_promise_touch_map_v1(payload, context="touch_map")
    if errors:
        raise ValueError(f"{path} invalid promise touch map: {'; '.join(errors)}")

    normalized = dict(payload)
    for field in PROMISE_TOUCH_MAP_REQUIRED_STRING_FIELDS:
        normalized[field] = _to_text(payload.get(field)).strip()

    normalized["purpose_context"] = _normalize_touch_map_purpose_context(payload.get("purpose_context"))
    normalized["actors"] = _normalize_string_list(payload.get("actors"))
    normalized["pressure_axes"] = _normalize_string_list(payload.get("pressure_axes"))
    normalized["evidence_refs"] = _normalize_touch_map_evidence_refs(payload.get("evidence_refs"))

    mutable_surfaces = payload.get("mutable_surfaces")
    normalized_surfaces: list[dict[str, Any]] = []
    if isinstance(mutable_surfaces, list):
        for raw_surface in mutable_surfaces:
            if not isinstance(raw_surface, dict):
                continue
            surface = dict(raw_surface)
            for field in PROMISE_TOUCH_SURFACE_REQUIRED_FIELDS:
                surface[field] = _to_text(raw_surface.get(field)).strip()
            normalized_surfaces.append(surface)
    normalized_surfaces.sort(key=lambda surface: _to_text(surface.get("surface_id")).strip())
    normalized["mutable_surfaces"] = normalized_surfaces

    interaction_families = payload.get("interaction_families")
    normalized_families: list[dict[str, Any]] = []
    if isinstance(interaction_families, list):
        for raw_family in interaction_families:
            if not isinstance(raw_family, dict):
                continue
            family = dict(raw_family)
            family["family_id"] = _to_text(raw_family.get("family_id")).strip()
            family["statement"] = _to_text(raw_family.get("statement")).strip()
            family["surface_ids"] = _normalize_string_list(raw_family.get("surface_ids"))
            family["actor_scope"] = _to_text(raw_family.get("actor_scope")).strip()
            family["transition_refs"] = _normalize_string_list(raw_family.get("transition_refs"))
            normalized_families.append(family)
    normalized_families.sort(key=lambda family: _to_text(family.get("family_id")).strip())
    normalized["interaction_families"] = normalized_families

    consistency_boundaries = payload.get("consistency_boundaries")
    normalized_boundaries: list[dict[str, Any]] = []
    if isinstance(consistency_boundaries, list):
        for raw_boundary in consistency_boundaries:
            if not isinstance(raw_boundary, dict):
                continue
            boundary = dict(raw_boundary)
            for field in PROMISE_TOUCH_CONSISTENCY_BOUNDARY_REQUIRED_FIELDS:
                boundary[field] = _to_text(raw_boundary.get(field)).strip()
            normalized_boundaries.append(boundary)
    normalized_boundaries.sort(key=lambda boundary: _to_text(boundary.get("boundary_id")).strip())
    normalized["consistency_boundaries"] = normalized_boundaries

    raw_slice_candidates = payload.get("slice_candidates")
    normalized_slices: list[dict[str, Any]] = []
    if isinstance(raw_slice_candidates, list):
        for raw_slice in raw_slice_candidates:
            if not isinstance(raw_slice, dict):
                continue
            slice_candidate = dict(raw_slice)
            for field in (
                "slice_id",
                "interaction_family",
                "consistency_boundary",
                "rationale",
                "priority",
                "status",
            ):
                slice_candidate[field] = _to_text(raw_slice.get(field)).strip()
            slice_candidate["confidence"] = float(raw_slice.get("confidence"))
            normalized_slices.append(slice_candidate)
    normalized_slices.sort(key=lambda slice_candidate: _to_text(slice_candidate.get("slice_id")).strip())
    normalized["slice_candidates"] = normalized_slices
    return normalized


def load_promise_touch_maps_from_dir_v1(touch_maps_dir: Path) -> list[dict[str, Any]]:
    if not touch_maps_dir.exists():
        return []
    if not touch_maps_dir.is_dir():
        raise ValueError(f"promise touch map path is not a directory: {touch_maps_dir}")

    deduped_by_touch_map_id: dict[str, dict[str, Any]] = {}
    for path in sorted(touch_maps_dir.glob("*.json")):
        touch_map = load_promise_touch_map_v1(path)
        touch_map_id = _to_text(touch_map.get("touch_map_id")).strip()
        if touch_map_id in deduped_by_touch_map_id:
            raise ValueError(f"duplicate touch_map_id in directory: {touch_map_id}")
        deduped_by_touch_map_id[touch_map_id] = touch_map

    return [deduped_by_touch_map_id[touch_map_id] for touch_map_id in sorted(deduped_by_touch_map_id)]


CHECK_CARD_REQUIRED_FIELDS = (
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
)

CHECK_CARD_REQUIRED_STRING_FIELDS = (
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
)

CHECK_CARD_REQUIRED_LIST_FIELDS = (
    "required_inputs",
    "procedure_steps",
    "expected_signals",
    "failure_signals",
    "evidence_outputs",
    "provenance_refs",
)

CHECK_CARD_ALLOWED_STATUSES = {"draft", "accepted", "deprecated"}
CHECK_CARD_ALLOWED_TYPES = {
    "inspection",
    "trace",
    "replay",
    "differential",
    "instrumentation",
    "minimization",
}


def validate_check_card_v1(check_card: dict[str, Any], *, context: str = "check_card") -> list[str]:
    if not isinstance(check_card, dict):
        return [f"{context} must be an object"]

    errors: list[str] = []
    missing = [field for field in CHECK_CARD_REQUIRED_FIELDS if field not in check_card]
    if missing:
        errors.append(f"{context} missing required keys: {', '.join(missing)}")
        return errors

    for field in CHECK_CARD_REQUIRED_STRING_FIELDS:
        if not _to_text(check_card.get(field)).strip():
            errors.append(f"{context}.{field} must be a non-empty string")

    for field in CHECK_CARD_REQUIRED_LIST_FIELDS:
        if not _normalize_string_list(check_card.get(field)):
            errors.append(f"{context}.{field} must be a non-empty array of strings")

    status = _to_text(check_card.get("status")).strip()
    if status not in CHECK_CARD_ALLOWED_STATUSES:
        errors.append(
            f"{context}.status must be one of {', '.join(sorted(CHECK_CARD_ALLOWED_STATUSES))}"
        )

    check_type = _to_text(check_card.get("check_type")).strip()
    if check_type not in CHECK_CARD_ALLOWED_TYPES:
        errors.append(
            f"{context}.check_type must be one of {', '.join(sorted(CHECK_CARD_ALLOWED_TYPES))}"
        )

    return errors


def _normalize_check_card_v1(check_card: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(check_card)
    for field in CHECK_CARD_REQUIRED_STRING_FIELDS:
        normalized[field] = _to_text(check_card.get(field)).strip()
    for field in CHECK_CARD_REQUIRED_LIST_FIELDS:
        normalized[field] = _normalize_string_list(check_card.get(field))
    normalized["status"] = _to_text(check_card.get("status")).strip()
    normalized["check_type"] = _to_text(check_card.get("check_type")).strip()
    return normalized


def load_promise_check_library_v1(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"promise check library must be an object: {path}")

    required_top_level = ("schema_version", "produced_by", "library_id", "library_version", "checks")
    missing = [key for key in required_top_level if key not in payload]
    if missing:
        raise ValueError(f"{path} missing required keys: {', '.join(missing)}")
    if payload.get("schema_version") != "PromiseCheckLibrary.v1":
        raise ValueError(f"{path} schema_version must be PromiseCheckLibrary.v1")

    library_id = _to_text(payload.get("library_id")).strip()
    if not library_id:
        raise ValueError(f"{path} library_id must be a non-empty string")

    library_version = payload.get("library_version")
    if not isinstance(library_version, int) or library_version < 1:
        raise ValueError(f"{path} library_version must be an integer >= 1")

    checks = payload.get("checks")
    if not isinstance(checks, list):
        raise ValueError(f"{path} checks must be an array")

    normalized_checks: list[dict[str, Any]] = []
    seen_check_ids: set[str] = set()
    for idx, raw_check in enumerate(checks, start=1):
        if not isinstance(raw_check, dict):
            raise ValueError(f"{path} checks[{idx}] must be an object")

        errors = validate_check_card_v1(raw_check, context=f"checks[{idx}]")
        if errors:
            raise ValueError(f"{path} invalid check card: {'; '.join(errors)}")

        check_id = _to_text(raw_check.get("check_id")).strip()
        if check_id in seen_check_ids:
            raise ValueError(f"{path} duplicate check_id: {check_id}")
        seen_check_ids.add(check_id)

        normalized_checks.append(_normalize_check_card_v1(raw_check))

    normalized_checks.sort(key=lambda check: _to_text(check.get("check_id")).strip())
    normalized = dict(payload)
    normalized["library_id"] = library_id
    normalized["checks"] = normalized_checks
    return normalized


def load_promise_check_libraries_from_dir_v1(libraries_dir: Path) -> list[dict[str, Any]]:
    if not libraries_dir.exists():
        return []
    if not libraries_dir.is_dir():
        raise ValueError(f"promise check library path is not a directory: {libraries_dir}")

    deduped_by_library_id: dict[str, dict[str, Any]] = {}
    for path in sorted(libraries_dir.glob("*.json")):
        library = load_promise_check_library_v1(path)
        library_id = _to_text(library.get("library_id")).strip()
        if library_id in deduped_by_library_id:
            raise ValueError(f"duplicate library_id in directory: {library_id}")
        deduped_by_library_id[library_id] = library

    return [deduped_by_library_id[library_id] for library_id in sorted(deduped_by_library_id)]


def suggest_checks_for_accepted_slice_candidate(
    touch_map: dict[str, Any],
    slice_candidate: dict[str, Any],
    check_library: dict[str, Any],
) -> list[dict[str, Any]]:
    touch_map_errors = validate_promise_touch_map_v1(touch_map, context="touch_map")
    if touch_map_errors:
        raise ValueError(f"invalid promise touch map: {'; '.join(touch_map_errors)}")
    if not isinstance(slice_candidate, dict):
        raise ValueError("slice_candidate must be an object")

    slice_status = _to_text(slice_candidate.get("status")).strip()
    if slice_status != "accepted":
        return []

    if not isinstance(check_library, dict):
        raise ValueError("check_library must be an object")
    checks = check_library.get("checks")
    if not isinstance(checks, list):
        raise ValueError("check_library.checks must be an array")

    family_by_id: dict[str, str] = {}
    for family in touch_map.get("interaction_families", []):
        if not isinstance(family, dict):
            continue
        family_id = _to_text(family.get("family_id")).strip()
        if family_id:
            family_by_id[family_id] = _to_text(family.get("statement")).strip()

    boundary_by_id: dict[str, str] = {}
    for boundary in touch_map.get("consistency_boundaries", []):
        if not isinstance(boundary, dict):
            continue
        boundary_id = _to_text(boundary.get("boundary_id")).strip()
        if boundary_id:
            boundary_by_id[boundary_id] = _to_text(boundary.get("statement")).strip()

    family_id = _to_text(slice_candidate.get("interaction_family")).strip()
    boundary_id = _to_text(slice_candidate.get("consistency_boundary")).strip()
    if not family_id or not boundary_id:
        raise ValueError("slice_candidate must include interaction_family and consistency_boundary")

    family_statement = family_by_id.get(family_id, "")
    boundary_statement = boundary_by_id.get(boundary_id, "")
    compatible_family_refs = {family_id}
    compatible_boundary_refs = {boundary_id}
    if family_statement:
        compatible_family_refs.add(family_statement)
    if boundary_statement:
        compatible_boundary_refs.add(boundary_statement)

    promise_id = _to_text(touch_map.get("promise_id")).strip()
    strength_rank = {
        "strong": 0,
        "high": 0,
        "moderate": 1,
        "medium": 1,
        "low": 2,
        "weak": 2,
    }
    cost_rank = {
        "low": 0,
        "medium": 1,
        "high": 2,
    }
    status_rank = {"accepted": 0, "draft": 1}

    suggestions: list[dict[str, Any]] = []
    for raw_check in checks:
        if not isinstance(raw_check, dict):
            continue

        errors = validate_check_card_v1(raw_check, context="check")
        if errors:
            continue

        check = _normalize_check_card_v1(raw_check)
        check_status = _to_text(check.get("status")).strip()
        if check_status == "deprecated":
            continue
        if _to_text(check.get("promise_id")).strip() != promise_id:
            continue

        check_family = _to_text(check.get("interaction_family")).strip()
        check_boundary = _to_text(check.get("consistency_boundary")).strip()
        if check_family not in compatible_family_refs:
            continue
        if check_boundary not in compatible_boundary_refs:
            continue

        suggestion = dict(check)
        suggestion["source_slice_id"] = _to_text(slice_candidate.get("slice_id")).strip()
        suggestion["manual_only"] = True
        suggestion["compatibility"] = (
            f"promise+family+boundary match for {suggestion['source_slice_id'] or 'accepted-slice'}"
        )
        suggestions.append(suggestion)

    suggestions.sort(
        key=lambda check: (
            status_rank.get(_to_text(check.get("status")).strip(), 9),
            strength_rank.get(_to_text(check.get("strength")).strip().lower(), 9),
            cost_rank.get(_to_text(check.get("cost")).strip().lower(), 9),
            _to_text(check.get("check_id")).strip(),
        )
    )
    return suggestions


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return slug.strip("-") or "unknown"


def derive_manual_task_stubs_from_touch_map(
    touch_map: dict[str, Any],
    *,
    produced_by: str = "manual:promise-touch-map",
    assigned_frame_id: str = "frame:manual-assignment-required",
    created_at: str | None = None,
) -> list[dict[str, Any]]:
    errors = validate_promise_touch_map_v1(touch_map, context="touch_map")
    if errors:
        raise ValueError(f"invalid promise touch map: {'; '.join(errors)}")

    family_by_id: dict[str, dict[str, Any]] = {}
    for family in touch_map.get("interaction_families", []):
        if isinstance(family, dict):
            family_id = _to_text(family.get("family_id")).strip()
            if family_id:
                family_by_id[family_id] = family

    boundary_by_id: dict[str, dict[str, Any]] = {}
    for boundary in touch_map.get("consistency_boundaries", []):
        if isinstance(boundary, dict):
            boundary_id = _to_text(boundary.get("boundary_id")).strip()
            if boundary_id:
                boundary_by_id[boundary_id] = boundary

    promise_id = _to_text(touch_map.get("promise_id")).strip()
    touch_map_id = _to_text(touch_map.get("touch_map_id")).strip()
    timestamp = _to_text(created_at).strip() or utc_now_iso()

    stubs: list[dict[str, Any]] = []
    for raw_slice in sorted(
        [item for item in touch_map.get("slice_candidates", []) if isinstance(item, dict)],
        key=lambda item: _to_text(item.get("slice_id")).strip(),
    ):
        if _to_text(raw_slice.get("status")).strip() != "accepted":
            continue

        slice_id = _to_text(raw_slice.get("slice_id")).strip()
        family_id = _to_text(raw_slice.get("interaction_family")).strip()
        boundary_id = _to_text(raw_slice.get("consistency_boundary")).strip()
        family = family_by_id.get(family_id, {})
        boundary = boundary_by_id.get(boundary_id, {})

        interaction_family = (
            _to_text(family.get("statement")).strip()
            or family_id
        )
        consistency_boundary = (
            _to_text(boundary.get("statement")).strip()
            or boundary_id
        )

        stubs.append(
            {
                "schema_version": "PromiseTraversalTask.v1",
                "produced_by": _to_text(produced_by).strip() or "manual:promise-touch-map",
                "task_id": f"task-{_slugify(promise_id)}-{_slugify(slice_id)}-stub",
                "promise_id": promise_id,
                "interaction_family": interaction_family,
                "consistency_boundary": consistency_boundary,
                "assigned_frame_id": _to_text(assigned_frame_id).strip() or "frame:manual-assignment-required",
                "objective": (
                    "Manual slice scan from PromiseTouchMap accepted candidate "
                    f"{slice_id}: validate {interaction_family} x {consistency_boundary}."
                ),
                "status": "queued",
                "budget": {
                    "checks_remaining": 1,
                },
                "created_at": timestamp,
                "updated_at": timestamp,
                "source_touch_map_id": touch_map_id,
                "source_slice_id": slice_id,
                "source_interaction_family_id": family_id,
                "source_consistency_boundary_id": boundary_id,
            }
        )

    return stubs


PROMISE_FRAME_REQUIRED_FIELDS = (
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
)

PROMISE_FRAME_REQUIRED_STRING_FIELDS = (
    "frame_id",
    "incident_id",
    "promise_id",
    "interaction_family",
    "consistency_boundary",
    "focus_statement",
    "violation_shape",
    "live_anomaly_id",
    "status",
)

PROMISE_FRAME_REQUIRED_LIST_FIELDS = (
    "touchpoints_remaining",
    "pressure_axes_remaining",
)

PROMISE_FRAME_WITNESS_BUCKETS = ("support", "pressure", "contradiction")

PROMISE_FRAME_ALLOWED_STATUSES = {
    "active",
    "blocked",
    "anomaly_found",
    "killed",
    "survives",
    "exhausted",
}

PROMISE_FRAME_NEXT_CHECK_REQUIRED_STRING_FIELDS = (
    "kind",
    "prompt",
)


def validate_promise_frame_checkpoint(frame: dict[str, Any], *, context: str = "promise_frame") -> list[str]:
    if not isinstance(frame, dict):
        return [f"{context} must be an object"]

    errors: list[str] = []
    missing = [field for field in PROMISE_FRAME_REQUIRED_FIELDS if field not in frame]
    if missing:
        errors.append(f"{context} missing required keys: {', '.join(missing)}")
        return errors

    for field in PROMISE_FRAME_REQUIRED_STRING_FIELDS:
        if not _to_text(frame.get(field)).strip():
            errors.append(f"{context}.{field} must be a non-empty string")

    for field in PROMISE_FRAME_REQUIRED_LIST_FIELDS:
        value = frame.get(field)
        if not isinstance(value, list):
            errors.append(f"{context}.{field} must be an array of strings")
            continue
        if any(not _to_text(item).strip() for item in value):
            errors.append(f"{context}.{field} entries must be non-empty strings")

    witness_ids = frame.get("witness_ids")
    if not isinstance(witness_ids, dict):
        errors.append(f"{context}.witness_ids must be an object")
    else:
        for bucket in PROMISE_FRAME_WITNESS_BUCKETS:
            bucket_values = witness_ids.get(bucket)
            if not isinstance(bucket_values, list):
                errors.append(f"{context}.witness_ids.{bucket} must be an array of strings")
                continue
            if any(not _to_text(item).strip() for item in bucket_values):
                errors.append(f"{context}.witness_ids.{bucket} entries must be non-empty strings")

    next_check = frame.get("next_check")
    if not isinstance(next_check, dict):
        errors.append(f"{context}.next_check must be an object")
    else:
        if not next_check:
            errors.append(f"{context}.next_check must not be empty")
        for field in PROMISE_FRAME_NEXT_CHECK_REQUIRED_STRING_FIELDS:
            if not _to_text(next_check.get(field)).strip():
                errors.append(f"{context}.next_check.{field} must be a non-empty string")

    budget = frame.get("budget")
    if not isinstance(budget, dict):
        errors.append(f"{context}.budget must be an object")
    else:
        checks_remaining = budget.get("checks_remaining")
        if not isinstance(checks_remaining, int) or checks_remaining < 0:
            errors.append(f"{context}.budget.checks_remaining must be an integer >= 0")

    status = _to_text(frame.get("status")).strip()
    if status not in PROMISE_FRAME_ALLOWED_STATUSES:
        errors.append(
            f"{context}.status must be one of {', '.join(sorted(PROMISE_FRAME_ALLOWED_STATUSES))}"
        )

    return errors


def load_promise_frame_checkpoint_v1(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"promise frame checkpoint must be an object: {path}")
    if payload.get("schema_version") != "PromiseFrameCheckpoint.v1":
        raise ValueError(f"{path} schema_version must be PromiseFrameCheckpoint.v1")

    errors = validate_promise_frame_checkpoint(payload, context="checkpoint")
    if errors:
        raise ValueError(f"{path} invalid promise frame checkpoint: {'; '.join(errors)}")

    normalized = dict(payload)
    for field in PROMISE_FRAME_REQUIRED_STRING_FIELDS:
        normalized[field] = _to_text(payload.get(field)).strip()

    for field in PROMISE_FRAME_REQUIRED_LIST_FIELDS:
        normalized[field] = _normalize_string_list(payload.get(field))

    raw_witness_ids = payload.get("witness_ids")
    witness_ids: dict[str, list[str]] = {}
    if isinstance(raw_witness_ids, dict):
        for bucket in PROMISE_FRAME_WITNESS_BUCKETS:
            witness_ids[bucket] = _normalize_string_list(raw_witness_ids.get(bucket))
    normalized["witness_ids"] = witness_ids

    raw_next_check = payload.get("next_check")
    next_check = dict(raw_next_check) if isinstance(raw_next_check, dict) else {}
    for field in PROMISE_FRAME_NEXT_CHECK_REQUIRED_STRING_FIELDS:
        next_check[field] = _to_text(next_check.get(field)).strip()
    normalized["next_check"] = next_check

    raw_budget = payload.get("budget")
    budget = dict(raw_budget) if isinstance(raw_budget, dict) else {}
    budget["checks_remaining"] = int(budget.get("checks_remaining", 0))
    normalized["budget"] = budget

    normalized["status"] = _to_text(payload.get("status")).strip()
    return normalized


def load_promise_frames_for_incident_v1(frames_root: Path, incident_id: str) -> list[dict[str, Any]]:
    normalized_incident_id = _to_text(incident_id).strip()
    if not normalized_incident_id:
        raise ValueError("incident_id must be non-empty")

    incident_dir = frames_root / normalized_incident_id
    if not incident_dir.exists():
        return []
    if not incident_dir.is_dir():
        raise ValueError(f"incident promise frame path is not a directory: {incident_dir}")

    deduped_by_frame_id: dict[str, dict[str, Any]] = {}
    for path in sorted(incident_dir.glob("*.json")):
        frame = load_promise_frame_checkpoint_v1(path)
        if _to_text(frame.get("incident_id")).strip() != normalized_incident_id:
            raise ValueError(f"{path} incident_id must match directory incident: {normalized_incident_id}")
        frame_id = _to_text(frame.get("frame_id")).strip()
        if frame_id in deduped_by_frame_id:
            raise ValueError(f"duplicate frame_id in incident directory: {frame_id}")
        deduped_by_frame_id[frame_id] = frame

    return [deduped_by_frame_id[frame_id] for frame_id in sorted(deduped_by_frame_id)]


PROMISE_COVERAGE_REQUIRED_FIELDS = (
    "promise_id",
    "interaction_family",
    "consistency_boundary",
    "status",
    "last_session_ref",
    "notes",
    "updated_at",
)

PROMISE_COVERAGE_REQUIRED_NON_EMPTY_STRING_FIELDS = (
    "promise_id",
    "interaction_family",
    "consistency_boundary",
    "status",
    "last_session_ref",
    "updated_at",
)

PROMISE_COVERAGE_ALLOWED_STATUSES = {
    "unseen",
    "mapped",
    "scanned",
    "anomaly_found",
    "killed",
    "survives",
}

PROMISE_COVERAGE_KEY_FIELDS = (
    "promise_id",
    "interaction_family",
    "consistency_boundary",
)

FRAME_TO_COVERAGE_STATUS = {
    "active": "scanned",
    "blocked": "scanned",
    "anomaly_found": "anomaly_found",
    "killed": "killed",
    "survives": "survives",
    "exhausted": "scanned",
}


def validate_promise_coverage_cell(cell: dict[str, Any], *, context: str = "coverage_cell") -> list[str]:
    if not isinstance(cell, dict):
        return [f"{context} must be an object"]

    errors: list[str] = []
    missing = [field for field in PROMISE_COVERAGE_REQUIRED_FIELDS if field not in cell]
    if missing:
        errors.append(f"{context} missing required keys: {', '.join(missing)}")
        return errors

    for field in PROMISE_COVERAGE_REQUIRED_NON_EMPTY_STRING_FIELDS:
        if not _to_text(cell.get(field)).strip():
            errors.append(f"{context}.{field} must be a non-empty string")

    if not isinstance(cell.get("notes"), str):
        errors.append(f"{context}.notes must be a string")

    status = _to_text(cell.get("status")).strip()
    if status not in PROMISE_COVERAGE_ALLOWED_STATUSES:
        errors.append(
            f"{context}.status must be one of {', '.join(sorted(PROMISE_COVERAGE_ALLOWED_STATUSES))}"
        )

    return errors


def _coverage_key(cell: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _to_text(cell.get("promise_id")).strip(),
        _to_text(cell.get("interaction_family")).strip(),
        _to_text(cell.get("consistency_boundary")).strip(),
    )


def load_promise_coverage_ledger_v1(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"promise coverage ledger must be an object: {path}")

    required_top_level = ("schema_version", "produced_by", "ledger_version", "coverage")
    missing = [key for key in required_top_level if key not in payload]
    if missing:
        raise ValueError(f"{path} missing required keys: {', '.join(missing)}")
    if payload.get("schema_version") != "PromiseCoverageLedger.v1":
        raise ValueError(f"{path} schema_version must be PromiseCoverageLedger.v1")

    ledger_version = payload.get("ledger_version")
    if not isinstance(ledger_version, int) or ledger_version < 1:
        raise ValueError(f"{path} ledger_version must be an integer >= 1")

    coverage = payload.get("coverage")
    if not isinstance(coverage, list):
        raise ValueError(f"{path} coverage must be an array")

    normalized_coverage: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for idx, raw_cell in enumerate(coverage, start=1):
        if not isinstance(raw_cell, dict):
            raise ValueError(f"{path} coverage[{idx}] must be an object")

        errors = validate_promise_coverage_cell(raw_cell, context=f"coverage[{idx}]")
        if errors:
            raise ValueError(f"{path} invalid coverage cell: {'; '.join(errors)}")

        key = _coverage_key(raw_cell)
        if key in seen_keys:
            raise ValueError(f"{path} duplicate coverage key: {key[0]} | {key[1]} | {key[2]}")
        seen_keys.add(key)

        normalized_cell = dict(raw_cell)
        for field in PROMISE_COVERAGE_REQUIRED_NON_EMPTY_STRING_FIELDS:
            normalized_cell[field] = _to_text(raw_cell.get(field)).strip()
        normalized_cell["notes"] = _to_text(raw_cell.get("notes"))
        normalized_coverage.append(normalized_cell)

    normalized_coverage.sort(key=_coverage_key)
    normalized_payload = dict(payload)
    normalized_payload["coverage"] = normalized_coverage
    return normalized_payload


def update_coverage_cell_from_frame_outcome(
    ledger: dict[str, Any],
    frame_outcome: dict[str, Any],
    *,
    notes: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(ledger, dict):
        raise ValueError("ledger must be an object")
    if not isinstance(frame_outcome, dict):
        raise ValueError("frame_outcome must be an object")

    promise_id = _to_text(frame_outcome.get("promise_id")).strip()
    interaction_family = _to_text(frame_outcome.get("interaction_family")).strip()
    consistency_boundary = _to_text(frame_outcome.get("consistency_boundary")).strip()
    frame_id = _to_text(frame_outcome.get("frame_id")).strip()
    frame_status = _to_text(frame_outcome.get("status")).strip()

    if not promise_id or not interaction_family or not consistency_boundary:
        raise ValueError("frame_outcome must include promise_id, interaction_family, and consistency_boundary")
    if frame_status not in FRAME_TO_COVERAGE_STATUS:
        raise ValueError(f"unsupported frame outcome status: {frame_status}")

    target_key = (promise_id, interaction_family, consistency_boundary)
    coverage = ledger.get("coverage")
    if not isinstance(coverage, list):
        raise ValueError("ledger.coverage must be an array")

    next_status = FRAME_TO_COVERAGE_STATUS[frame_status]
    terminal_statuses = {"anomaly_found", "killed", "survives"}
    normalized_cells: list[dict[str, Any]] = []
    found = False

    for raw_cell in coverage:
        if not isinstance(raw_cell, dict):
            raise ValueError("ledger.coverage entries must be objects")
        cell = dict(raw_cell)
        if _coverage_key(cell) == target_key:
            found = True
            current_status = _to_text(cell.get("status")).strip()
            if current_status in terminal_statuses and next_status == "scanned":
                resolved_status = current_status
            else:
                resolved_status = next_status
            cell["status"] = resolved_status
            cell["last_session_ref"] = frame_id or _to_text(cell.get("last_session_ref")).strip()
            if notes is not None:
                cell["notes"] = notes
            else:
                cell["notes"] = _to_text(cell.get("notes"))
            cell["updated_at"] = (
                _to_text(updated_at).strip()
                or _to_text(frame_outcome.get("updated_at")).strip()
                or utc_now_iso()
            )
        normalized_cells.append(cell)

    if not found:
        raise ValueError(
            "no coverage cell found for frame outcome key: "
            f"{target_key[0]} | {target_key[1]} | {target_key[2]}"
        )

    normalized_cells.sort(key=_coverage_key)
    normalized_ledger = dict(ledger)
    normalized_ledger["coverage"] = normalized_cells
    return normalized_ledger


PROMISE_TASK_REQUIRED_FIELDS = (
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
)

PROMISE_TASK_REQUIRED_STRING_FIELDS = (
    "task_id",
    "promise_id",
    "interaction_family",
    "consistency_boundary",
    "assigned_frame_id",
    "objective",
    "status",
    "created_at",
    "updated_at",
)

PROMISE_TASK_ALLOWED_STATUSES = {"queued", "active", "blocked", "done"}


def validate_promise_traversal_task(task: dict[str, Any], *, context: str = "promise_task") -> list[str]:
    if not isinstance(task, dict):
        return [f"{context} must be an object"]

    errors: list[str] = []
    missing = [field for field in PROMISE_TASK_REQUIRED_FIELDS if field not in task]
    if missing:
        errors.append(f"{context} missing required keys: {', '.join(missing)}")
        return errors

    for field in PROMISE_TASK_REQUIRED_STRING_FIELDS:
        if not _to_text(task.get(field)).strip():
            errors.append(f"{context}.{field} must be a non-empty string")

    if not isinstance(task.get("budget"), dict):
        errors.append(f"{context}.budget must be an object")

    status = _to_text(task.get("status")).strip()
    if status not in PROMISE_TASK_ALLOWED_STATUSES:
        errors.append(
            f"{context}.status must be one of {', '.join(sorted(PROMISE_TASK_ALLOWED_STATUSES))}"
        )

    return errors


def load_promise_traversal_task_v1(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"promise traversal task must be an object: {path}")
    if payload.get("schema_version") != "PromiseTraversalTask.v1":
        raise ValueError(f"{path} schema_version must be PromiseTraversalTask.v1")

    errors = validate_promise_traversal_task(payload, context="task")
    if errors:
        raise ValueError(f"{path} invalid promise traversal task: {'; '.join(errors)}")

    normalized = dict(payload)
    for field in PROMISE_TASK_REQUIRED_STRING_FIELDS:
        normalized[field] = _to_text(payload.get(field)).strip()
    normalized["status"] = _to_text(payload.get("status")).strip()

    raw_budget = payload.get("budget")
    normalized["budget"] = dict(raw_budget) if isinstance(raw_budget, dict) else {}
    return normalized


def load_promise_tasks_from_dir_v1(tasks_dir: Path) -> list[dict[str, Any]]:
    if not tasks_dir.exists():
        return []
    if not tasks_dir.is_dir():
        raise ValueError(f"promise tasks path is not a directory: {tasks_dir}")

    deduped_by_task_id: dict[str, dict[str, Any]] = {}
    for path in sorted(tasks_dir.glob("*.json")):
        task = load_promise_traversal_task_v1(path)
        task_id = _to_text(task.get("task_id")).strip()
        if task_id in deduped_by_task_id:
            raise ValueError(f"duplicate task_id in directory: {task_id}")
        deduped_by_task_id[task_id] = task

    return [deduped_by_task_id[task_id] for task_id in sorted(deduped_by_task_id)]


PROMISE_SCAN_OUTCOME_REQUIRED_FIELDS = (
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
)

PROMISE_SCAN_OUTCOME_REQUIRED_STRING_FIELDS = (
    "outcome_id",
    "task_id",
    "frame_id",
    "incident_id",
    "promise_id",
    "interaction_family",
    "consistency_boundary",
    "outcome",
    "summary",
    "next_action",
    "resulting_coverage_status",
    "resulting_task_status",
    "created_at",
)

PROMISE_SCAN_OUTCOME_ALLOWED_OUTCOMES = {
    "killed",
    "anomaly_found",
    "survives",
    "exhausted",
    "blocked",
}


def validate_promise_scan_outcome(
    outcome: dict[str, Any], *, context: str = "promise_scan_outcome"
) -> list[str]:
    if not isinstance(outcome, dict):
        return [f"{context} must be an object"]

    errors: list[str] = []
    missing = [field for field in PROMISE_SCAN_OUTCOME_REQUIRED_FIELDS if field not in outcome]
    if missing:
        errors.append(f"{context} missing required keys: {', '.join(missing)}")
        return errors

    for field in PROMISE_SCAN_OUTCOME_REQUIRED_STRING_FIELDS:
        if not _to_text(outcome.get(field)).strip():
            errors.append(f"{context}.{field} must be a non-empty string")

    raw_outcome = _to_text(outcome.get("outcome")).strip()
    if raw_outcome not in PROMISE_SCAN_OUTCOME_ALLOWED_OUTCOMES:
        errors.append(
            f"{context}.outcome must be one of {', '.join(sorted(PROMISE_SCAN_OUTCOME_ALLOWED_OUTCOMES))}"
        )

    for key in ("witness_ids_added", "anomaly_ids"):
        raw_items = outcome.get(key)
        if not isinstance(raw_items, list):
            errors.append(f"{context}.{key} must be an array of strings")
            continue
        if any(not _to_text(item).strip() for item in raw_items):
            errors.append(f"{context}.{key} entries must be non-empty strings")

    killed_reason = outcome.get("killed_reason")
    if killed_reason is not None and not _to_text(killed_reason).strip():
        errors.append(f"{context}.killed_reason must be null or a non-empty string")
    if raw_outcome == "killed" and not _to_text(killed_reason).strip():
        errors.append(f"{context}.killed_reason must be non-empty when outcome is killed")

    next_action = _to_text(outcome.get("next_action")).strip()
    if not next_action:
        errors.append(f"{context}.next_action must be a non-empty string")

    resulting_coverage_status = _to_text(outcome.get("resulting_coverage_status")).strip()
    if resulting_coverage_status not in PROMISE_COVERAGE_ALLOWED_STATUSES:
        errors.append(
            f"{context}.resulting_coverage_status must be one of "
            f"{', '.join(sorted(PROMISE_COVERAGE_ALLOWED_STATUSES))}"
        )

    resulting_task_status = _to_text(outcome.get("resulting_task_status")).strip()
    if resulting_task_status not in PROMISE_TASK_ALLOWED_STATUSES:
        errors.append(
            f"{context}.resulting_task_status must be one of {', '.join(sorted(PROMISE_TASK_ALLOWED_STATUSES))}"
        )

    return errors


def load_promise_scan_outcome_v1(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"promise scan outcome must be an object: {path}")
    if payload.get("schema_version") != "PromiseScanOutcome.v1":
        raise ValueError(f"{path} schema_version must be PromiseScanOutcome.v1")

    errors = validate_promise_scan_outcome(payload, context="scan_outcome")
    if errors:
        raise ValueError(f"{path} invalid promise scan outcome: {'; '.join(errors)}")

    normalized = dict(payload)
    for field in PROMISE_SCAN_OUTCOME_REQUIRED_STRING_FIELDS:
        normalized[field] = _to_text(payload.get(field)).strip()

    normalized["witness_ids_added"] = _normalize_string_list(payload.get("witness_ids_added"))
    normalized["anomaly_ids"] = _normalize_string_list(payload.get("anomaly_ids"))
    raw_killed_reason = payload.get("killed_reason")
    normalized["killed_reason"] = None if raw_killed_reason is None else _to_text(raw_killed_reason).strip()
    normalized["outcome"] = _to_text(payload.get("outcome")).strip()
    normalized["resulting_coverage_status"] = _to_text(payload.get("resulting_coverage_status")).strip()
    normalized["resulting_task_status"] = _to_text(payload.get("resulting_task_status")).strip()
    return normalized


def load_promise_scan_outcomes_for_incident_v1(
    outcomes_root: Path, incident_id: str
) -> list[dict[str, Any]]:
    normalized_incident_id = _to_text(incident_id).strip()
    if not normalized_incident_id:
        raise ValueError("incident_id must be non-empty")

    incident_dir = outcomes_root / normalized_incident_id
    if not incident_dir.exists():
        return []
    if not incident_dir.is_dir():
        raise ValueError(f"incident promise outcome path is not a directory: {incident_dir}")

    deduped_by_outcome_id: dict[str, dict[str, Any]] = {}
    for path in sorted(incident_dir.glob("*.json")):
        outcome = load_promise_scan_outcome_v1(path)
        if _to_text(outcome.get("incident_id")).strip() != normalized_incident_id:
            raise ValueError(f"{path} incident_id must match directory incident: {normalized_incident_id}")
        outcome_id = _to_text(outcome.get("outcome_id")).strip()
        if outcome_id in deduped_by_outcome_id:
            raise ValueError(f"duplicate outcome_id in incident directory: {outcome_id}")
        deduped_by_outcome_id[outcome_id] = outcome

    return [deduped_by_outcome_id[outcome_id] for outcome_id in sorted(deduped_by_outcome_id)]


def apply_promise_scan_outcome_statuses(
    coverage_cell: dict[str, Any],
    task: dict[str, Any],
    scan_outcome: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(coverage_cell, dict):
        raise ValueError("coverage_cell must be an object")
    if not isinstance(task, dict):
        raise ValueError("task must be an object")
    if not isinstance(scan_outcome, dict):
        raise ValueError("scan_outcome must be an object")

    coverage_errors = validate_promise_coverage_cell(coverage_cell, context="coverage_cell")
    if coverage_errors:
        raise ValueError(f"invalid coverage_cell: {'; '.join(coverage_errors)}")

    task_errors = validate_promise_traversal_task(task, context="task")
    if task_errors:
        raise ValueError(f"invalid task: {'; '.join(task_errors)}")

    outcome_errors = validate_promise_scan_outcome(scan_outcome, context="scan_outcome")
    if outcome_errors:
        raise ValueError(f"invalid scan_outcome: {'; '.join(outcome_errors)}")

    outcome_key = (
        _to_text(scan_outcome.get("promise_id")).strip(),
        _to_text(scan_outcome.get("interaction_family")).strip(),
        _to_text(scan_outcome.get("consistency_boundary")).strip(),
    )
    coverage_key = (
        _to_text(coverage_cell.get("promise_id")).strip(),
        _to_text(coverage_cell.get("interaction_family")).strip(),
        _to_text(coverage_cell.get("consistency_boundary")).strip(),
    )
    task_key = (
        _to_text(task.get("promise_id")).strip(),
        _to_text(task.get("interaction_family")).strip(),
        _to_text(task.get("consistency_boundary")).strip(),
    )

    if coverage_key != outcome_key:
        raise ValueError("malformed linkage: scan outcome key does not match coverage cell key")
    if task_key != outcome_key:
        raise ValueError("malformed linkage: scan outcome key does not match task key")
    if _to_text(scan_outcome.get("task_id")).strip() != _to_text(task.get("task_id")).strip():
        raise ValueError("malformed linkage: scan outcome task_id does not match task.task_id")
    if _to_text(scan_outcome.get("frame_id")).strip() != _to_text(task.get("assigned_frame_id")).strip():
        raise ValueError("malformed linkage: scan outcome frame_id does not match task.assigned_frame_id")

    updated_coverage_cell = dict(coverage_cell)
    updated_coverage_cell["status"] = _to_text(scan_outcome.get("resulting_coverage_status")).strip()

    updated_task = dict(task)
    updated_task["status"] = _to_text(scan_outcome.get("resulting_task_status")).strip()
    return updated_coverage_cell, updated_task


PROMISE_WORK_PACKET_REQUIRED_FIELDS = (
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
)

PROMISE_WORK_PACKET_REQUIRED_STRING_FIELDS = (
    "work_packet_id",
    "incident_id",
    "promise_id",
    "frame_ref",
    "task_ref",
    "touch_map_ref",
    "coverage_ref",
    "objective",
    "status",
    "created_at",
    "updated_at",
)

PROMISE_WORK_PACKET_ALLOWED_STATUSES = {
    "draft",
    "ready",
    "active",
    "blocked",
    "completed",
    "stale",
}


def validate_promise_work_packet_v1(
    packet: dict[str, Any], *, context: str = "promise_work_packet"
) -> list[str]:
    if not isinstance(packet, dict):
        return [f"{context} must be an object"]

    errors: list[str] = []
    missing = [field for field in PROMISE_WORK_PACKET_REQUIRED_FIELDS if field not in packet]
    if missing:
        errors.append(f"{context} missing required keys: {', '.join(missing)}")
        return errors

    for field in PROMISE_WORK_PACKET_REQUIRED_STRING_FIELDS:
        if not _to_text(packet.get(field)).strip():
            errors.append(f"{context}.{field} must be a non-empty string")

    slice_obj = packet.get("slice")
    if not isinstance(slice_obj, dict):
        errors.append(f"{context}.slice must be an object")
    else:
        for field in ("interaction_family", "consistency_boundary"):
            if not _to_text(slice_obj.get(field)).strip():
                errors.append(f"{context}.slice.{field} must be a non-empty string")

    status = _to_text(packet.get("status")).strip()
    if status not in PROMISE_WORK_PACKET_ALLOWED_STATUSES:
        errors.append(
            f"{context}.status must be one of {', '.join(sorted(PROMISE_WORK_PACKET_ALLOWED_STATUSES))}"
        )

    check_ids = packet.get("check_ids")
    if not isinstance(check_ids, list):
        errors.append(f"{context}.check_ids must be an array of strings")
    else:
        normalized_check_ids = [_to_text(item).strip() for item in check_ids]
        if any(not item for item in normalized_check_ids):
            errors.append(f"{context}.check_ids entries must be non-empty strings")
        if len({item for item in normalized_check_ids if item}) != len([item for item in normalized_check_ids if item]):
            errors.append(f"{context}.check_ids entries must be unique")
        if status != "draft" and not [item for item in normalized_check_ids if item]:
            errors.append(f"{context}.check_ids may be empty only when status is draft")

    prior_outcome_refs = packet.get("prior_outcome_refs")
    if not isinstance(prior_outcome_refs, list):
        errors.append(f"{context}.prior_outcome_refs must be an array of strings")
    else:
        normalized_outcome_refs = [_to_text(item).strip() for item in prior_outcome_refs]
        if any(not item for item in normalized_outcome_refs):
            errors.append(f"{context}.prior_outcome_refs entries must be non-empty strings")

    current_pressure = packet.get("current_pressure")
    if not isinstance(current_pressure, dict):
        errors.append(f"{context}.current_pressure must be an object")
    else:
        for field in ("focus_statement", "violation_shape"):
            if not _to_text(current_pressure.get(field)).strip():
                errors.append(f"{context}.current_pressure.{field} must be a non-empty string")

        unresolved_questions = current_pressure.get("unresolved_questions")
        if not isinstance(unresolved_questions, list):
            errors.append(f"{context}.current_pressure.unresolved_questions must be an array of strings")
        elif any(not _to_text(item).strip() for item in unresolved_questions):
            errors.append(f"{context}.current_pressure.unresolved_questions entries must be non-empty strings")

        if "next_check" not in current_pressure:
            errors.append(f"{context}.current_pressure.next_check must be present")
        else:
            next_check = _to_text(current_pressure.get("next_check")).strip()
            if status != "completed" and not next_check:
                errors.append(
                    f"{context}.current_pressure.next_check must be non-empty unless status is completed"
                )

    budget = packet.get("budget")
    if not isinstance(budget, dict):
        errors.append(f"{context}.budget must be an object")

    return errors


def _resolve_artifact_ref_path(ref: str, *, packet_path: Path) -> Path:
    ref_path = _to_text(ref).split("#", 1)[0].strip()
    if not ref_path:
        raise ValueError("artifact ref must include a path")

    raw_path = Path(ref_path)
    if raw_path.is_absolute():
        return raw_path

    packet_relative = (packet_path.parent / raw_path).resolve()
    if packet_relative.exists():
        return packet_relative

    repo_relative = (REPO_ROOT / raw_path).resolve()
    if repo_relative.exists():
        return repo_relative

    return packet_relative


def _parse_coverage_ref(coverage_ref: str) -> tuple[str, tuple[str, str, str]]:
    raw_ref = _to_text(coverage_ref).strip()
    if "#" not in raw_ref:
        raise ValueError("coverage_ref must include '<ledger_path>#<promise_id>|<interaction_family>|<consistency_boundary>'")

    ledger_path_raw, key_raw = raw_ref.split("#", 1)
    key_parts = [part.strip() for part in key_raw.split("|")]
    if len(key_parts) != 3 or any(not part for part in key_parts):
        raise ValueError(
            "coverage_ref must include exactly three key parts: promise_id|interaction_family|consistency_boundary"
        )
    return ledger_path_raw.strip(), (key_parts[0], key_parts[1], key_parts[2])


def _load_coverage_cell_from_ref(coverage_ref: str, *, packet_path: Path) -> dict[str, Any]:
    ledger_ref, target_key = _parse_coverage_ref(coverage_ref)
    ledger_path = _resolve_artifact_ref_path(ledger_ref, packet_path=packet_path)
    ledger = load_promise_coverage_ledger_v1(ledger_path)

    coverage = ledger.get("coverage")
    if not isinstance(coverage, list):
        raise ValueError("coverage ledger is malformed: coverage must be an array")

    for raw_cell in coverage:
        if not isinstance(raw_cell, dict):
            continue
        cell_key = _coverage_key(raw_cell)
        if cell_key == target_key:
            return dict(raw_cell)

    raise ValueError(
        "coverage_ref key not found in ledger: "
        f"{target_key[0]} | {target_key[1]} | {target_key[2]}"
    )


def _find_accepted_slice_candidate(
    touch_map: dict[str, Any], interaction_family: str, consistency_boundary: str
) -> dict[str, Any] | None:
    for raw_slice in touch_map.get("slice_candidates", []):
        if not isinstance(raw_slice, dict):
            continue
        if _to_text(raw_slice.get("status")).strip() != "accepted":
            continue
        if _to_text(raw_slice.get("interaction_family")).strip() != interaction_family:
            continue
        if _to_text(raw_slice.get("consistency_boundary")).strip() != consistency_boundary:
            continue
        return raw_slice
    return None


def _validate_promise_work_packet_linkage(
    packet: dict[str, Any],
    *,
    frame: dict[str, Any],
    task: dict[str, Any],
    touch_map: dict[str, Any],
    coverage_cell: dict[str, Any],
    prior_outcomes: list[dict[str, Any]],
    check_libraries: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    packet_promise_id = _to_text(packet.get("promise_id")).strip()
    packet_incident_id = _to_text(packet.get("incident_id")).strip()

    packet_slice = packet.get("slice")
    packet_slice_family = _to_text(packet_slice.get("interaction_family")).strip() if isinstance(packet_slice, dict) else ""
    packet_slice_boundary = _to_text(packet_slice.get("consistency_boundary")).strip() if isinstance(packet_slice, dict) else ""

    promise_ids = {
        "packet.promise_id": packet_promise_id,
        "frame.promise_id": _to_text(frame.get("promise_id")).strip(),
        "task.promise_id": _to_text(task.get("promise_id")).strip(),
        "touch_map.promise_id": _to_text(touch_map.get("promise_id")).strip(),
        "coverage.promise_id": _to_text(coverage_cell.get("promise_id")).strip(),
    }
    for idx, outcome in enumerate(prior_outcomes, start=1):
        promise_ids[f"prior_outcomes[{idx}].promise_id"] = _to_text(outcome.get("promise_id")).strip()

    unique_promise_ids = {value for value in promise_ids.values() if value}
    if len(unique_promise_ids) != 1:
        errors.append("malformed linkage: promise mismatch across refs")

    if _to_text(frame.get("incident_id")).strip() != packet_incident_id:
        errors.append("malformed linkage: frame.incident_id does not match packet incident_id")

    if _to_text(task.get("assigned_frame_id")).strip() != _to_text(frame.get("frame_id")).strip():
        errors.append("malformed linkage: task.assigned_frame_id does not match frame.frame_id")

    slice_scopes: dict[str, tuple[str, str]] = {
        "frame": (
            _to_text(frame.get("interaction_family")).strip(),
            _to_text(frame.get("consistency_boundary")).strip(),
        ),
        "task": (
            _to_text(task.get("interaction_family")).strip(),
            _to_text(task.get("consistency_boundary")).strip(),
        ),
        "coverage": (
            _to_text(coverage_cell.get("interaction_family")).strip(),
            _to_text(coverage_cell.get("consistency_boundary")).strip(),
        ),
    }
    for idx, outcome in enumerate(prior_outcomes, start=1):
        slice_scopes[f"prior_outcomes[{idx}]"] = (
            _to_text(outcome.get("interaction_family")).strip(),
            _to_text(outcome.get("consistency_boundary")).strip(),
        )

    unique_slice_scopes = {scope for scope in slice_scopes.values() if all(scope)}
    if len(unique_slice_scopes) != 1:
        errors.append("malformed linkage: slice mismatch across refs")

    for idx, outcome in enumerate(prior_outcomes, start=1):
        if _to_text(outcome.get("incident_id")).strip() != packet_incident_id:
            errors.append(
                f"malformed linkage: prior_outcomes[{idx}].incident_id does not match packet incident_id"
            )
        if _to_text(outcome.get("task_id")).strip() != _to_text(task.get("task_id")).strip():
            errors.append(
                f"malformed linkage: prior_outcomes[{idx}].task_id does not match task.task_id"
            )
        if _to_text(outcome.get("frame_id")).strip() != _to_text(frame.get("frame_id")).strip():
            errors.append(
                f"malformed linkage: prior_outcomes[{idx}].frame_id does not match frame.frame_id"
            )

    accepted_slice = _find_accepted_slice_candidate(
        touch_map,
        packet_slice_family,
        packet_slice_boundary,
    )
    if accepted_slice is None:
        errors.append("malformed linkage: packet slice must reference an accepted touch-map slice")
        return errors

    compatible_check_ids: set[str] = set()
    for library in check_libraries:
        for check in suggest_checks_for_accepted_slice_candidate(touch_map, accepted_slice, library):
            check_id = _to_text(check.get("check_id")).strip()
            if check_id:
                compatible_check_ids.add(check_id)

    for check_id in _normalize_string_list(packet.get("check_ids")):
        if check_id not in compatible_check_ids:
            errors.append(f"incompatible check_id for packet slice: {check_id}")

    return errors


def _normalize_promise_work_packet(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)

    for field in PROMISE_WORK_PACKET_REQUIRED_STRING_FIELDS:
        normalized[field] = _to_text(payload.get(field)).strip()
    normalized["status"] = _to_text(payload.get("status")).strip()

    raw_slice = payload.get("slice")
    normalized["slice"] = {
        "interaction_family": _to_text(raw_slice.get("interaction_family")).strip() if isinstance(raw_slice, dict) else "",
        "consistency_boundary": _to_text(raw_slice.get("consistency_boundary")).strip() if isinstance(raw_slice, dict) else "",
    }

    normalized["check_ids"] = sorted(_normalize_string_list(payload.get("check_ids")))
    normalized["prior_outcome_refs"] = sorted(_normalize_string_list(payload.get("prior_outcome_refs")))

    raw_current_pressure = payload.get("current_pressure")
    current_pressure = dict(raw_current_pressure) if isinstance(raw_current_pressure, dict) else {}
    current_pressure["focus_statement"] = _to_text(current_pressure.get("focus_statement")).strip()
    current_pressure["violation_shape"] = _to_text(current_pressure.get("violation_shape")).strip()
    current_pressure["unresolved_questions"] = _normalize_string_list(current_pressure.get("unresolved_questions"))
    current_pressure["next_check"] = _to_text(current_pressure.get("next_check")).strip()
    normalized["current_pressure"] = current_pressure

    raw_budget = payload.get("budget")
    normalized["budget"] = dict(raw_budget) if isinstance(raw_budget, dict) else {}
    return normalized


def load_promise_work_packet_v1(
    path: Path,
    *,
    check_libraries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"promise work packet must be an object: {path}")
    if payload.get("schema_version") != "PromiseWorkPacket.v1":
        raise ValueError(f"{path} schema_version must be PromiseWorkPacket.v1")

    errors = validate_promise_work_packet_v1(payload, context="work_packet")
    if errors:
        raise ValueError(f"{path} invalid promise work packet: {'; '.join(errors)}")

    normalized = _normalize_promise_work_packet(payload)

    frame_path = _resolve_artifact_ref_path(normalized["frame_ref"], packet_path=path)
    task_path = _resolve_artifact_ref_path(normalized["task_ref"], packet_path=path)
    touch_map_path = _resolve_artifact_ref_path(normalized["touch_map_ref"], packet_path=path)

    frame = load_promise_frame_checkpoint_v1(frame_path)
    task = load_promise_traversal_task_v1(task_path)
    touch_map = load_promise_touch_map_v1(touch_map_path)

    coverage_ref_promise_id = _parse_coverage_ref(normalized["coverage_ref"])[1][0]
    if coverage_ref_promise_id != normalized["promise_id"]:
        raise ValueError(f"{path} malformed linkage: coverage_ref promise key does not match promise_id")
    coverage_cell = _load_coverage_cell_from_ref(normalized["coverage_ref"], packet_path=path)

    prior_outcomes: list[dict[str, Any]] = []
    for prior_ref in normalized["prior_outcome_refs"]:
        prior_path = _resolve_artifact_ref_path(prior_ref, packet_path=path)
        prior_outcomes.append(load_promise_scan_outcome_v1(prior_path))

    active_check_libraries = check_libraries
    if active_check_libraries is None:
        active_check_libraries = load_promise_check_libraries_from_dir_v1(
            REPO_ROOT / "diagnostics/memory/promise_check_libraries"
        )

    linkage_errors = _validate_promise_work_packet_linkage(
        normalized,
        frame=frame,
        task=task,
        touch_map=touch_map,
        coverage_cell=coverage_cell,
        prior_outcomes=prior_outcomes,
        check_libraries=active_check_libraries,
    )
    if linkage_errors:
        raise ValueError(f"{path} invalid promise work packet linkage: {'; '.join(linkage_errors)}")

    return normalized


def load_promise_work_packets_for_incident_v1(
    work_packets_root: Path,
    incident_id: str,
    *,
    check_libraries: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    normalized_incident_id = _to_text(incident_id).strip()
    if not normalized_incident_id:
        raise ValueError("incident_id must be non-empty")

    incident_dir = work_packets_root / normalized_incident_id
    if not incident_dir.exists():
        return []
    if not incident_dir.is_dir():
        raise ValueError(f"incident promise work packet path is not a directory: {incident_dir}")

    deduped_by_work_packet_id: dict[str, dict[str, Any]] = {}
    for path in sorted(incident_dir.glob("*.json")):
        packet = load_promise_work_packet_v1(path, check_libraries=check_libraries)
        if _to_text(packet.get("incident_id")).strip() != normalized_incident_id:
            raise ValueError(f"{path} incident_id must match directory incident: {normalized_incident_id}")
        work_packet_id = _to_text(packet.get("work_packet_id")).strip()
        if work_packet_id in deduped_by_work_packet_id:
            raise ValueError(f"duplicate work_packet_id in incident directory: {work_packet_id}")
        deduped_by_work_packet_id[work_packet_id] = packet

    return [deduped_by_work_packet_id[packet_id] for packet_id in sorted(deduped_by_work_packet_id)]


def assemble_promise_work_packet(
    *,
    work_packet_id: str,
    incident_id: str,
    promise: dict[str, Any],
    touch_map: dict[str, Any],
    accepted_slice: dict[str, Any],
    frame: dict[str, Any],
    task: dict[str, Any],
    coverage: dict[str, Any],
    candidate_checks: list[dict[str, Any]],
    prior_outcomes: list[dict[str, Any]],
    frame_ref: str,
    task_ref: str,
    touch_map_ref: str,
    coverage_ref: str,
    prior_outcome_refs: list[str] | None = None,
    objective: str | None = None,
    unresolved_questions: list[str] | None = None,
    next_check: str | None = None,
    budget: dict[str, Any] | None = None,
    status: str = "ready",
    produced_by: str = "manual:promise-work-packet",
    created_at: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(promise, dict):
        raise ValueError("promise must be an object")
    if not isinstance(accepted_slice, dict):
        raise ValueError("accepted_slice must be an object")
    if not isinstance(frame, dict):
        raise ValueError("frame must be an object")
    if not isinstance(task, dict):
        raise ValueError("task must be an object")
    if not isinstance(coverage, dict):
        raise ValueError("coverage must be an object")

    if _to_text(accepted_slice.get("status")).strip() != "accepted":
        raise ValueError("accepted_slice.status must be accepted")

    check_library = {
        "checks": candidate_checks,
    }
    compatible_checks = suggest_checks_for_accepted_slice_candidate(
        touch_map,
        accepted_slice,
        check_library,
    )
    check_ids = sorted(
        {
            _to_text(check.get("check_id")).strip()
            for check in compatible_checks
            if _to_text(check.get("check_id")).strip()
        }
    )

    prior_refs = _normalize_string_list(prior_outcome_refs)
    if not prior_refs:
        prior_refs = sorted(
            {
                _to_text(outcome.get("outcome_id")).strip()
                for outcome in prior_outcomes
                if isinstance(outcome, dict) and _to_text(outcome.get("outcome_id")).strip()
            }
        )

    next_check_prompt = _to_text(next_check).strip()
    if not next_check_prompt:
        frame_next_check = frame.get("next_check")
        if isinstance(frame_next_check, dict):
            next_check_prompt = _to_text(frame_next_check.get("prompt")).strip()

    created_at_value = _to_text(created_at).strip() or utc_now_iso()
    updated_at_value = _to_text(updated_at).strip() or created_at_value
    promise_id = _to_text(promise.get("promise_id")).strip()

    packet: dict[str, Any] = {
        "schema_version": "PromiseWorkPacket.v1",
        "produced_by": _to_text(produced_by).strip() or "manual:promise-work-packet",
        "work_packet_id": _to_text(work_packet_id).strip(),
        "incident_id": _to_text(incident_id).strip(),
        "promise_id": promise_id,
        "slice": {
            "interaction_family": _to_text(accepted_slice.get("interaction_family")).strip(),
            "consistency_boundary": _to_text(accepted_slice.get("consistency_boundary")).strip(),
        },
        "frame_ref": _to_text(frame_ref).strip(),
        "task_ref": _to_text(task_ref).strip(),
        "touch_map_ref": _to_text(touch_map_ref).strip(),
        "coverage_ref": _to_text(coverage_ref).strip(),
        "check_ids": check_ids,
        "prior_outcome_refs": prior_refs,
        "objective": _to_text(objective).strip() or _to_text(task.get("objective")).strip(),
        "current_pressure": {
            "focus_statement": _to_text(frame.get("focus_statement")).strip(),
            "violation_shape": _to_text(frame.get("violation_shape")).strip(),
            "unresolved_questions": _normalize_string_list(unresolved_questions),
            "next_check": next_check_prompt,
        },
        "budget": dict(budget) if isinstance(budget, dict) else dict(task.get("budget", {})),
        "status": _to_text(status).strip() or "ready",
        "created_at": created_at_value,
        "updated_at": updated_at_value,
    }

    packet_errors = validate_promise_work_packet_v1(packet, context="work_packet")
    if packet_errors:
        raise ValueError(f"invalid assembled promise work packet: {'; '.join(packet_errors)}")

    linkage_errors = _validate_promise_work_packet_linkage(
        packet,
        frame=frame,
        task=task,
        touch_map=touch_map,
        coverage_cell=coverage,
        prior_outcomes=prior_outcomes,
        check_libraries=[check_library],
    )
    if linkage_errors:
        raise ValueError(f"invalid assembled promise work packet linkage: {'; '.join(linkage_errors)}")

    return packet


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
