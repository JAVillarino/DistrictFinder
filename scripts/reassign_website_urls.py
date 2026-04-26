"""Reassign CLEAR'd website URLs to the districts whose names appear in
the URL. Mirrors scripts/reassign_stream_urls.py but targets the
`website_url` column.
"""

from __future__ import annotations

import csv
from pathlib import Path

from reassign_stream_urls import best_target, UNVERIFIABLE  # reuse scoring

DATA = Path(__file__).resolve().parent.parent / "data"
SRC = DATA / "districts_complete.csv"
REPORT = DATA / "website_validation_report.csv"


def main() -> int:
    with SRC.open() as f:
        fieldnames = csv.DictReader(f).fieldnames
    rows = list(csv.DictReader(SRC.open()))

    report_by_id = {r["district_id"]: r for r in csv.DictReader(REPORT.open())}

    reassigned = 0
    conflicts = 0
    skipped = 0
    for src_id, rep in report_by_id.items():
        if rep["decision"] != "CLEAR":
            continue
        plat, ident = rep["signature"].split(":", 1)
        if plat in UNVERIFIABLE:
            skipped += 1
            continue
        target = best_target(rows, (plat, ident))
        if target is None or target["district_id"] == src_id:
            continue
        if target["website_url"].strip():
            conflicts += 1
            print(f"CONFLICT: {ident} -> {target['district_name']} (already has {target['website_url']})")
            continue
        target["website_url"] = rep["website_url"]
        reassigned += 1
        print(f"REASSIGN: {rep['website_url']} : {rep['district_name']} -> {target['district_name']}")

    with SRC.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print()
    print(f"Reassigned: {reassigned}")
    print(f"Conflicts: {conflicts}")
    print(f"Skipped (unverifiable): {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
