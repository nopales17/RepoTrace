# ADR 0001: Separate Evidence, Session Lineage, and Durable Memory

## Status
Accepted (scaffold v1)

## Date
2026-03-24

## Context
RepoTrace currently stores incidents, retrieval outputs, and claims in legacy locations that are useful but not strongly separated by mutability semantics. A concrete external case in Nutriplanner (`incident-20260313-235921`, branch `repotrace-eval`) showed stable incident evidence while retrieval interpretation changed between commits `85486cd` and `f3a3a59`.

That case demonstrates a non-negotiable architecture constraint:

- incident evidence can remain valid while investigation interpretation evolves
- investigation/session state therefore requires lineage and versioning
- durable claims/motifs/procedures must not be conflated with per-incident verdict files

## Decision
RepoTrace adopts a three-layer control-plane split:

1. Immutable Evidence Layer
- Authoritative evidence artifact: `Incident.v1`
- Witness-level structure: `WitnessSet.v1`
- Storage boundary: `diagnostics/evidence/incidents/*.json`
- Markdown incident files are derived views, not authoritative state

2. Revisable Investigation Lineage Layer
- Versioned attempts: `RetrievalAttempt.v1`
- Session lineage/materialized latest view: `InvestigationSession.v1`
- Storage boundary:
  - `diagnostics/session/retrieval_attempts/<incident_id>/<run_id>.json`
  - `diagnostics/session/latest/<incident_id>.json`

3. Durable Memory Layer
- Compatibility reader over legacy `diagnostics/claims.json`
- New boundary for durable memory artifacts: `diagnostics/memory/claims.json`
- Durable claims require concrete provenance fields and remain distinct from per-incident retrieval attempts

## Mutability Rules
Immutable:
- `Incident.v1` evidence payloads are append-only once written
- Witness material referenced by evidence is immutable

Mutable and Versioned:
- Retrieval and investigation/session state are revised via new run artifacts, never by overwriting lineage history
- `latest` files are materialized views/pointers over versioned runs

Durable but Revisable:
- Claims/motifs/procedures are persistent memory artifacts with provenance and can evolve independently of any single incident session

## Minimum Viable Architecture in This PR
- Add schemas for evidence/session/memory separation
- Operationalize only: `Incident.v1`, `WitnessSet.v1`, `RetrievalAttempt.v1`, `InvestigationSession.v1`, `Feedback.v1`, `ExperimentProfile.v1`, `ResearchState.v1`
- Add compatibility adapters for legacy incident markdown, raw incident JSON, legacy retrieval artifacts, and legacy claims
- Add forward-only validator for new v1 artifacts, fixtures, and research state
- Keep existing behavior intact for legacy workflows while writing new authoritative/session artifacts

## Consequences
Positive:
- Prevents conflation of evidence and interpretation
- Supports retrieval lineage across commits and runs
- Introduces explicit control boundaries and provenance requirements

Deferred by design:
- predictive routing
- frame engine runtime
- graph database adoption
- learned weighting
- broad refactors
- app bug solving
