"""Apply website_validation_report decisions to districts_complete.csv.

For rows flagged CLEAR, blank out website_url (only). video_* fields and
notes are untouched here; the stream pipeline handles those separately.

Run: python scripts/apply_website_validation.py
"""

from __future__ import annotations

import csv
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SRC = DATA / "districts_complete.csv"
REPORT = DATA / "website_validation_report.csv"


def main() -> int:
    decisions = {
        r["district_id"]: (r["decision"], r["reason"])
        for r in csv.DictReader(REPORT.open())
    }

    with SRC.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    cleared = 0
    for row in rows:
        dec, _ = decisions.get(row["district_id"], (None, None))
        if dec != "CLEAR":
            continue
        row["website_url"] = ""
        cleared += 1

    with SRC.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Cleared {cleared} website_url rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
