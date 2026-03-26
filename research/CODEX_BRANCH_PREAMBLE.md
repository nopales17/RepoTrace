# Codex Branch Preamble

At branch start:
1. Read in order:
- `research/ARCHITECTURE_INDEX.md`
- `research/ARCHITECTURE_STATE.md`
- `research/ARCHITECTURE_PROGRAM.md`
- `research/ARCHITECTURE_FRONTIER.md`
- `research/ARCHITECTURE_DECISIONS.md`
- `research/ARCHITECTURE_NOTES.md` (context only)
2. Briefly restate current architecture state, program context, and frontier.
3. Classify changed dimensions (mark changed dimensions only):
- canonical architecture state
- frontier
- notes
- decisions
- program hypothesis / authority / stage map
- no architecture state
Default assumption: `no architecture state` unless justified.
4. State which architecture files (if any) may change.
5. For architecture-affecting branches, run:
   - `python3 scripts/check_architecture_governance.py`
   - `python3 -m unittest tests/test_architecture_governance.py`
   before implementation.
6. If the branch is architecture-affecting, predeclare expected closeout artifact path under `research/architecture_deltas/` or predeclare `no architecture state change`.
