# Eval Harness Checkpoint — 2026-03-24

## What This Harness Measures
- Cross-profile behavior on the same fixture incidents using normalized retrieval-attempt objects.
- Frontier pressure after first pass (`frontier_size_after_first_pass`).
- Speed-of-guidance proxy (`time_to_first_discriminating_check` as attempt index, not wall-clock).
- Unsupported statements exposed after profile processing (`unsupported_claim_count`).
- Contradictory evidence volume surfaced per considered attempts (`contradiction_count`).
- Abstention/ambiguity rate over considered attempts (`abstention_or_ambiguous_rate`).
- Verdict drift across attempt lineage (`retrieval_drift_between_attempts`).
- Structural storage growth proxy (`memory_artifact_growth`).

## What This Harness Does Not Measure
- True semantic correctness of retrieval conclusions.
- End-user bug-fix quality or app runtime quality.
- Promise-aware search effectiveness (reserved only, not activated here).
- Learned ranking quality, graph traversal quality, or frame/procedure runtime behavior.

## Why Normalized Attempts Were Required
- Legacy and current retrieval artifacts expose different field shapes.
- Direct metric computation against raw field names would overfit to artifact quirks and break under shape drift.
- `normalize_retrieval_attempt` enforces a stable minimal contract (`attempt_id`, `verdict`, `candidate_count`, `has_discriminating_check`, `contradiction_items`, `source_shape`) so all metrics run on one canonical view.

## Why Promise Hooks Were Reserved But Not Activated
- This branch needs future-proofing for scoped evaluation without introducing promise-runtime behavior.
- Optional fields were added (`scoping_mode`, `promise_id`, `slice_key`) in profiles and run outputs.
- Default behavior is strict no-op (`scoping_mode=none`, nullable IDs/keys) unless a fixture explicitly opts in.

## Known Metric Crudeness
- `memory_artifact_growth` is a proxy structural metric (artifact-unit count), not an intrinsic quality metric.
- `time_to_first_discriminating_check` is intentionally deterministic attempt-index time, not wall-clock latency.
- `unsupported_claim_count` depends on witness-pruning semantics and should be read as exposure after profile processing, not absolute truth.
- This harness is intended for repeatable architecture comparisons, not final model-quality benchmarking.
