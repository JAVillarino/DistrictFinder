"""Audit the primary district CSV for structural and data-quality issues.

This does not fetch the network. It verifies invariants that should hold
after discovery/validation:
  - districts_complete.csv contains exactly the TEA district IDs
  - required fields and coordinate columns exist
  - populated URLs agree with status fields
  - coordinates are in a Texas-ish bounding box
  - duplicate video URLs are reported for review

Run:
    python scripts/audit_dataset.py
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
COMPLETE = DATA / "districts_complete.csv"
MASTER = DATA / "tea_districts_master_clean.csv"

REQUIRED_COLUMNS = [
    "district_id", "district_name", "county", "enrollment", "website_url",
    "video_platform", "video_url", "archive_start_year", "youtube_channel_id",
    "notes", "confidence", "last_checked", "video_status", "latitude",
    "longitude", "coordinate_source",
]

TEXAS_BOUNDS = {
    "min_lat": 25.0,
    "max_lat": 37.0,
    "min_lng": -107.5,
    "max_lng": -93.0,
}


def read_csv(path: Path) -> tuple[list[dict], list[str]]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def add_issue(issues: list[str], message: str) -> None:
    issues.append(f"ERROR: {message}")


def add_warning(warnings: list[str], message: str) -> None:
    warnings.append(f"WARN: {message}")


def audit() -> int:
    rows, fieldnames = read_csv(COMPLETE)
    master_rows, _ = read_csv(MASTER)
    issues: list[str] = []
    warnings: list[str] = []

    missing_columns = [field for field in REQUIRED_COLUMNS if field not in fieldnames]
    if missing_columns:
        add_issue(issues, f"missing columns: {', '.join(missing_columns)}")

    ids = [row.get("district_id", "") for row in rows]
    master_ids = {row["district_id"] for row in master_rows}
    if len(rows) != len(master_rows):
        add_issue(issues, f"row count {len(rows)} does not match TEA master {len(master_rows)}")
    if len(set(ids)) != len(ids):
        duplicates = [did for did, count in Counter(ids).items() if count > 1]
        add_issue(issues, f"duplicate district IDs: {', '.join(duplicates[:20])}")
    if set(ids) != master_ids:
        add_issue(
            issues,
            f"district ID set differs from TEA master: missing={len(master_ids - set(ids))}, extra={len(set(ids) - master_ids)}",
        )

    status_counts = Counter(row.get("video_status", "") for row in rows)
    video_populated = sum(bool(row.get("video_url", "").strip()) for row in rows)
    website_populated = sum(bool(row.get("website_url", "").strip()) for row in rows)
    coords_populated = 0

    video_url_to_ids: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        did = row.get("district_id", "")
        status = row.get("video_status", "")
        video_url = row.get("video_url", "").strip()
        platform = row.get("video_platform", "").strip()
        lat = row.get("latitude", "").strip()
        lng = row.get("longitude", "").strip()

        if status in {"verified", "auto_discovered"} and not video_url:
            add_issue(issues, f"{did} is {status} but has no video_url")
        if status == "pending" and video_url:
            add_issue(issues, f"{did} is pending but still has video_url")
        if video_url and not platform:
            add_warning(warnings, f"{did} has video_url but no video_platform")
        if platform and not video_url:
            add_warning(warnings, f"{did} has video_platform but no video_url")

        if video_url:
            video_url_to_ids[video_url].append(did)

        if lat or lng:
            try:
                lat_num = float(lat)
                lng_num = float(lng)
            except ValueError:
                add_issue(issues, f"{did} has non-numeric coordinates: {lat}, {lng}")
                continue
            coords_populated += 1
            if not (TEXAS_BOUNDS["min_lat"] <= lat_num <= TEXAS_BOUNDS["max_lat"]):
                add_issue(issues, f"{did} latitude outside Texas bounds: {lat}")
            if not (TEXAS_BOUNDS["min_lng"] <= lng_num <= TEXAS_BOUNDS["max_lng"]):
                add_issue(issues, f"{did} longitude outside Texas bounds: {lng}")

    duplicate_video_urls = {
        url: ids for url, ids in video_url_to_ids.items()
        if len(ids) > 1 and "boardbook.org" not in url and "citizenportal.ai" not in url
    }
    for url, dids in sorted(duplicate_video_urls.items(), key=lambda item: (-len(item[1]), item[0]))[:25]:
        add_warning(warnings, f"duplicate video_url shared by {len(dids)} districts: {url} ({', '.join(dids)})")

    print("Dataset Audit")
    print(f"  rows: {len(rows)}")
    print(f"  unique district IDs: {len(set(ids))}")
    print(f"  video URLs populated: {video_populated}")
    print(f"  website URLs populated: {website_populated}")
    print(f"  coordinates populated: {coords_populated}")
    print(f"  status counts: {dict(status_counts)}")
    print(f"  warnings: {len(warnings)}")
    print(f"  errors: {len(issues)}")

    for message in warnings[:50]:
        print(message)
    for message in issues:
        print(message)

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(audit())
