# 2026-03-24 Promise Touch Map Checkpoint

## Why PromiseRegistry was not enough
PromiseRegistry establishes durable promise identity and high-level semantics, but it does not provide a stable decomposition artifact that tells a scanner exactly which mutable surfaces and consistency boundaries should be inspected together. In practice, registry entries are too coarse for deterministic slice-level scan planning because they do not encode reusable family/boundary IDs or explicit candidate slice units.

## Why touch maps are the bridge from promise to scanable slice
PromiseTouchMap.v1 introduces the missing bridge layer between "promise exists" and "worker scans a slice" by explicitly modeling:
- mutable surfaces that can perturb protected state,
- interaction families that group transitions over those surfaces,
- consistency boundaries that define which representations must settle together,
- slice candidates that bind one family to one boundary with rationale and status.

This creates a durable, reviewable decomposition artifact without introducing runtime automation.

## Why decomposition is promise x interaction_family x consistency_boundary
The decomposition unit is `promise x interaction_family x consistency_boundary` because:
- Promise selects the protected semantic contract.
- Interaction family selects the transition context where that contract is exercised.
- Consistency boundary selects the concrete representation pair that must agree within a settlement horizon.

A slice candidate is therefore a bounded testable cell for scan planning and coverage accounting.

## Why this is still manual and not automatic promise derivation
This branch adds a schema, loader/validator, and a helper that converts `accepted` slice candidates into manual task stubs. It does not infer new promises, predict routes, or schedule workers. The touch map remains authored and curated by humans, preserving deterministic control over scope and frontier size.

## What is still missing before large-scale promise-scoped search exists
- Cross-incident touch-map authoring workflow and governance (promotion/review/retirement).
- Coverage loop integration that tracks slice status transitions from proposed -> accepted -> exhausted at scale.
- Execution orchestration (scheduler/multi-worker coordination) tied to explicit policy.
- Retrieval-layer prioritization heuristics that consume touch-map structure without becoming predictive routing.
- Procedure/check libraries and reusable verifier packs for each interaction family/boundary class.
