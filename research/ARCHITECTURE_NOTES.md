# Architecture Notes

## Supports Current Architecture
- Local agents can already find real bugs on large codebases when promise scope is explicit.
- The hardest failures are upstream of test execution: choosing and holding the right promise.
- Under-specified objectives repeatedly pull search into local attractors (nearest logs, nearby edits, easy checks).
- Process-level control with typed memory and replay/consolidation improves repeatability over flat context accumulation.

## Active Tensions
- Promise specificity vs flexibility:
  Too broad loses falsifiability; too narrow misses system interactions.
- Slice depth vs cross-slice coupling:
  Deep local pressure can miss cross-promise boundary effects.
- Artifact rigor vs operator burden:
  Structure improves replayability but can slow exploratory throughput.
- Metrics discipline vs convenience:
  Retrieval-friendly proxies are easier than semantic-loop quality measures.

## Disconfirmation Signals
- Promise selection remains unstable even with derivation support.
- Cross-promise failures dominate observed incidents but slice-local methods fail to expose them.
- Added artifacts increase process load without improving falsification speed or closure quality.
- Evaluation gains come mainly from retrieval-style metrics while semantic-loop coherence stagnates.
- Operators routinely bypass promise-scoped flow to get better results.

## Notes Maintenance Rules
- Keep:
  Only active pressure, tensions, and disconfirmation signals that still influence current architecture choices.
- Remove:
  Delete notes that are resolved, duplicated elsewhere, or no longer decision-relevant.
- Archive:
  When a note is retired, mention its resolution briefly in the branch delta artifact rather than accumulating historical narrative here.
