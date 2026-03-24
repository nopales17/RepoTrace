# Promise coverage ledger checkpoint (2026-03-24)

## Gap audit: frame state vs. real search control

PromiseFrameCheckpoint captures one active investigative slice (`promise_id`, `interaction_family`, `consistency_boundary`) and local session state (`next_check`, `budget`, witness buckets, status). It does not persist semantic coverage across slices, does not account for what parts of a promise surface were never scanned, and does not provide an explicit assignment artifact for manual work partitioning.

That means the system can carry local frame progress, but it cannot yet prove global promise coverage. Work can drift (re-checking already scanned cells) or appear covered without an explicit durable coverage cell update.

## Why coverage is keyed by promise x interaction_family x consistency_boundary

Promise-level correctness commitments are too large to validate in one pass. Coverage must be tracked at the smallest reusable semantic unit that still maps to user-visible correctness:

- `promise_id`: which contract is under investigation.
- `interaction_family`: which class of user/system interaction is being exercised.
- `consistency_boundary`: which boundary agreement (UI/runtime/rule/layout, etc.) is being challenged.

This key prevents false coverage claims because progress is attributed only to a concrete contract slice, not to the promise in aggregate.

## Why this is needed before traversal policy

Before any traversal policy can decide what to scan next, the system needs durable accounting of what has already been mapped/scanned and where anomalies were found, killed, or survived. Without this ledger, traversal decisions have no reliable substrate and become session-local guesses.

The manual task object adds the minimum assignment skeleton (`task_id`, frame binding, objective, budget, status) so slices can be explicitly tracked without introducing scheduling or autonomous routing.

## Why this is not a full orchestrator

This layer intentionally stops at artifact definitions plus validation/load/update helpers. It does not include:

- scheduling
- graph traversal or path planning
- automatic promise derivation
- multi-frame search control loops
- automatic worker dispatch

## What is still missing before multi-worker promise-scoped search

- traversal policy that selects next cells from ledger state under budget constraints
- conflict-safe concurrent updates (merge/reconcile rules) for coverage/task artifacts
- worker lease/ownership protocol for tasks
- completion criteria for promise-wide semantic closure
- orchestration loop wiring to execute and persist outcomes automatically
