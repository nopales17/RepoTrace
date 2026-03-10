# Diagnostics

This folder stores persistent debugging state for RepoTrace.

## incidents/
Structured incident reports exported from the app and converted into repo-local artifacts.

## claims.json
A small persistent store of reusable debugging claims.

Claims should be:
- short
- reusable
- attached to files or subsystems when possible
- clearly marked as one of:
  - proposed
  - supported
  - falsified
  - stale

Do not store long summaries unless they reduce future debugging ambiguity.
Prefer compact structural facts over narrative prose.
