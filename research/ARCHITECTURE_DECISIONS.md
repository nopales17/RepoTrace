# Architecture Decisions

## AD-001
- decision_id: AD-001
- title: Promises are primary durable objects
- status: accepted
- context: Retrieval-centric traces did not preserve stable semantic scope across investigations.
- decision: Use Promise objects as primary durable semantic anchors for scoped search.
- alternatives_considered: motif-first memory, retrieval-chain-first memory.
- consequences: Better scope continuity and replayability; stronger need for promise-derivation discipline.
- reversal_condition: A different durable object repeatedly outperforms promise anchors on closure quality and reuse.

## AD-002
- decision_id: AD-002
- title: Witnesses remain promise-agnostic
- status: accepted
- context: Early promise binding of evidence increased lock-in and reduced reuse.
- decision: Keep witness capture grounded and promise-agnostic; bind scope later via frame/task state.
- alternatives_considered: immediate promise-labeled witness capture.
- consequences: Better evidence reuse across competing promises; requires explicit downstream linkage.
- reversal_condition: Early binding consistently yields better reliability without harmful lock-in.

## AD-003
- decision_id: AD-003
- title: Work packets are bundle/view artifacts
- status: accepted
- context: Execution handoff needed compact context without creating competing truth sources.
- decision: Treat work packets as execution bundles/views over canonical and session artifacts.
- alternatives_considered: authoritative packet-centric truth model.
- consequences: Lower truth-fragmentation risk; integrity checks across references remain necessary.
- reversal_condition: View-only packets cannot support reliable execution without becoming canonical.

## AD-004
- decision_id: AD-004
- title: Invariants are late formalizations
- status: accepted
- context: Early invariant formalization hardens unstable boundaries too soon.
- decision: Formalize invariants after repeated evidence and stable decomposition.
- alternatives_considered: invariant-first architecture.
- consequences: Slower formalization, lower premature lock-in risk.
- reversal_condition: Early invariants repeatedly improve correctness and speed without lock-in cost.

## AD-005
- decision_id: AD-005
- title: Touch maps define decomposition, not execution
- status: accepted
- context: Scope decomposition and run policy are separate concerns.
- decision: Keep touch maps for slice decomposition only; execution policy lives in frame/task/check layers.
- alternatives_considered: encode execution sequencing directly in touch maps.
- consequences: Clearer boundaries; additional control artifacts required for run management.
- reversal_condition: Separation repeatedly causes unavoidable coordination failures.

## AD-006
- decision_id: AD-006
- title: Human-authorized thesis and ontology boundary
- status: accepted
- context: Fresh Codex conversations need a stable authority split to avoid silent thesis/ontology drift.
- decision: High-level thesis, ontology, and program-model changes require explicit architectural review; Codex may implement and reconcile within that boundary but may not silently redefine it. Architecture docs are the shared control plane between human architect and Codex implementer.
- alternatives_considered: fully autonomous thesis updates; implementation-only docs without explicit authority boundary.
- consequences: Lower drift risk with explicit review gate; requires maintaining architecture docs as active control-plane artifacts.
- reversal_condition: Autonomous thesis/ontology edits consistently improve outcomes without increasing drift or governance failures.
