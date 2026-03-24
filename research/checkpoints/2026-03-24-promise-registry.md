# Promise Registry Checkpoint — 2026-03-24

## Why promises are now the primary durable object
- Eval harness runs still report empty `promise_id` and `slice_key` across profiles, so layered artifacts have no durable semantic anchor for scoped reuse.
- Witnesses are concrete evidence units, but they do not encode a stable contract boundary by themselves.
- PromiseCards capture the durable semantic contract (what must remain true, who depends on it, and where evidence anchors it), giving retrieval/session layers a stable object to scope against.

## Why witnesses remain promise-agnostic
- Witnesses are lower-layer observations derived from incident evidence and should remain neutral to later interpretation objects.
- Keeping witness extraction promise-agnostic preserves reuse across multiple candidate promises and avoids coupling evidence capture to one hypothesis.
- This keeps the architecture layered: evidence -> witnesses -> promise registry -> later session/frame logic.

## Why invariants are deferred
- Current branch goal is durable semantic scaffolding, not executable invariant runtime.
- Premature invariant syntax would harden uncertain boundaries before session lineage becomes promise-scoped.
- PromiseCards stay soft/derivational so they can absorb new evidence without formal constraint churn.

## Why motifs were not used as the primary schema
- Existing motif artifacts are useful pattern labels, but motif-first storage does not preserve per-case contract ownership as the primary retrieval object.
- Promise-first registry supports future promise-scoped session lineage directly, while motifs can remain deferred (`failure_motif`) as secondary analysis.
- This branch intentionally avoids reviving motif runtime machinery.

## What remains missing before runtime promise frames exist
- Promise-scoped session lineage wiring (`session_id` and retrieval attempt chains keyed by `promise_id`).
- Runtime frame construction/execution over PromiseCards.
- Controlled promotion rules from `hypothesized` to `accepted` to `formalized` with verifier policy.
- Promise-scoped discriminating-check templates and authoring flow.
- Optional deferred layers (`promise_template`, `failure_motif`) and late invariant formalization tools.
