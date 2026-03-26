#!/usr/bin/env python3
"""Lightweight fitness checks for architecture-governance docs."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

ARCH_FILES = {
    "index": Path("research/ARCHITECTURE_INDEX.md"),
    "state": Path("research/ARCHITECTURE_STATE.md"),
    "program": Path("research/ARCHITECTURE_PROGRAM.md"),
    "frontier": Path("research/ARCHITECTURE_FRONTIER.md"),
    "notes": Path("research/ARCHITECTURE_NOTES.md"),
    "decisions": Path("research/ARCHITECTURE_DECISIONS.md"),
    "protocol": Path("research/CODEX_ARCHITECTURE_PROTOCOL.md"),
    "preamble": Path("research/CODEX_BRANCH_PREAMBLE.md"),
    "closeout": Path("research/CODEX_BRANCH_CLOSEOUT.md"),
    "delta": Path("research/ARCHITECTURE_DELTA_TEMPLATE.md"),
}

REQUIRED_SECTIONS = {
    "state": [
        "Why This System Exists",
        "Canonical Thesis",
        "Core Ontology",
        "Architectural Invariants",
        "Anti-Goals",
        "Merged Core",
        "Source-of-Truth Boundaries",
        "Known Boundary Conditions",
        "Update Rule",
    ],
    "program": [
        "Program Hypothesis",
        "Strategic Context",
        "Authority Model",
        "Lifecycle / Stage Map",
        "Success Conditions",
        "Kill Criteria / Strong Falsifiers",
        "Provisional Mechanisms",
        "Later-Stage Expansion Ladder",
        "Update Rule",
    ],
    "frontier": [
        "Current Frontier",
        "Current Bet",
        "Success Signal",
        "Failure Signal / Falsifiers",
        "Branch Queue",
        "Current Decision Boundary",
    ],
    "notes": [
        "Supports Current Architecture",
        "Active Tensions",
        "Disconfirmation Signals",
    ],
}

REQUIRED_CLASSIFICATIONS = [
    "canonical architecture state",
    "frontier",
    "notes",
    "decisions",
    "program hypothesis / authority / stage map",
    "no architecture state",
]

REQUIRED_READ_ORDER = [
    "research/architecture_index.md",
    "research/architecture_state.md",
    "research/architecture_program.md",
    "research/architecture_frontier.md",
    "research/architecture_decisions.md",
    "research/architecture_notes.md",
]

CLASSIFICATION_FILES = {
    "protocol": ARCH_FILES["protocol"],
    "preamble": ARCH_FILES["preamble"],
    "closeout": ARCH_FILES["closeout"],
    "delta": ARCH_FILES["delta"],
}

DECISION_FIELDS = [
    "decision_id",
    "title",
    "status",
    "context",
    "decision",
    "alternatives_considered",
    "consequences",
    "reversal_condition",
]

HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", re.MULTILINE)

INDEX_REQUIRED_REFERENCES = [
    "research/codex_architecture_protocol.md",
    "research/architecture_state.md",
    "research/architecture_program.md",
    "research/architecture_decisions.md",
    "research/architecture_frontier.md",
    "research/architecture_notes.md",
    "research/implementation_state.yaml",
    "research/architecture_deltas/",
]

DELTA_REQUIRED_FIELDS = [
    "- branch:",
    "- initial changed dimensions:",
    "- actual changed dimensions:",
    "- architecture files updated:",
    "- reason for each update:",
    "- no-state-change declaration",
    "- any new decision entry required:",
    "- any frontier shift detected:",
    "- governance check status",
    "- governance test status",
]


def _norm(value: str) -> str:
    lowered = value.strip().lower().replace("`", "")
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_headings(markdown: str) -> set[str]:
    return {_norm(match.group(1)) for match in HEADING_RE.finditer(markdown)}


def _heading_present(headings: set[str], expected_heading: str) -> bool:
    target = _norm(expected_heading)
    return any(target in heading for heading in headings)


def check_required_files(root: Path) -> list[str]:
    errors: list[str] = []
    for key, rel in ARCH_FILES.items():
        if not (root / rel).is_file():
            errors.append(f"missing required file [{key}]: {rel}")
    return errors


def check_required_sections(root: Path) -> list[str]:
    errors: list[str] = []
    for key, section_names in REQUIRED_SECTIONS.items():
        file_path = root / ARCH_FILES[key]
        if not file_path.is_file():
            continue
        headings = _extract_headings(_read(file_path))
        for section_name in section_names:
            if not _heading_present(headings, section_name):
                errors.append(f"missing required section in {ARCH_FILES[key]}: {section_name}")
    return errors


def _ensure_ordered(text: str, fragments: Iterable[str], label: str) -> list[str]:
    cursor = -1
    errors: list[str] = []
    for fragment in fragments:
        next_pos = text.find(fragment, cursor + 1)
        if next_pos == -1:
            errors.append(f"missing {label}: {fragment}")
            continue
        if next_pos < cursor:
            errors.append(f"out-of-order {label}: {fragment}")
        cursor = max(cursor, next_pos)
    return errors


def check_protocol(root: Path) -> list[str]:
    path = root / ARCH_FILES["protocol"]
    if not path.is_file():
        return []
    text = _norm(_read(path))

    errors: list[str] = []
    errors.extend(_ensure_ordered(text, REQUIRED_READ_ORDER, "protocol read-order entry"))

    if "start-of-branch handshake" not in text:
        errors.append("protocol missing start-of-branch handshake requirement")
    if "end-of-branch reconciliation" not in text:
        errors.append("protocol missing end-of-branch reconciliation requirement")
    if "default assumption" not in text or "no architecture state" not in text:
        errors.append("protocol missing default no-architecture-state assumption")
    if "python3 scripts/check_architecture_governance.py" not in text:
        errors.append("protocol missing governance checker command")
    if "python3 -m unittest tests/test_architecture_governance.py" not in text:
        errors.append("protocol missing governance unittest command")
    if "research/architecture_deltas/" not in text:
        errors.append("protocol missing branch closeout artifact directory reference")

    return errors


def check_classification_surfaces(root: Path) -> list[str]:
    errors: list[str] = []
    for label, rel in CLASSIFICATION_FILES.items():
        path = root / rel
        if not path.is_file():
            continue
        text = _norm(_read(path))
        for classification in REQUIRED_CLASSIFICATIONS:
            if _norm(classification) not in text:
                errors.append(f"{label} missing classification: {classification}")
    return errors


def check_preamble_read_order(root: Path) -> list[str]:
    path = root / ARCH_FILES["preamble"]
    if not path.is_file():
        return []
    text = _norm(_read(path))
    return _ensure_ordered(text, REQUIRED_READ_ORDER, "preamble read-order entry")


def check_closeout_requirements(root: Path) -> list[str]:
    path = root / ARCH_FILES["closeout"]
    if not path.is_file():
        return []

    text = _norm(_read(path))
    errors: list[str] = []
    if "python3 scripts/check_architecture_governance.py" not in text:
        errors.append("closeout missing governance checker command")
    if "python3 -m unittest tests/test_architecture_governance.py" not in text:
        errors.append("closeout missing governance unittest command")
    if "pass/fail" not in text and "passed" not in text:
        errors.append("closeout missing governance pass/fail recording requirement")
    if "research/architecture_deltas/" not in text:
        errors.append("closeout missing branch closeout artifact directory reference")
    return errors


def check_architecture_index(root: Path) -> list[str]:
    path = root / ARCH_FILES["index"]
    if not path.is_file():
        return []

    text = _norm(_read(path))
    errors: list[str] = []
    for ref in INDEX_REQUIRED_REFERENCES:
        if ref not in text:
            errors.append(f"architecture index missing reference: {ref}")
    return errors


def check_closeout_artifact(root: Path, artifact_path: Path) -> list[str]:
    errors: list[str] = []
    target = artifact_path if artifact_path.is_absolute() else root / artifact_path
    target = target.resolve()

    if not target.is_file():
        return [f"closeout artifact not found: {artifact_path}"]

    expected_parent = (root / "research/architecture_deltas").resolve()
    if expected_parent not in target.parents:
        errors.append(
            "closeout artifact must live under research/architecture_deltas/"
        )

    text = _norm(_read(target))
    for field in DELTA_REQUIRED_FIELDS:
        if _norm(field) not in text:
            errors.append(f"closeout artifact missing field: {field}")
    return errors


def _decision_blocks(text: str) -> list[str]:
    parts = re.split(r"^\s*##\s+", text, flags=re.MULTILINE)
    return [part for part in parts[1:] if part.strip()]


def check_decisions(root: Path) -> list[str]:
    path = root / ARCH_FILES["decisions"]
    if not path.is_file():
        return []

    text = _read(path)
    blocks = _decision_blocks(text)
    errors: list[str] = []

    if not blocks:
        return ["decisions file has no decision entries"]

    for index, block in enumerate(blocks, start=1):
        block_norm = _norm(block)
        for field in DECISION_FIELDS:
            token = _norm(f"- {field}:")
            if token not in block_norm:
                errors.append(f"decision entry {index} missing field: {field}")
    return errors


def run_all_checks(root: Path, closeout_artifact: Path | None = None) -> list[str]:
    errors: list[str] = []
    errors.extend(check_required_files(root))
    errors.extend(check_required_sections(root))
    errors.extend(check_protocol(root))
    errors.extend(check_classification_surfaces(root))
    errors.extend(check_preamble_read_order(root))
    errors.extend(check_closeout_requirements(root))
    errors.extend(check_architecture_index(root))
    errors.extend(check_decisions(root))
    if closeout_artifact is not None:
        errors.extend(check_closeout_artifact(root, closeout_artifact))
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--closeout-artifact",
        type=Path,
        default=None,
        help="Optional path to a branch closeout artifact to validate structurally.",
    )
    args = parser.parse_args(argv)

    root = args.repo_root.resolve()
    errors = run_all_checks(root, closeout_artifact=args.closeout_artifact)
    if errors:
        print("Architecture governance check FAILED")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Architecture governance check PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
