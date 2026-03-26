# Codex Branch Closeout

Before commit:
1. Compare landed work against initial branch-impact classification.
2. Set actual changed dimensions:
- canonical architecture state
- frontier
- notes
- decisions
- program hypothesis / authority / stage map
- no architecture state
3. Update only necessary architecture files.
4. If architecture files changed, run:
   - `python3 scripts/check_architecture_governance.py`
   - `python3 -m unittest tests/test_architecture_governance.py`
5. Record pass/fail for both governance commands in closeout.
6. If branch is architecture-affecting, write one closeout artifact under `research/architecture_deltas/` using `research/ARCHITECTURE_DELTA_TEMPLATE.md`.
7. If branch is not architecture-affecting, explicitly state `no architecture state change`.
