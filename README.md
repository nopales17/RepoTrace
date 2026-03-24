# RepoTrace

**Promise-scoped semantic search for high-value state bugs.**

RepoTrace is a repo-local system for turning vague bug hunting into structured search over **reachable promise violations**.

The core idea is:

> a bug is a reachable state where an important promise is false

The hard part is usually not local code reading or final exploit execution.  
It is reconstructing the right promise, holding it fixed, and scanning the right semantic slice long enough to falsify it.

RepoTrace is built to preserve that reasoning state.

---

## Why this exists

LLM-based bug hunting is already good at:
- shallow local search
- pattern matching
- bug-dense surface exploration

It is much weaker at:
- hidden-spec reconstruction
- choosing the right semantic object
- maintaining focus across stateful logic
- tracking real semantic coverage

RepoTrace is designed for that gap.

Instead of organizing search around files or functions, it organizes around:

**promise × interaction family × consistency boundary**

---

## What RepoTrace does

RepoTrace provides a layered architecture for promise-scoped search:

### Evidence
Grounded, append-only artifacts.

Examples:
- incidents
- witness sets
- provenance-bearing observations

### Session lineage
Revisable active search state.

Examples:
- promise frame checkpoints
- traversal tasks
- scan outcomes

### Durable memory
Reusable semantic objects.

Examples:
- promise registry
- promise touch maps
- promise coverage ledgers

### Evaluation
Profile-based measurement over fixtures.

Current profiles include:
- `baseline_flat_retrieval`
- `layered_storage_only`
- `layered_plus_witnesses`
- `promise_manual`

---

## Core ontology

### Promise
The primary durable semantic object.  
A protocol- or app-specific obligation over state and transitions.

### Witness
A grounded atomic observation with provenance.

### Promise frame
A minimal runtime object for one active promise slice under test.

### Promise touch map
The bridge from:
“this promise matters”
to
“these are the exact semantic slices worth scanning.”

### Invariant
A late formalization of a surviving minimized promise violation.

---

## Current search loop

RepoTrace is organized around a three-stage loop:

### 1. Promise derivation
Derive what the system is trying to keep true.

### 2. Promise slice scanning
Decompose one promise into scanable slices.

Operational unit:

**promise × interaction family × consistency boundary**

### 3. Violation reduction
Take one suspicious break and try to kill it.  
If it survives, reduce it to the smallest concrete broken state.

---

## What has already landed

RepoTrace already includes:

- layered artifact architecture
- witness extraction with proposer / critic structure
- profile-driven evaluation harness
- promise registry as the primary durable semantic layer
- promise frame checkpoints
- promise coverage ledgers
- promise traversal tasks
- promise scan outcomes
- promise-manual evaluation
- promise touch maps for slice decomposition

This means the project is already past the “debugging notes + retrieval” phase.

It is now a **promise-scoped semantic search architecture**.

---

## Why this is different

The main bet is that under current LLM-agent equilibrium, the scarce step is not local code reading.

It is:
- reconstructing the right promise
- choosing the right semantic slice
- preserving focus long enough to falsify it
- tracking real semantic coverage instead of pretending that local traversal equals understanding

RepoTrace is built around that bottleneck.

---

## Current frontier

The current frontier is:

**make promise-slice probing repeatable, discriminating, and measurable without jumping too early to full automation**

That is why the next layer is a reusable check / probe library rather than predictive routing or full orchestration.

---

## One-line summary

RepoTrace is a repo-local promise-scoped search system for finding high-value state bugs by preserving the semantic objects that ordinary retrieval-based debugging loses.
