# RepoTrace

**Promise-scoped semantic search for high-value state bugs.**

RepoTrace is a repo-local system for turning vague bug hunting into structured search over **reachable promise violations**.

The core model is simple:

> a bug is a reachable state where an important promise is false

RepoTrace exists to preserve the reasoning state needed to find those bugs:
- what promise is under test
- how that promise decomposes into scanable slices
- what evidence has been gathered
- what has already been ruled out
- what happened when a slice was worked
- what semantic coverage actually exists

This started as a debugging-memory experiment. It is now becoming a **promise-scoped search substrate**.

---

## Why this exists

Most debugging and bug hunting time is not spent on final verification.

It is spent reconstructing enough hidden structure to even begin:
- what the system is trying to keep true
- what state is actually authoritative
- which surfaces can affect that state
- where representations can drift
- which slice is worth scanning next
- which branches have already been killed

LLMs are already strong at shallow local search and pattern matching.

They are much weaker at:
- hidden-spec reconstruction
- selecting the right semantic object
- maintaining focus across stateful logic
- tracking real semantic coverage

RepoTrace is built for that gap.

---

## Core idea

RepoTrace no longer treats the file or function as the deepest search object.

The durable search unit is:

**promise × interaction family × consistency boundary**

Examples of the kinds of things this captures:
- queued entitlement must settle exactly once
- preview state must reflect selected collection
- boundary state must move in lockstep across layout seams
- repricing and settlement must agree across delayed paths

That means the workflow is not:

`repo -> files -> local bug patterns`

It is:

`promise -> touch map -> slice -> probe -> outcome -> coverage`

---

## What RepoTrace is

RepoTrace is:

- a repo-local evidence and witness layer
- a session-lineage layer for active promise-scoped work
- a durable promise memory layer
- a semantic coverage layer
- an evaluation harness for comparing search modes
- a better starting state for Codex or another agent than “go find a bug”

It is **not**:
- a crash reporting platform
- a generic observability suite
- a SaaS backend
- a full autonomous agent runtime
- an invariant prover
- a bug-pattern wrapper around retrieval

---

## Current architecture

RepoTrace is organized into four layers.

### 1. Evidence
Grounded, append-only artifacts.

Examples:
- incidents
- witness sets
- provenance-bearing observations

Witnesses stay **promise-agnostic**.  
They are the grounded layer beneath interpretation.

### 2. Session lineage
Revisable active search state.

Examples:
- promise frame checkpoints
- traversal tasks
- scan outcomes

This is where one active promise slice under test is preserved across work.

### 3. Durable memory
Reusable semantic objects.

Examples:
- promise registry
- promise touch maps
- promise coverage ledgers

This is where the system remembers what matters and how it decomposes.

### 4. Evaluation
Profile-based measurement over fixtures.

Current profiles include:
- `baseline_flat_retrieval`
- `layered_storage_only`
- `layered_plus_witnesses`
- `promise_manual`

This lets RepoTrace compare prettier artifacts against actual process improvements.

---

## Current ontology

### Promise
The primary durable semantic object.

A promise is a system-specific obligation over state and transitions:
what the protocol or application must preserve for some actor, asset, or right.

### Witness
A grounded atomic observation with provenance.

### Anomaly
A witness pattern that puts pressure on a promise.

### Promise frame
A minimal runtime object representing one active promise slice under test.

### Promise touch map
The bridge from “this promise matters” to “these are the exact slices worth scanning.”

### Invariant
A late formalization of a surviving minimized promise violation.

---

## Current search loop

RepoTrace is built around a three-stage loop.

### Stage 1 — Promise derivation
Derive what the system is trying to keep true.

Outputs include:
- actors
- protected state
- interaction families
- consistency boundaries
- settlement horizons
- PromiseCard entries

### Stage 2 — Promise slice scanning
Take one promise, keep it fixed, and decompose it into scanable slices.

Operational unit:
**promise × interaction family × consistency boundary**

Outputs include:
- PromiseTouchMap
- PromiseTraversalTask
- PromiseFrameCheckpoint

### Stage 3 — Violation reduction
Take one suspicious break and try to kill it.

If it survives:
- reduce it to the smallest concrete broken state
- preserve the outcome durably
- only then move toward stronger invariant language

Outputs include:
- PromiseScanOutcome
- updated semantic coverage
- anomaly reduction
- candidate surviving violation

---

## What has already landed

RepoTrace already includes:

- layered artifact architecture:
  - Evidence / Session / Durable Memory / Evaluation
- witness extraction with proposer / critic structure
- profile-driven evaluation harness
- promise registry as the primary durable semantic object
- promise frame checkpoints for active session state
- promise coverage ledgers
- promise traversal tasks
- promise scan outcomes
- promise-manual evaluation
- promise touch maps for durable slice decomposition

This means the repo is already past the “debugging notes + retrieval” phase.

It is now a **promise-scoped semantic search architecture**.

---

## What is novel here

The main bet is that under current LLM-agent equilibrium, the scarce step is not local code reading.

It is:
- reconstructing the right promise
- choosing the right semantic slice
- holding that focus long enough to falsify it

RepoTrace is built around that bottleneck.

Instead of rewarding broad wandering, it tries to preserve:
- semantic focus
- explicit slice decomposition
- loop-closing scan outcomes
- real coverage accounting

That is the real differentiator.

---

## Current frontier

The current frontier is no longer “store more structure.”

It is:

**make promise-slice probing repeatable, discriminating, and measurable without jumping too early to full automation**

That is why the next layer is a reusable check / probe library rather than predictive routing or full orchestration.

---

## Status

RepoTrace is an active systems experiment in turning:

**bug = reachable promise violation**

into a practical search architecture with:
- grounded evidence
- promise memory
- slice decomposition
- semantic coverage
- loop-closing outcomes
- measurable promise-scoped evaluation

If you are browsing this repo quickly, the shortest accurate summary is:

**RepoTrace is a repo-local promise-scoped search system for finding high-value state bugs by preserving the semantic objects that ordinary retrieval-based debugging loses.**
