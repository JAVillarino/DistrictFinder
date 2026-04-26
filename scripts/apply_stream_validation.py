"""Apply decisions from data/stream_validation_report.csv to districts_complete.csv.

For every row flagged CLEAR: wipe video_platform, video_url,
archive_start_year, youtube_channel_id, confidence, last_checked; set
video_status to 'pending' and append a note explaining why. notes
describing a specific *other* video URL (e.g. "Board Meeting Video Archive
on ...") are also wiped to avoid leaving stale breadcrumbs pointing at the
wrong district.

KEEP and REVIEW rows are left untouched.

Run: python scripts/apply_stream_validation.py
"""

from __future__ import annotations

import csv
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SRC = DATA / "districts_complete.csv"
REPORT = DATA / "stream_validation_report.csv"


def main() -> int:
    decisions: dict[str, tuple[str, str]] = {}
    for row in csv.DictReader(REPORT.open()):
        decisions[row["district_id"]] = (row["decision"], row["reason"])

    with SRC.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    cleared = 0
    for row in rows:
        dec, reason = decisions.get(row["district_id"], (None, None))
        if dec != "CLEAR":
            continue
        row["video_platform"] = ""
        row["video_url"] = ""
        row["archive_start_year"] = ""
        row["youtube_channel_id"] = ""
        row["notes"] = f"Cleared: {reason}"
        row["confidence"] = ""
        row["last_checked"] = ""
        row["video_status"] = "pending"
        cleared += 1

    with SRC.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Cleared {cleared} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
