# Promise scan outcome checkpoint (2026-03-24)

## Why coverage and task objects were not enough

`PromiseCoverageLedger.v1` can say a promise slice is `mapped`, `scanned`, or terminal (`anomaly_found` / `killed` / `survives`), and `PromiseTraversalTask.v1` can assign manual work with budget and status. But neither object records what happened during a concrete worked scan attempt.

That gap leaves two ambiguities:
- task status can move (`active` -> `blocked`/`done`) without a durable explanation of the observed result.
- coverage status can change without an explicit artifact linking the change to one worked frame/task slice and a next manual move.

## Why `PromiseScanOutcome.v1` is the minimal loop-closing object

`PromiseScanOutcome.v1` adds only one completion/partial-result artifact with linkage keys:
- `task_id`, `frame_id`, `incident_id`, `promise_id`, `interaction_family`, `consistency_boundary`

And only one outcome payload surface:
- what happened (`outcome`, `summary`, `witness_ids_added`, `anomaly_ids`, `killed_reason`)
- what should happen next (`next_action`)
- the resulting status write targets (`resulting_coverage_status`, `resulting_task_status`)

This is the smallest durable object that explains a worked slice and allows deterministic status updates for exactly one coverage cell and one task.

## Why this is still not a scheduler

This addition does not introduce:
- predictive routing
- graph traversal
- automatic promise derivation
- worker pools or orchestration loops
- automatic task creation/assignment

The helper only applies statuses to already-selected artifacts and rejects linkage mismatches.

## What becomes possible now

- A task/frame slice can be closed with an explicit, reviewable outcome artifact.
- Coverage and task transitions can be justified by one durable lineage object instead of inferred side effects.
- Session outcomes can be loaded per incident from `diagnostics/session/promise_outcomes/<incident>/` with deterministic ordering and strict validation.

## What is still missing before promise-manual evaluation exists

- Manual-evaluation run contract that requires outcome emission per worked slice.
- Policy for when to open follow-up tasks from `next_action` (still manual today).
- Roll-up criteria for promise-level closure across all coverage cells.
- Conflict/merge rules for concurrent edits to coverage/task/outcome artifacts.
