# Promise Work Packet (v1)

## Why existing promise artifacts were too scattered for consistent worker operation
`PromiseRegistry.v1`, `PromiseTouchMap.v1`, `PromiseFrameCheckpoint.v1`, `PromiseTraversalTask.v1`, `PromiseCoverageLedger.v1`, `PromiseScanOutcome.v1`, and `PromiseCheckLibrary.v1` each preserve one part of the manual investigation loop, but a worker run still had to reconstruct context from multiple files and implicit joins. In practice, this allowed drift between selected slice intent, active frame pressure, assigned task objective, allowed checks, and prior outcomes. The result was inconsistent packet handoff and repeated linkage mistakes (wrong promise scope, wrong slice scope, or stale check selection).

## Why PromiseWorkPacket.v1 is a bundle/view, not a canonical semantic object
`PromiseWorkPacket.v1` does not replace durable semantics already anchored in registry, touch map, frame, task, outcome, and coverage artifacts. It is a session-level bundle that references those objects and captures one coherent work unit for execution-time handoff. The canonical sources remain unchanged; the packet is a portable view over already-existing state.

## Semantic pressure preserved by the packet
The packet preserves the minimum pressure required to execute one promise-scoped run coherently:
- promise identity (`promise_id`, `incident_id`)
- selected slice identity (`slice.interaction_family`, `slice.consistency_boundary` from accepted touch-map slice)
- concrete linkage refs (`frame_ref`, `task_ref`, `touch_map_ref`, `coverage_ref`, `prior_outcome_refs`)
- discriminating checks (`check_ids`) constrained to the selected slice
- active pressure (`focus_statement`, `violation_shape`, `unresolved_questions`, `next_check`)
- bounded effort and lifecycle (`budget`, `status`, timestamps)

## Why this is still not an autonomous worker runtime
This change adds no scheduler, no orchestration loop, no predictive routing, no automatic check execution, and no autonomous task generation. Packet assembly is explicit/manual and uses already-selected artifacts. Loading validates linkage and compatibility, but does not dispatch or run checks.

## What remains missing before integration and merge
- explicit UI/CLI workflow for packet creation/update in normal incident handling
- packet lifecycle transitions tied to existing frame/task/outcome updates
- explicit merge policy for multiple packets in the same incident/promise scope
- end-to-end integration in eval harness/reporting flows
- operational guidance for packet staleness handling across long-running sessions
