import tempfile
import textwrap
import unittest
from pathlib import Path

from scripts.check_architecture_governance import (
    ARCH_FILES,
    check_architecture_index,
    check_classification_surfaces,
    check_closeout_artifact,
    check_closeout_requirements,
    check_decisions,
    check_hypotheses_structure,
    check_preamble_read_order,
    check_protocol,
    check_required_files,
    check_required_sections,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def _write_valid_tree(root: Path) -> None:
    _write(
        root / ARCH_FILES["index"],
        """
        # Architecture Index
        - research/CODEX_ARCHITECTURE_PROTOCOL.md
        - research/ARCHITECTURE_STATE.md
        - research/ARCHITECTURE_PROGRAM.md
        - research/ARCHITECTURE_DECISIONS.md
        - research/ARCHITECTURE_FRONTIER.md
        - research/ARCHITECTURE_HYPOTHESES.md
        - research/ARCHITECTURE_NOTES.md
        - research/IMPLEMENTATION_STATE.yaml
        - research/architecture_deltas/
        """,
    )
    _write(
        root / ARCH_FILES["state"],
        """
        # Architecture State
        ## Why This System Exists
        ## Canonical Thesis
        ## Core Ontology
        ## Architectural Invariants
        ## Anti-Goals
        ## Merged Core
        ## Source-of-Truth Boundaries
        ## Known Boundary Conditions
        ## Update Rule
        """,
    )
    _write(
        root / ARCH_FILES["program"],
        """
        # Architecture Program
        ## A. Program Hypothesis
        ## B. Strategic Context
        ## C. Authority Model
        ## D. Lifecycle / Stage Map
        ## E. Success Conditions
        ## F. Kill Criteria / Strong Falsifiers
        ## G. Provisional Mechanisms
        ## H. Later-Stage Expansion Ladder
        ## I. Update Rule
        """,
    )
    _write(
        root / ARCH_FILES["frontier"],
        """
        # Architecture Frontier
        ## Current Frontier
        ## Current Bet
        ## Success Signal
        ## Failure Signal / Falsifiers
        ## Branch Queue
        ## Current Decision Boundary
        """,
    )
    _write(
        root / ARCH_FILES["hypotheses"],
        """
        # Architecture Hypotheses
        ## A. Purpose
        ## B. Promotion Rules
        ## C. Active Hypotheses
        - hypothesis_id: HYP-001
        - claim: x
        - why_it_matters: x
        - mechanism: x
        - success_signal: x
        - falsifier: x
        - influence_surfaces: search
        - next_proving_move: x
        - possible_promotion_surfaces: FRONTIER
        - current_maturity: active
        - seed
        - shaped
        - promoted
        - rejected
        ## D. Sparks / Early Ideas
        - spark_id: SPK-001
        - idea: x
        - possible_surfaces: search
        ## E. Parked / Lower-Priority Hypotheses
        ## F. Rejected / Falsified
        ## G. Update Rule
        """,
    )
    _write(
        root / ARCH_FILES["notes"],
        """
        # Architecture Notes
        ## Supports Current Architecture
        ## Active Tensions
        ## Disconfirmation Signals
        """,
    )
    _write(
        root / ARCH_FILES["decisions"],
        """
        # Architecture Decisions
        ## AD-001
        - decision_id: AD-001
        - title: x
        - status: accepted
        - context: x
        - decision: x
        - alternatives_considered: x
        - consequences: x
        - reversal_condition: x
        """,
    )
    _write(
        root / ARCH_FILES["protocol"],
        """
        # Codex Architecture Protocol
        ## Phase 1: Start-of-Branch Handshake
        Read in order:
        - research/ARCHITECTURE_INDEX.md
        - research/ARCHITECTURE_STATE.md
        - research/ARCHITECTURE_PROGRAM.md
        - research/ARCHITECTURE_FRONTIER.md
        - research/ARCHITECTURE_DECISIONS.md
        - research/ARCHITECTURE_HYPOTHESES.md
        - research/ARCHITECTURE_NOTES.md

        Classify changed dimensions:
        - canonical architecture state
        - frontier
        - notes
        - decisions
        - program hypothesis / authority / stage map
        - no architecture state

        Default assumption: no architecture state.
        Run: python3 scripts/check_architecture_governance.py
        Run: python3 -m unittest tests/test_architecture_governance.py
        Use: research/architecture_deltas/
        soft convergence layer
        no capture
        spark
        hypothesis
        direct promotion
        high-level architectural dialogue
        matured, stayed unchanged, promoted, or rejected

        ## Phase 2: End-of-Branch Reconciliation
        """,
    )
    _write(
        root / ARCH_FILES["preamble"],
        """
        # Codex Branch Preamble
        Read in order:
        - research/ARCHITECTURE_INDEX.md
        - research/ARCHITECTURE_STATE.md
        - research/ARCHITECTURE_PROGRAM.md
        - research/ARCHITECTURE_FRONTIER.md
        - research/ARCHITECTURE_DECISIONS.md
        - research/ARCHITECTURE_HYPOTHESES.md
        - research/ARCHITECTURE_NOTES.md
        - canonical architecture state
        - frontier
        - notes
        - decisions
        - program hypothesis / authority / stage map
        - no architecture state
        - python3 scripts/check_architecture_governance.py
        - python3 -m unittest tests/test_architecture_governance.py
        - pass/fail
        """,
    )
    _write(
        root / ARCH_FILES["closeout"],
        """
        # Codex Branch Closeout
        - canonical architecture state
        - frontier
        - notes
        - decisions
        - program hypothesis / authority / stage map
        - no architecture state
        - python3 scripts/check_architecture_governance.py
        - python3 -m unittest tests/test_architecture_governance.py
        - pass/fail
        - research/architecture_deltas/
        - matured, stayed unchanged, promoted, or rejected
        """,
    )
    _write(
        root / ARCH_FILES["delta"],
        """
        # Architecture Delta
        - canonical architecture state
        - frontier
        - notes
        - decisions
        - program hypothesis / authority / stage map
        - no architecture state
        """,
    )


class ArchitectureGovernanceTests(unittest.TestCase):
    def test_required_file_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_tree(root)
            (root / ARCH_FILES["program"]).unlink()
            errors = check_required_files(root)
            self.assertTrue(any("ARCHITECTURE_PROGRAM.md" in e for e in errors))

    def test_required_section_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_tree(root)
            _write(
                root / ARCH_FILES["program"],
                """
                # Architecture Program
                ## A. Program Hypothesis
                ## B. Strategic Context
                """,
            )
            errors = check_required_sections(root)
            self.assertTrue(any("Lifecycle / Stage Map" in e for e in errors))

    def test_protocol_classification_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_tree(root)
            _write(
                root / ARCH_FILES["protocol"],
                """
                # Codex Architecture Protocol
                ## Phase 1: Start-of-Branch Handshake
                - canonical architecture state
                - frontier
                - notes
                - decisions
                - no architecture state
                """,
            )
            errors = check_classification_surfaces(root)
            self.assertTrue(any("protocol missing classification" in e for e in errors))

    def test_protocol_read_order_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_tree(root)
            _write(
                root / ARCH_FILES["protocol"],
                """
                # Codex Architecture Protocol
                ## Phase 1: Start-of-Branch Handshake
                - research/ARCHITECTURE_INDEX.md
                - research/ARCHITECTURE_STATE.md
                - research/ARCHITECTURE_FRONTIER.md
                - research/ARCHITECTURE_PROGRAM.md
                - research/ARCHITECTURE_DECISIONS.md
                - research/ARCHITECTURE_HYPOTHESES.md
                - research/ARCHITECTURE_NOTES.md
                - canonical architecture state
                - frontier
                - notes
                - decisions
                - program hypothesis / authority / stage map
                - no architecture state
                default assumption: no architecture state
                python3 scripts/check_architecture_governance.py
                research/architecture_deltas/
                soft convergence layer
                high-level architectural dialogue
                matured, stayed unchanged, promoted, or rejected
                ## Phase 2: End-of-Branch Reconciliation
                """,
            )
            errors = check_protocol(root)
            self.assertTrue(any("protocol read-order entry" in e for e in errors))

    def test_preamble_read_order_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_tree(root)
            _write(
                root / ARCH_FILES["preamble"],
                """
                # Codex Branch Preamble
                - research/ARCHITECTURE_INDEX.md
                - research/ARCHITECTURE_STATE.md
                - research/ARCHITECTURE_FRONTIER.md
                - research/ARCHITECTURE_PROGRAM.md
                - research/ARCHITECTURE_DECISIONS.md
                - research/ARCHITECTURE_HYPOTHESES.md
                - research/ARCHITECTURE_NOTES.md
                - canonical architecture state
                - frontier
                - notes
                - decisions
                - program hypothesis / authority / stage map
                - no architecture state
                """,
            )
            errors = check_preamble_read_order(root)
            self.assertTrue(any("preamble read-order entry" in e for e in errors))

    def test_closeout_classification_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_tree(root)
            _write(
                root / ARCH_FILES["closeout"],
                """
                # Codex Branch Closeout
                - canonical architecture state
                - frontier
                - notes
                - decisions
                - no architecture state
                """,
            )
            errors = check_classification_surfaces(root)
            self.assertTrue(any("closeout missing classification" in e for e in errors))

    def test_closeout_governance_command_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_tree(root)
            _write(
                root / ARCH_FILES["closeout"],
                """
                # Codex Branch Closeout
                - canonical architecture state
                - frontier
                - notes
                - decisions
                - program hypothesis / authority / stage map
                - no architecture state
                - python3 scripts/check_architecture_governance.py
                - research/architecture_deltas/
                - matured, stayed unchanged, promoted, or rejected
                """,
            )
            errors = check_closeout_requirements(root)
            self.assertTrue(any("unittest command" in e for e in errors))

    def test_hypotheses_section_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_tree(root)
            _write(
                root / ARCH_FILES["hypotheses"],
                """
                # Architecture Hypotheses
                ## A. Purpose
                ## B. Promotion Rules
                """,
            )
            errors = check_required_sections(root)
            self.assertTrue(any("Active Hypotheses" in e for e in errors))

    def test_hypotheses_card_field_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_tree(root)
            _write(
                root / ARCH_FILES["hypotheses"],
                """
                # Architecture Hypotheses
                ## A. Purpose
                ## B. Promotion Rules
                ## C. Active Hypotheses
                - hypothesis_id: HYP-001
                ## D. Sparks / Early Ideas
                ## E. Parked / Lower-Priority Hypotheses
                ## F. Rejected / Falsified
                ## G. Update Rule
                """,
            )
            errors = check_hypotheses_structure(root)
            self.assertTrue(any("missing card field" in e for e in errors))

    def test_architecture_index_reference_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_tree(root)
            _write(
                root / ARCH_FILES["index"],
                """
                # Architecture Index
                - research/CODEX_ARCHITECTURE_PROTOCOL.md
                - research/ARCHITECTURE_STATE.md
                """,
            )
            errors = check_architecture_index(root)
            self.assertTrue(any("missing reference" in e for e in errors))

    def test_closeout_artifact_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_tree(root)
            artifact = root / "research/architecture_deltas/example.md"
            _write(
                artifact,
                """
                # Architecture Delta
                - branch: x
                - initial changed dimensions: x
                """,
            )
            errors = check_closeout_artifact(root, Path("research/architecture_deltas/example.md"))
            self.assertTrue(any("missing field" in e for e in errors))

    def test_decision_entry_field_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid_tree(root)
            _write(
                root / ARCH_FILES["decisions"],
                """
                # Architecture Decisions
                ## AD-001
                - decision_id: AD-001
                - title: x
                - status: accepted
                """,
            )
            errors = check_decisions(root)
            self.assertTrue(any("missing field" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
