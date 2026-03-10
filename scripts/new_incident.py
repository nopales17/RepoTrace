import json
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("usage: python scripts/new_incident.py /path/to/incident.json")
    raise SystemExit(1)

src = Path(sys.argv[1])
data = json.loads(src.read_text())

incident_id = data["id"]
out_dir = Path("diagnostics/incidents")
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / f"{incident_id}.md"

breadcrumbs = "\n".join(
    f"- [{b['timestamp']}] ({b['category']}) {b['message']}"
    for b in data.get("breadcrumbs", [])
)

text = f"""# {incident_id}

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

out_file.write_text(text)
print(f"wrote {out_file}")
