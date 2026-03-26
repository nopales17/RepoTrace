# Architecture Frontier

## Current Frontier
Within the broader program hypothesis in `research/ARCHITECTURE_PROGRAM.md`, the current leverage point is upstream Stage 1 support: improve promise derivation aid so candidate promises are generated, compared, and stabilized before entering the manual promise-scoped loop.

## Current Bet
A lightweight promise-derivation layer will reduce objective drift and improve falsification efficiency without requiring autonomous orchestration.

## Success Signal
- More investigations start with one stable, falsifiable promise boundary.
- Fewer runs are terminated due to promise drift mid-loop.
- Time/check budget to first closure decision decreases.
- Semantic-loop coherence improves without large artifact overhead growth.

## Failure Signal / Falsifiers
- Candidate promises remain unstable despite derivation aid.
- Ad hoc retrieval-first workflows outperform promise-scoped flow.
- Derivation artifacts increase overhead without improving closure quality.
- Dominant high-value failures are cross-promise and under-explained by current decomposition.

## Main Risks / Open Questions
- Promise-first framing can become vague without stronger derivation discipline.
- Cross-promise/system-level failures may be under-modeled by narrow slice focus.
- Artifact growth can outpace actual search-quality gains.
- Promise derivation can become a new ambiguity sink.
- Retrieval-shaped metrics can still dominate evaluation unless explicitly constrained.

## Deferred Non-Goals
- Autonomous promise discovery/execution loops.
- Global scheduler/orchestrator design for multi-worker operation.
- Full invariant runtime formalization.
- End-to-end optimization against generic retrieval leaderboard metrics.

## Branch Queue
1. `chore/promise-derivation-aid`
2. `chore/promise-derivation-eval`
3. `chore/cross-promise-risk-scan`
4. `chore/promise-closure-criteria`
5. `chore/worker-assist-loop`

## Current Decision Boundary
Advance this frontier only if changes improve at least one of:
- candidate-promise quality/comparability,
- sustained promise focus during execution,
- slice-level falsifiability/closure signal,
- semantic-loop coherence.

Defer work that mainly increases artifact surface area without measurable governance/search delta.

## Frontier Maintenance Rules
- Promote:
  Move a frontier topic into `ARCHITECTURE_STATE.md` and/or `ARCHITECTURE_DECISIONS.md` only after repeated evidence and accepted durable decisions.
- Prune:
  Remove branch-queue items that remain stale across multiple cycles or fail to produce measurable leverage.
- Archive:
  Capture retired/superseded frontier items in branch delta artifacts under `research/architecture_deltas/` instead of keeping dead items in active queue.
