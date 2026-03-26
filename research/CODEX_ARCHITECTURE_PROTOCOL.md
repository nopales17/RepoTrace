# Codex Architecture Protocol

## Phase 1: Start-of-Branch Handshake
Before implementation, read in order:
0. `research/ARCHITECTURE_INDEX.md`
1. `research/ARCHITECTURE_STATE.md`
2. `research/ARCHITECTURE_PROGRAM.md`
3. `research/ARCHITECTURE_FRONTIER.md`
4. `research/ARCHITECTURE_DECISIONS.md`
5. `research/ARCHITECTURE_NOTES.md` (context only)

Then classify branch impact dimensions (mark changed dimensions only):
- canonical architecture state
- frontier
- notes
- decisions
- program hypothesis / authority / stage map
- no architecture state

Default assumption: `no architecture state` unless justified.
Update only the minimum files required by the selected changed dimensions.

For architecture-affecting branches, run:
- `python3 scripts/check_architecture_governance.py`
- `python3 -m unittest tests/test_architecture_governance.py`

Decision-log posture is required:
- relies on existing decision(s), or
- challenges existing decision(s), or
- introduces a new decision, or
- no decision change.

## Phase 2: End-of-Branch Reconciliation
Before commit:
1. Compare landed work against initial branch-impact classification.
2. Reclassify actual changed dimensions using the same categories.
3. Update only minimal required architecture files.
4. Re-run:
   - `python3 scripts/check_architecture_governance.py`
   - `python3 -m unittest tests/test_architecture_governance.py`
   when architecture files changed.
5. Record whether each governance command passed or failed in closeout.
6. For architecture-affecting branches, produce one durable closeout artifact in `research/architecture_deltas/` using `research/ARCHITECTURE_DELTA_TEMPLATE.md`.
7. Non-architecture branches may skip closeout artifacts but must explicitly state `no architecture state change`.

Fresh conversations may inspect recent files under `research/architecture_deltas/` for short branch-level architecture memory.

## Architecture File Update Rules
- `ARCHITECTURE_STATE.md`:
  Update only for durable merged changes or explicit accepted decisions that alter thesis, ontology, invariants, merged core, or source-of-truth boundaries.
- `ARCHITECTURE_FRONTIER.md`:
  Update only when leverage point, risk posture, falsifiers, or decision boundary changes.
- `ARCHITECTURE_NOTES.md`:
  Update only for meaningful pressure/tension/disconfirmation changes.
- `ARCHITECTURE_DECISIONS.md`:
  Update only when a durable architectural choice is accepted, superseded, reversed, or clarified.
- `ARCHITECTURE_PROGRAM.md`:
  Update only when program hypothesis, strategic context, authority model, stage map, success/kill criteria, or provisional/expansion boundaries change.

## Drift Guards
- Do not promote branch-local implementation detail into canonical architecture state.
- Do not update architecture docs just because a branch existed.
- Do not silently change thesis/ontology/invariants without merged durable artifacts or decision-log support.
- Do not treat generated eval outputs as canonical truth.
- Do not treat bundle/view artifacts as canonical truth.

## Maintenance Rules
- Frontier maintenance:
  Promote items to `ARCHITECTURE_STATE.md` or `ARCHITECTURE_DECISIONS.md` only when durable and accepted; prune/replace items that stop producing leverage; archive stale branch queue entries in branch deltas rather than accumulating dead backlog.
- Notes maintenance:
  Keep only live pressure/tension/disconfirmation signals; move resolved or obsolete pressure to branch deltas and remove from active notes.
- Implementation state maintenance:
  `research/IMPLEMENTATION_STATE.yaml` is implementation/migration tracking only and must never carry canonical thesis, ontology, frontier, notes, or decision authority.
