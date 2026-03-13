# RepoTrace

**Persistent debugging memory for evolving codebases.**

RepoTrace is a repo-local debugging layer for iOS apps and Codex-style workflows.

It captures structured incidents from a running app, stores reusable debugging claims and motif-level priors in the repository, and helps future debugging sessions start from a smaller, more relevant search frontier instead of repeatedly reconstructing repo context from scratch.

## Why this exists

A lot of debugging time is not spent fixing the bug itself.

It is spent reconstructing enough local understanding to even begin:

- what subsystem likely owns the behavior
- what state or contract is actually authoritative
- which branches were already ruled out
- what this repo has broken like before
- what the smallest next discriminating check should be

That reconstruction cost repeats across incidents and across commits.

RepoTrace is an experiment in preserving the **minimum reusable debugging structure** that makes future investigation cheaper.

## Core idea

RepoTrace started as:

**incident → trace → claims → narrower frontier**

It now supports a more explicit control loop:

**incident → retrieval verdict → triage mode → targeted search**

Instead of starting every investigation with a vague prompt like “my app doesn’t work,” the repository accumulates structured debugging state over time:

- incident reports
- reusable claims
- motif-level priors
- falsified branches
- retrieval results
- scoped triage policy

The goal is not to store everything.

The goal is to store the **smallest reusable causal structure** that reduces repeated inference.

## What RepoTrace is

RepoTrace is:

- a repo-local diagnostics layer
- a structured incident capture workflow
- a persistent claim and motif store for debugging
- a retrieval-and-triage layer for narrowing search
- a way to give Codex or another debugging agent a better starting state

## What RepoTrace is not

RepoTrace is not:

- a crash reporting platform
- a full observability suite
- a backend-heavy SaaS
- a generic AI wrapper
- a replacement for deterministic debugging tools

The intended use is:

- collect high-signal incident context
- preserve reusable debugging facts
- classify incidents against known motifs
- narrow the active search frontier
- choose the next debugging action more intelligently
- let Codex or a developer do more targeted work

## How the current architecture works

RepoTrace currently revolves around four persistent artifacts:

### 1. Incidents

Structured bug reports captured from the app, including things like:

- expected vs actual behavior
- breadcrumbs
- metadata
- optional screenshots
- staged notes

An incident is the primary evidence object.

### 2. Claims

Stored in `diagnostics/claims.json`.

These include:

- bug-instance claims
- falsified branches
- motif-level claims
- retrieval-priority hints

Claims are not meant to be a full knowledge base. They are meant to preserve reusable debugging priors that are likely to matter again.

### 3. Retrieval results

Stored under `diagnostics/retrieval_results/`.

A retrieval result is a per-incident classification artifact that captures:

- verdict (`motif_match`, `motif_non_match`, `ambiguous`)
- candidate motif
- supporting evidence
- contradicting evidence
- missing evidence
- next discriminating check

This is the step where RepoTrace moves from “memory” into “control.”

### 4. Triage policy

Stored in `diagnostics/triage_policy.json`.

This is a small machine-readable policy that maps retrieval verdicts to the next debugging mode.

Current modes are:

- `motif_match`
- `motif_non_match`
- `ambiguous`

The point is to prevent broad, expensive wandering before the next action is justified.

## Current workflow

The current minimal RepoTrace workflow is:

1. reproduce a bug in the app
2. capture a structured incident
3. ingest that incident into the repo
4. retrieve the most relevant motif or abstain
5. save a retrieval result
6. apply triage policy
7. take the smallest justified next action

In practice, this means RepoTrace can now support a loop like:

**incident → retrieval result → triage policy → scoped next action**

## Design principle

RepoTrace is built around a simple division of labor:

**semantic proposal → deterministic verification**

LLMs are useful for:

- identifying likely motifs
- proposing hypotheses
- narrowing the frontier
- choosing the next discriminating check

Static tools and instrumentation are useful for:

- confirming or falsifying those hypotheses
- resolving ambiguity cheaply
- grounding debugging in deterministic evidence

RepoTrace exists to preserve the reusable intermediate state between those two steps.

## What has been validated so far

RepoTrace has already been used to validate several important behaviors in the demo environment:

- structured incident capture works
- repo-local claim storage works
- Codex can narrow using incidents plus claims
- motif reuse works across superficially different bug surfaces
- motif retrieval can transfer under refactor/name drift
- retrieval can distinguish:
  - `motif_match`
  - `motif_non_match`
  - `ambiguous`
- ambiguity can be resolved by requesting one targeted discriminating check
- retrieval verdicts can drive a scoped triage mode
- retrieval results can now be saved as repo-local artifacts before broader search

In other words, RepoTrace is no longer just a bug-report archive. It is starting to function as a lightweight **causal retrieval and debugging-control layer**.

## How this fits into the larger architecture

RepoTrace is meant to sit between raw runtime symptoms and deeper code-level debugging.

At a high level, the intended architecture is:

**runtime incident → structured evidence → motif retrieval → triage policy → targeted search**

The idea is not to replace Codex or static tooling. The idea is to make them more efficient by preserving the smallest reusable debugging structure across incidents.

Right now, RepoTrace is still a research prototype, but it already has the core control-plane pieces:

- incident evidence
- reusable motifs
- retrieval verdicts
- uncertainty handling
- policy-driven next actions

That is enough to test whether the architecture has real epistemic value before building heavier automation.

## Current status

Early research prototype.

RepoTrace is currently strong enough to support meaningful usage tests on real debugging problems, especially bugs that involve:

- cross-layer identity drift
- source-of-truth divergence
- stale state between UI and execution
- ambiguous causal boundaries that benefit from one carefully chosen discriminating check

The most important thing that has been demonstrated so far is not just that RepoTrace can help identify bugs, but that it can:

- recognize a known motif
- reject a superficially similar non-match
- abstain when evidence is mixed
- request the smallest missing evidence needed to resolve ambiguity

That is the core behavior the architecture is aiming for.

## Near-term direction

The next likely directions are:

- multi-motif retrieval and ranking
- stronger abstention and uncertainty calibration
- drift-aware motif maintenance across code changes
- stronger integration with real app repositories beyond the demo fixture
- moving from single-motif evaluation toward competing candidate bug classes

The long-term goal is not to store everything.

The long-term goal is to preserve just enough reusable causal structure that future debugging starts from a better prior instead of repeatedly reconstructing the same latent context from scratch.

## Directory Structure 
```text
RepoTrace/
├── AGENTS.md
├── diagnostics/
│   ├── claims.json
│   ├── triage_policy.json
│   ├── README.md
│   ├── incidents/
│   ├── inbox/
│   └── retrieval_results/
├── RepoTrace/
│   └── Diagnostics/
│       ├── BreadcrumbStore.swift
│       ├── DebugReportDraftStore.swift
│       ├── DebugReportEntryPoint.swift
│       ├── DebugReportView.swift
│       ├── DiagnosticModels.swift
│       └── IncidentWriter.swift
├── ios/
│   └── RepoTraceDemo/
│       ├── DemoRootView.swift
│       ├── PlaylistQueueing.swift
│       ├── CheckoutPricing.swift
│       └── RepoTraceDemoApp.swift
├── scripts/
│   ├── new_incident.py
│   ├── pull_simulator_incident.py
│   └── save_retrieval_result.py
├── LICENSE
└── README.md
```
