"""
MODULE_SPEC
module_id: scripts.new_incident
responsibility: Ingest raw incident JSON into repo-local incident artifacts.
inputs: Optional path to raw incident JSON; otherwise newest diagnostics/inbox/*.json.
outputs: Legacy markdown view at diagnostics/incidents/<incident-id>.md; authoritative Incident.v1 evidence JSON at diagnostics/evidence/incidents/<incident-id>.json; markdown view copy at diagnostics/evidence/views/<incident-id>.md.
invariants: Legacy markdown behavior remains intact; structured evidence is append-only and authoritative; markdown is a derived view.
experiment_toggles: REPO_TRACE_WRITE_V1_EVIDENCE=1 (default on)
"""

import json
import os
import sys
from pathlib import Path

from artifact_adapters import adapt_raw_incident_to_v1


def newest_inbox_json(inbox_dir: Path) -> Path:
    candidates = [p for p in inbox_dir.glob("*.json") if p.is_file()]
    if not candidates:
        print("no incident JSON files found in diagnostics/inbox/")
        raise SystemExit(1)
    return max(candidates, key=lambda p: p.stat().st_mtime)


def format_markdown_view(data: dict) -> str:
    breadcrumbs = "\n".join(
        f"- [{b['timestamp']}] ({b['category']}) {b['message']}"
        for b in data.get("breadcrumbs", [])
    )

    return f"""# {data['id']}

## Title
{data.get("title", "")}

## Expected
{data.get("expectedBehavior", "")}

## Actual
{data.get("actualBehavior", "")}

## Notes
{data.get("reporterNotes", "")}

## Metadata
- App Version: {data["metadata"].get("appVersion", "")}
- Build: {data["metadata"].get("buildNumber", "")}
- iOS: {data["metadata"].get("osVersion", "")}
- Device: {data["metadata"].get("deviceModel", "")}
- Screen: {data["metadata"].get("screenName", "")}
- Commit: {data["metadata"].get("gitCommit", "")}
- Timestamp: {data["metadata"].get("timestamp", "")}

## Breadcrumbs
{breadcrumbs if breadcrumbs else "- none"}

## Screenshot
{data.get("screenshotFilename", "")}
"""


def main() -> None:
    if len(sys.argv) > 2:
        print("usage: python scripts/new_incident.py [path/to/incident.json]")
        raise SystemExit(1)

    if len(sys.argv) == 2:
        src = Path(sys.argv[1])
    else:
        src = newest_inbox_json(Path("diagnostics/inbox"))

    if not src.exists():
        print(f"input file does not exist: {src}")
        raise SystemExit(1)

    data = json.loads(src.read_text())

    incident_id = data["id"]
    markdown_text = format_markdown_view(data)

    legacy_view_dir = Path("diagnostics/incidents")
    legacy_view_dir.mkdir(parents=True, exist_ok=True)
    legacy_view_file = legacy_view_dir / f"{incident_id}.md"
    legacy_view_file.write_text(markdown_text)

    evidence_dir = Path("diagnostics/evidence/incidents")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = evidence_dir / f"{incident_id}.json"

    write_v1_evidence = os.getenv("REPO_TRACE_WRITE_V1_EVIDENCE", "1") != "0"

    view_dir = Path("diagnostics/evidence/views")
    view_dir.mkdir(parents=True, exist_ok=True)
    view_file = view_dir / f"{incident_id}.md"

    if write_v1_evidence:
        incident_v1 = adapt_raw_incident_to_v1(
            data,
            produced_by="scripts/new_incident.py",
            source_path=str(src),
        )
        evidence_file.write_text(json.dumps(incident_v1, indent=2) + "\n")
        view_file.write_text(markdown_text)
    else:
        print("skipped Incident.v1 evidence write (REPO_TRACE_WRITE_V1_EVIDENCE=0)")

    print(f"wrote {legacy_view_file}")
    if write_v1_evidence:
        print(f"wrote {evidence_file}")
        print(f"wrote {view_file}")


if __name__ == "__main__":
    main()
