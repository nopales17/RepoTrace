# 2026-03-24 Promise Derivation Aid Checkpoint

## Why the existing core loop was not enough
The current manual promise-scoped search loop begins effectively only after a PromiseCard already exists. That left an upstream gap: teams still needed an ad-hoc way to turn protocol/system understanding into stable, reviewable candidate promises. Without an explicit Stage 1 artifact, promise selection was inconsistent across operators and hard to audit.

## Why Stage 1 needed an explicit worksheet
`PromiseDerivationWorksheet.v1` adds a minimal manual worksheet layer that captures:
- system purpose and actors,
- assets/rights and consistency boundaries worth protecting,
- transition families where those boundaries can break,
- candidate promise statements with scoped references and confidence/status.

This makes derivation decisions explicit and reviewable before touch-map decomposition or scan execution begins.

## Why this is manual support, not autonomous extraction
This branch does not add automatic promise extraction, predictive routing, scheduler/orchestrator behavior, motif systems, or invariant formalization. The worksheet is manually authored and manually curated. Loader/validator support only enforces structural correctness and reference integrity.

## How this feeds PromiseRegistry
Accepted worksheet candidates can now be converted into PromiseCard-shaped stubs through a deterministic helper. Those stubs are suggestions only (`status=hypothesized`) and can be reviewed/refined before promotion into `PromiseRegistry.v1`. This keeps the registry durable while making upstream derivation reproducible.

## What is still missing before large-scale promise discovery
- Cross-incident governance for worksheet lifecycle (review, supersede, retire).
- Promotion workflow from worksheet stubs to finalized PromiseRegistry entries.
- Tooling to compare derivation quality and drift across teams/incidents.
- Integration between worksheet outcomes and touch-map/check-library authoring guidance at scale.
- Evidence quality gates for when a candidate can move from `accepted` in worksheet to durable registry acceptance.
