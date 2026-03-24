# 2026-03-24 Promise Check Library Checkpoint

## Why touch maps were not enough
`PromiseTouchMap.v1` decomposes a promise into slice candidates, but it does not define a reusable probing method for those slices. A touch map can say which `interaction_family x consistency_boundary` pair matters, yet it cannot answer: "what concrete manual check should run, what signals should kill the branch, and what outputs should be captured?" Without that layer, different investigators can choose inconsistent procedures for the same slice and produce non-comparable outcomes.

## Why reusable discriminating checks are the next layer
`CheckCard.v1` adds a durable probe template with explicit objective, required inputs, procedure steps, expected/failure signals, and evidence outputs. `PromiseCheckLibrary.v1` stores these cards in one deterministic artifact so accepted slice candidates can be mapped to known manual checks. This creates repeatable probing behavior for the same slice key across incidents without introducing automation.

## Why this is still manual and not an execution engine
This branch only adds schema, validation/loading, and a compatibility helper that returns ordered suggestions. It does not schedule work, derive tasks autonomously, execute procedures, or route traffic predictively. Human operators still choose whether to run a suggested check, how to gather inputs, and how to interpret evidence.

## How checks differ from promises, witnesses, frames, and outcomes
- Promises define semantic contracts that should hold.
- Touch-map slices define where a promise can be pressure-tested.
- Check cards define how to probe one slice manually and what would discriminate outcomes.
- Witnesses are accepted evidence statements produced by probing.
- Frame checkpoints hold the active investigative state and next manual check prompt.
- Scan outcomes record the result and status transitions after a scan attempt.

## What remains missing before promise-scoped workers can probe consistently
- A policy layer for selecting among multiple compatible checks when several cards match one slice.
- Explicit card lifecycle governance beyond local status fields (review ownership, promotion criteria, retirement process).
- Shared evidence output templates so witness generation is standardized per check type.
- Cross-incident measurement of check yield (false-positive rate, kill rate, operator effort) to tune strength/cost labels.
- Integration rules that bind selected check cards into task/frame updates without introducing autonomous execution.
