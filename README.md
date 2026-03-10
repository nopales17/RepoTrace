# RepoPulse 

Persistent debugging memory for iOS apps: structured incident capture, claim tracking, and Codex-ready search frontier narrowing.

## What this is

RepoPulse is an experiment in making app debugging more stateful.

Instead of repeatedly telling an agent or developer that “the app is broken” and forcing them to reconstruct the repo from scratch, RepoPulse captures a bug incident in a structured way, stores reusable debugging claims over time, and helps narrow the active search frontier for future investigation.

The idea is simple:

- capture high-signal runtime context from the app
- preserve durable debugging facts in the repo
- avoid re-deriving the same structure every time
- give Codex a smaller, more relevant starting point

## Why

A lot of debugging effort is not spent fixing the bug itself. It is spent reconstructing enough local understanding to begin fixing it.

For an evolving app, this reconstruction tax happens over and over:

- what screen owns this behavior?
- what service path does this action use?
- what was already checked before?
- what subsystem is most likely implicated?
- which branches were already falsified?

RepoPulse exists to turn some of that repeated inference into persistent repo-local state.

## Core idea

The workflow is:

1. the app emits a structured incident
2. the repo stores that incident
3. durable claims are tracked over time
4. Codex reads incidents + claims before broad repo exploration
5. the search frontier stays smaller and more relevant

This is not a crash reporter or a full observability platform.

It is a lightweight diagnostics layer aimed at reducing repeated inference in repo-specific debugging workflows.

## Current scope

This repo is intentionally minimal.

Initial goals:

- in-app incident capture for iOS
- screenshot export
- metadata capture
- breadcrumb logging
- repo-local incident files
- persistent `claims.json`
- Codex workflow guidance through `AGENTS.md`

Not in scope right now:

- backend infrastructure
- dashboards
- multi-user collaboration
- autonomous fix generation
- large graph infrastructure
- enterprise observability features

## Repository structure

```text
.
├─ AGENTS.md
├─ diagnostics/
│  ├─ incidents/
│  ├─ claims.json
│  └─ README.md
├─ scripts/
│  └─ new_incident.py
└─ YourApp/
   └─ Diagnostics/
