# RepoTrace

**Persistent debugging traces for evolving codebases.**

RepoTrace is a repo-local debugging memory system for iOS apps and Codex-style development workflows.

It captures structured bug incidents from a running app, stores reusable debugging claims directly in the repository, and helps future debugging sessions start from a smaller, more relevant search frontier instead of reconstructing the same repo context from scratch.

## Why this exists

A lot of debugging time is not spent fixing the bug itself.

It is spent reconstructing enough local understanding to begin fixing it:

- what subsystem likely owns this behavior
- what path this action takes through the app
- what was already checked before
- which branches were already ruled out
- what stable assumptions this repo depends on

That reconstruction cost repeats across incidents and across commits.

RepoTrace is an experiment in preserving the smallest reusable debugging structure that survives long enough to matter.

## Core idea

RepoTrace turns debugging into a persistent loop:

**incident → trace → claims → narrower frontier**

With retrieval triage enabled, the loop is now:

**incident → retrieval verdict → triage mode → targeted search**

Instead of starting every investigation with a vague prompt like “my app doesn’t work,” the repo accumulates structured state over time:

- incident reports
- reusable claims
- falsified branches
- subsystem hints
- commit-aware debugging memory

The goal is not to store everything.

The goal is to store the **minimum reusable structure** that reduces repeated inference.

## What RepoTrace is

RepoTrace is:

- a repo-local diagnostics layer
- a structured incident capture workflow
- a persistent claim store for debugging
- a way to give Codex a better starting state

## What RepoTrace is not

RepoTrace is not:

- a crash reporting platform
- a full observability system
- a backend-heavy SaaS
- a generic AI wrapper
- a replacement for deterministic tooling

The intended use is:

- collect high-signal incident context
- preserve reusable debugging facts
- narrow the active search frontier
- let Codex or a developer do more targeted work

## Repository layout

```text
RepoTrace/
├─ AGENTS.md
├─ diagnostics/
│  ├─ claims.json
│  ├─ triage_policy.json
│  └─ incidents/
├─ scripts/
├─ examples/
└─ ios/
   └─ RepoTraceDemo/
```

## Current progress (March 10, 2026)

- Implemented the in-app diagnostics primitives used by RepoTrace (`BreadcrumbStore`, debug report drafting, incident writer, and debug report UI entry point).
- The repository now supports a full local loop from repro breadcrumbs to structured incident artifacts under `diagnostics/`.
- Added scripts for incident workflow support, including creating and pulling simulator incidents.
- `RepoTraceDemo` is a fixture app used to exercise and validate the debugging workflow, not the core product itself.
- Added a minimal machine-readable triage policy at `diagnostics/triage_policy.json` so retrieval verdicts (`motif_match`, `motif_non_match`, `ambiguous`) map to scoped next actions.
