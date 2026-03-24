# Promise Frame Checkpoint (2026-03-24)

## Why frame state is promise-scoped

`diagnostics/memory/promise_registry.json` now carries durable promise definitions, but runtime session lineage still lacked a live object that tracks which promise is actively under test for a concrete incident. `PromiseFrameCheckpoint.v1` fills that gap with a single active frame shape keyed by `promise_id` and `incident_id`, so semantic pressure remains attached to one concrete promise boundary during investigation.

## Why witnesses remain promise-agnostic

Witnesses continue to be stored in `WitnessSet.v1` exactly as concrete observations, missing events, and system/UI facts. The frame references witnesses by ID via support/pressure/contradiction buckets, but does not mutate witness artifacts and does not embed promise-specific witness rewriting. This keeps witness generation reusable across promises and preserves layered compatibility.

## Why this is not yet a full runtime engine

This checkpoint adds only a minimal frame contract and loader/validator support. It does not add multi-frame search, scheduling, orchestration, traversal policy, predictive routing, or automatic promise derivation. `budget` is local frame metadata only (`checks_remaining`) and is not tied to a global coordinator.

## Semantic pressure preserved by this checkpoint

The frame keeps the smallest active state needed to preserve investigative pressure:
- the active promise boundary (`promise_id`, `interaction_family`, `consistency_boundary`)
- the current rupture statement (`focus_statement`, `violation_shape`, `live_anomaly_id`)
- unresolved pressure vectors (`touchpoints_remaining`, `pressure_axes_remaining`)
- concrete evidence posture (`witness_ids.support|pressure|contradiction`)
- deterministic next deterministic move (`next_check`) and local stop budget (`budget`)
- current local outcome (`status`)

## Missing before real promise-scoped search exists

Still missing:
- transition rules for frame lifecycle progression across statuses
- promotion/demotion criteria for support/pressure/contradiction buckets
- linkage from retrieval verdict updates into frame state transitions
- policy for selecting/replacing frames when more than one promise is in play
- deterministic orchestration semantics for budgets across multiple checks/runs
