# Architecture Hypotheses

## A. Purpose
This file is the soft idea-intake layer for important architecture/program ideas that are still abstract, messy, and convergent.

It uses two speeds:
- Sparks: cheap capture for important but not-yet-actionable ideas.
- Hypotheses: richer cards only when mechanism and proving path are bounded.

Hard-role files remain authoritative:
- `ARCHITECTURE_STATE.md`
- `ARCHITECTURE_FRONTIER.md`
- `ARCHITECTURE_PROGRAM.md`
- `ARCHITECTURE_DECISIONS.md`

## B. Promotion Rules
- Capture threshold options:
  - no capture
  - spark
  - hypothesis
  - direct promotion (exceptional)
- Default bias: no capture or spark, not full hypothesis, not direct promotion.
- Full hypothesis threshold requires:
  - bounded mechanism
  - success signal
  - falsifier
  - real next proving move
- Spark threshold requires only:
  - idea
  - why it matters
  - possible surfaces
  - next question

Promotion routing after sufficient pressure:
- `PROGRAM`: deeper wager, authority model, stage map, success/kill criteria.
- `FRONTIER`: current operational bet with concrete success signal and falsifier.
- `DECISIONS`: durable side chosen.
- `STATE`: no longer a live bet.
- `NOTES`: pressure/tension/disconfirmation only.

Full hypothesis card format:
- hypothesis_id
- claim
- why_it_matters
- mechanism
- success_signal
- falsifier
- influence_surfaces
- next_proving_move
- possible_promotion_surfaces
- current_maturity

Allowed hypothesis `current_maturity` values:
- seed
- shaped
- active
- promoted
- rejected

## C. Active Hypotheses
Keep active full hypotheses very small.

### HYP-001
- hypothesis_id: HYP-001
- claim: Promise selection and sustained semantic focus are the durable moat; shallow local search improvements are secondary.
- why_it_matters: This determines long-horizon architecture investment.
- mechanism: Hidden-spec reconstruction and focus retention dominate closure quality under objective ambiguity.
- success_signal: Promise-derivation improvements outperform local-search-only improvements on matched incidents.
- falsifier: Local-search improvements consistently dominate closure gains across incident families.
- influence_surfaces: search, program, evaluation
- next_proving_move: compare matched incident outcomes under stronger promise-selection flow versus local-search-only optimization.
- possible_promotion_surfaces: PROGRAM, FRONTIER
- current_maturity: active

### HYP-002
- hypothesis_id: HYP-002
- claim: Cross-promise failures may dominate later high-value incidents and require explicit cross-promise reasoning.
- why_it_matters: Single-promise loops may plateau on system-level failures.
- mechanism: Coupled boundary interactions create failures no isolated promise slice explains.
- success_signal: Cross-promise probes improve closure quality where single-promise scans stall.
- falsifier: Single-promise decomposition consistently closes high-value incidents without cross-promise extensions.
- influence_surfaces: search, program
- next_proving_move: add targeted cross-promise probes on incidents that end with unresolved coupling ambiguity.
- possible_promotion_surfaces: FRONTIER, PROGRAM
- current_maturity: active

### HYP-003
- hypothesis_id: HYP-003
- claim: Operator burden and bypass rate may become the decisive falsifier of the current control-plane shape.
- why_it_matters: If operators bypass the flow, architecture value does not transfer operationally.
- mechanism: Artifact overhead can outgrow decision-quality gains.
- success_signal: Reduced overhead with stable-or-better closure quality and lower bypass.
- falsifier: Operators sustain the current flow with acceptable burden and superior outcomes.
- influence_surfaces: governance, operator, search
- next_proving_move: track bypass frequency and closure quality before/after targeted burden reductions.
- possible_promotion_surfaces: FRONTIER, NOTES, DECISIONS
- current_maturity: active

## D. Sparks / Early Ideas
Sparks are intentionally lightweight and can be more numerous than active full hypotheses.

Spark format:
- spark_id
- idea
- why_it_matters
- possible_surfaces
- next_question
- current_maturity

Allowed spark `current_maturity` values:
- seed
- shaped
- dropped

### SPK-001
- spark_id: SPK-001
- idea: Current metrics may still be too retrieval-shaped and underweight semantic-loop quality.
- why_it_matters: Misaligned metrics can steer architecture toward convenient but low-transfer wins.
- possible_surfaces: evaluation, governance, search
- next_question: Which minimal semantic-loop metrics would most likely change method ranking on existing fixtures?
- current_maturity: shaped

### SPK-002
- spark_id: SPK-002
- idea: Work packets may need to become thinner and more compiled from canonical/session artifacts.
- why_it_matters: Heavy packet ceremony can increase operator burden and duplicate state.
- possible_surfaces: governance, operator, search
- next_question: What is the smallest thin-packet variant that preserves handoff quality?
- current_maturity: shaped

### SPK-003
- spark_id: SPK-003
- idea: Touch maps may need to become more derived and sparse rather than broad upfront decompositions.
- why_it_matters: Over-broad maps can dilute falsifiability pressure.
- possible_surfaces: search, evaluation
- next_question: Which evidence-derived sparsification rule should be tested first?
- current_maturity: shaped

### SPK-004
- spark_id: SPK-004
- idea: The architecture control plane may itself be a productizable operating layer.
- why_it_matters: This may open a parallel value path beyond internal debugging productivity.
- possible_surfaces: product, governance, program, operator
- next_question: What constrained pilot would best test transferability without forcing product commitments?
- current_maturity: seed

### SPK-005
- spark_id: SPK-005
- idea: Internal debugging/incident analysis may be the strongest early wedge for proving control-plane value.
- why_it_matters: Early wedge choice determines evidence quality and adoption speed.
- possible_surfaces: product, operator, governance
- next_question: Which internal incident-loop scorecard is sufficient to validate wedge strength?
- current_maturity: shaped

## E. Parked / Lower-Priority Hypotheses
No parked full hypotheses currently. Move entries here only when they remain full hypotheses but are deprioritized.

## F. Rejected / Falsified
Rejected/falsified entries are durable short records and should not be deleted.

No rejected entries yet.

## G. Update Rule
Update this file when important ideas are captured, matured, promoted, rejected, or dropped.

Do not let this file become a backlog or a second `NOTES` file.
