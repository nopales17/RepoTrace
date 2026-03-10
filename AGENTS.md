# Project guidance for Codex

You are working on an iOS app.

Primary debugging workflow:
1. Read `diagnostics/incidents/` for the current incident.
2. Read `diagnostics/claims.json` before broad repo exploration.
3. Distinguish clearly between:
   - observations
   - claims / hypotheses
   - checks run
   - falsified branches
4. Prefer narrowing the search frontier over broad speculative reading.
5. Reuse existing claims if they remain relevant.
6. When a claim is disproven, mark it as falsified instead of repeating it.
7. When a new durable repo-specific debugging fact is discovered, update `diagnostics/claims.json`.

Output style:
- Be explicit about top candidate subsystems.
- Name the smallest next deterministic check.
- Keep the active frontier small.

When fixing a bug:
- First identify likely files and checks.
- Then implement the smallest fix.
- Then explain which claim was confirmed or falsified.
