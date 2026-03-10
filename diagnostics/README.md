# Diagnostics

This folder stores persistent debugging state for Codex-assisted development.

## incidents/
Concrete incident reports emitted from the app.

## claims.json
Persistent repo-local debugging memory.

Each claim should be:
- short
- reusable
- attached to files/modules when possible
- marked with status:
  - proposed
  - supported
  - falsified
  - stale

Do not store long prose unless it materially reduces future debugging ambiguity.
