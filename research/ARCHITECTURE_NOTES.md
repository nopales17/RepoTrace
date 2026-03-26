# Architecture Notes

## Empirical Evidence Behind the Thesis
- Local agents can already find real bugs on large codebases when promise scope is explicit.
- The hardest failures are upstream of test execution: choosing and holding the right promise.
- Under-specified objectives repeatedly pull search into local attractors (nearest logs, nearby edits, easy checks).
- High-value stateful bugs persist when the right promise is never selected or held fixed long enough.

## Research / Conceptual Inspirations
- Process-level architecture over finished-choice formalism.
- Working memory as stable global semantic content over noisy local dynamics.
- Predictive-processing style routing/gating with explicit residual handling.
- Replay/consolidation as the path from episodes to reusable structure.
- Typed memory plus control as a better model than flat context accumulation.

## Architectural Tensions
- Promise specificity vs flexibility:
  Too broad loses falsifiability; too narrow misses system interactions.
- Slice depth vs cross-slice coupling:
  Deep local pressure can miss cross-promise boundary effects.
- Artifact rigor vs operator burden:
  Structure increases replayability but can slow exploratory throughput.
- Metrics discipline vs convenience:
  Retrieval-friendly proxies are easier than semantic-loop quality measures.

## Lessons From Recent Branches
- Typed artifacts improved loop legibility and replayability when they preserved explicit linkage across promise, slice, check, and outcome.
- Manual promise-scoped search became operational before autonomous control; this sequence reduced ambiguity and kept evaluation grounded.
- Layering worked when witness capture remained promise-agnostic and promise scope entered explicitly at frame/task layers.
- The largest remaining leverage moved upstream to promise derivation, not deeper downstream instrumentation.

## Signs The Framing May Be Wrong
- Promise selection remains unstable even with derivation support.
- Cross-promise failures dominate observed incidents but slice-local methods fail to expose them.
- Added artifacts increase process load without improving falsification speed or closure quality.
- Evaluation gains come mainly from retrieval-style metrics while semantic-loop coherence stagnates.
- Operators routinely bypass promise-scoped flow to get better results.
