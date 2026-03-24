# Witness Layer Checkpoint — 2026-03-24

## What landed
This branch turns the layered artifact architecture into a grounded evidence-to-witness bridge.

Implemented:
- `WitnessSet.v1` as a real artifact, not just a placeholder schema
- proposer / critic split for witness extraction
- concrete provenance fields on witnesses
- witness-set metrics with explicit semantics
- validator support for witness-layer invariants
- tests for missing provenance, composite witnesses, abstract witnesses, noisy log statements, and metric invariants
- example witness artifacts for:
  - RepoTrace incident fixture
  - Nutriplanner collapse fixture

## Why this matters
This is the first layer that begins to function like reasoning infrastructure rather than storage structure.

Before this branch, evidence and higher-level interpretation were still too close together.
Now there is an explicit intermediate object:
raw evidence -> witnesses -> later motif/frame/control layers

This is the first grounded substrate for:
- motif binding
- contradiction tracking
- discriminating checks
- active frame construction later

## What seems right
- provenance is becoming first-class
- witness extraction is now explicit rather than implicit
- validator/test pressure is starting to constrain artifact drift
- the repo now has a real place where abstraction can be forced to stay anchored

## Known fractures
1. witness quality still depends on heuristic filters and may need domain tuning
2. noisy log streams can still produce high candidate volume before critic pruning
3. branch scope discipline still matters for retrieval/meta-memory boundaries

## Decisions
- witness layer remains strictly below motif/frame logic
- no predictive routing yet
- no graph traversal yet
- no frame runtime yet
- retrieval artifacts should not be rewritten by witness-layer changes
- architecture/meta notes belong in research/checkpoints, not durable debugging memory

## Invariants to preserve
- no witness without provenance
- no composite witness accepted as atomic
- no abstract witness accepted without grounding
- witness metrics must have explicit semantics
- `candidate_count == accepted_count + rejected_count`
- `unsupported_count` is a subset of rejected candidates with supportability failures
- structured evidence remains authoritative
- markdown remains a view

## Gate for the next branch
Do not proceed to the next architecture layer until:
- witness metrics are coherent
- critic behavior is credible on the noisy fixture
- branch scope is clean
- tests and validator pass

## Next intended branch
`feat/eval-harness`

Goal:
compare baseline vs witness-layer behavior on the same fixtures using process metrics such as:
- frontier size after first pass
- unsupported claim count
- contradiction count
- abstention / ambiguous rate
- retrieval drift
- memory artifact growth
