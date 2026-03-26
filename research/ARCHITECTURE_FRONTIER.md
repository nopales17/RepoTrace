# Architecture Frontier

## Current Frontier
Upstream Stage 1 support: improve promise derivation aid so candidate promises are generated, compared, and stabilized before entering the manual promise-scoped loop.

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
Advance the frontier only if new work improves one of the following:
- candidate-promise quality and comparability,
- sustained promise focus during execution,
- slice-level falsifiability/closure signal,
- measurable semantic-loop coherence.

Defer work that mainly increases artifact surface area without a clear delta on those criteria.
