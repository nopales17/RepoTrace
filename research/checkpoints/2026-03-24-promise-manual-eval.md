# Promise Manual Eval Checkpoint — 2026-03-24

## Why this is the first measurable promise-scoped search version
- The eval harness now includes a dedicated `promise_manual` profile that reads manual promise artifacts directly: registry, frame checkpoint, traversal task, scan outcome, and coverage ledger.
- This is the first run mode where scope, slice, and closure can be measured from explicit promise-scoped objects instead of only retrieval lineage snapshots.
- `semantic_loop_closed` now verifies whether frame/task/outcome/coverage are linked consistently for the same promise slice.

## Why this is still manual and not autonomous
- Task assignment, frame creation, and outcome authoring are still manually authored artifacts.
- No autonomous traversal policy, worker scheduler, predictive routing, or automatic promise derivation was added.
- The harness evaluates the state represented by artifacts; it does not generate or execute search behavior.

## Metrics that are genuinely informative now
- `promise_scope_present`: confirms the run used a concrete promise card and promise id.
- `promise_slice_defined`: confirms the run has explicit slice scope.
- `coverage_status_after_scan`: reports the ledger state for the scoped slice after manual scan recording.
- `task_completion_status`: reports the resulting manual task status.
- `scan_outcome`: reports manual scan outcome class.
- `anomaly_count`: reports anomaly identifiers emitted by the scan outcome.
- `semantic_loop_closed`: checks linkage integrity across frame/task/outcome/coverage.

## Metrics that remain retrieval-shaped proxies
- `frontier_size_after_first_pass`: proxy from remaining touchpoints/pressure axes, not search-space optimality.
- `time_to_first_discriminating_check`: deterministic index proxy (presence of first explicit check), not wall-clock runtime.
- `unsupported_claim_count`: fixed proxy (`0`) because unsupported-claim accounting is not authored in promise artifacts.
- `abstention_or_ambiguous_rate`: mapped from blocked/exhausted outcome classes, not probabilistic confidence.
- `retrieval_drift_between_attempts`: fixed proxy (`0.0`) in this single-pass manual path.
- `memory_artifact_growth`: structural artifact count, not semantic quality.

## What must exist before comparing promise-scoped workers at scale
- Worker-produced promise tasks and outcomes with stable IDs and deterministic replay hooks.
- A scheduler/orchestrator contract for concurrent slice assignment and completion semantics.
- Consistent promise-level closure criteria across all slices in a promise surface.
- Cross-worker drift and conflict metrics grounded in produced events rather than manual snapshots.
- Batch fixture coverage where each fixture has complete promise artifacts and comparable closure states.
