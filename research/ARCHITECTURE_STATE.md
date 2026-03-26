# Architecture State

## Why This System Exists
Shallow local bug search is increasingly commoditized across LLM agents. The scarce step is hidden-spec reconstruction: selecting the right behavioral promise and keeping semantic focus on it long enough to falsify or retain it. Repo size is usually not the limiting factor; objective ambiguity and semantic state-space are.

RepoTrace exists to preserve coherent promise pressure through an investigation so search does not collapse into local attractors. The deeper program wager and authority boundaries live in `research/ARCHITECTURE_PROGRAM.md`.

## Canonical Thesis
- Bug = reachable promise violation.
- Primary bottleneck = promise selection plus sustained semantic focus.
- Stable decomposition unit = `promise x interaction family x consistency boundary`.
- Search quality improves when this decomposition is explicit and carried through a full evidence-to-outcome loop.

## Core Ontology
- Promise: scoped behavioral contract candidate whose violation would matter.
- Witness: provenance-grounded evidence atom.
- Anomaly: concrete rupture instance relative to a promise.
- Invariant: durable rule distilled from repeated surviving checks.
- Frame: active state for one promise-scoped slice under pressure.
- Touch map: decomposition of a promise into scanable slice surfaces.
- Check: repeatable probing procedure for one slice.
- Work packet: execution bundle binding scope, checks, and prior state for one run.

## Architectural Invariants
- Promise scope is explicit before deep search.
- Witnesses remain grounded and provenance-preserving.
- Active search state is typed and slice-scoped, not free-form context.
- Coverage/progress is artifact-backed, not implicit operator memory.
- Outcomes close loops by linking promise, slice, check, and result.
- Evaluation prioritizes semantic-loop coherence, not only retrieval convenience proxies.

## Anti-Goals
- Generic retrieval-first debugging without explicit promise scope.
- Fully autonomous orchestration at the current maturity stage.
- Flat untyped context accumulation as the primary state mechanism.
- Declaring semantic closure from code locality alone.

## Merged Core
Mainline architecture includes a manual promise-scoped search core with typed layers for:
- evidence/witness grounding,
- durable promise memory,
- slice-scoped frame/task control,
- touch-map decomposition and coverage tracking,
- repeatable check definitions,
- explicit scan outcomes and execution handoff,
- promise-loop integrity evaluation.

## Source-of-Truth Boundaries
- Canonical durable memory:
  Promise registry, accepted touch maps/check libraries, and accepted architecture decisions define long-lived architectural semantics.
- Session lineage:
  Frame checkpoints, traversal tasks, scan outcomes, and coverage transitions define incident-local execution truth.
- Bundle/view artifacts:
  Work packets and similar execution bundles are convenience views over canonical/session artifacts and are not canonical truth.
- Derived evaluation artifacts:
  Eval runs/metrics are derived signals for comparison and governance, not direct architecture truth.
- Evidence/witness grounding artifacts:
  Evidence and witness artifacts are canonical for observed facts/provenance, while remaining promise-agnostic.

## Known Boundary Conditions
- Strongest fit:
  Promise-first is strongest when a failure can be scoped to a falsifiable behavioral contract and decomposed into stable interaction/boundary slices.
- Weaker fit:
  Promise-first weakens when objective uncertainty stays high and candidate promises cannot stabilize before probing.
- Extension triggers:
  Cross-promise/system-level, long-horizon temporal, or policy/compliance failure modes may require extensions beyond single-promise framing.

## Update Rule
Treat this file as the canonical seed for architecture resets and future planning. Update only when durable state changes (why, thesis, ontology, invariants, anti-goals, merged core, source-of-truth boundaries, or boundary conditions), not for routine branch churn or short-lived tactics. Use `research/ARCHITECTURE_PROGRAM.md` for program-level hypothesis and authority changes.
