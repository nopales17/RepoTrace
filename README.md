# RepoTrace

**Persistent debugging memory for evolving codebases.**

RepoTrace is a repo-local debugging layer for iOS apps and Codex-style workflows.

It captures structured incidents from a running app, stores reusable debugging claims and motif-level priors in the repository, and helps future debugging sessions start from a smaller, more relevant search frontier instead of repeatedly reconstructing repo context from scratch.

## Why

A lot of debugging time is not spent fixing the bug itself.

It is spent reconstructing enough local understanding to begin:

- what subsystem likely owns the behavior
- what state or contract is actually authoritative
- which branches were already ruled out
- what this repo has broken like before
- what the smallest next discriminating check should be

RepoTrace is an experiment in preserving the **minimum reusable debugging structure** that makes future investigation cheaper.

## Core loop

RepoTrace started as:

**incident → trace → claims → narrower frontier**

It now supports a more explicit loop:

**incident → retrieval verdict → triage mode → targeted search**

## What RepoTrace stores

RepoTrace currently persists four main artifacts:

- **incidents** — structured bug reports captured from the app
- **claims** — reusable debugging facts and motif-level priors
- **retrieval results** — per-incident classification outputs
- **triage policy** — a small control layer mapping retrieval verdicts to the next debugging action

## What it does

RepoTrace helps a debugging agent or developer:

- capture high-signal incident context
- retrieve likely recurring bug motifs
- distinguish match / non-match / ambiguous cases
- request the smallest missing evidence when needed
- avoid broad repo wandering too early

## What it is not

RepoTrace is not:

- a crash reporting platform
- a full observability suite
- a backend-heavy SaaS
- a generic AI wrapper
- a replacement for deterministic debugging tools

## Repository layout

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
## Current status

Early research prototype.

So far, RepoTrace has been used to validate:

- structured incident capture
- repo-local claim storage
- motif transfer across different bug surfaces
- motif retrieval under refactor/name drift
- retrieval verdicts of:
  - `motif_match`
  - `motif_non_match`
  - `ambiguous`
- ambiguity resolution through one targeted discriminating check
- triage-policy-driven next actions

In other words, RepoTrace is no longer just a bug-report archive. It is starting to function as a lightweight **causal retrieval and debugging-control layer**.
