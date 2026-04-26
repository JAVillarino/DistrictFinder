#!/usr/bin/env python3
"""
Merge Discovery Results - Texas School Board Video Sources

Consolidates results from all discovery tools into districts_complete.csv:
    - website_crawler.py    → data/crawler_results.csv
    - platform_directory_scraper.py → data/directory_results.csv
    - google_search_finder.py       → data/search_results.csv

Priority order (highest confidence wins):
    1. directory_results (known platform matches)
    2. crawler_results (website-crawled findings)
    3. search_results (search engine findings)

Only updates districts that are currently "pending" in districts_complete.csv.
Never overwrites existing verified data.

Usage:
    python merge_discovery_results.py              # Merge all
    python merge_discovery_results.py --dry-run    # Preview without writing
    python merge_discovery_results.py --report     # Just print stats
"""

import csv
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Configuration
COMPLETE_FILE = "../data/districts_complete.csv"
CRAWLER_FILE = "../data/crawler_results.csv"
DIRECTORY_FILE = "../data/directory_results.csv"
SEARCH_FILE = "../data/search_results.csv"
BACKUP_FILE = "../data/districts_complete_backup_{date}.csv"
LOG_FILE = "merge_results.log"

# Source priority (lower = higher priority)
SOURCE_PRIORITY = {
    "directory_swagit": 1,
    "directory_granicus": 2,
    "directory_boxcast": 3,
    "directory_boarddocs": 4,
    "crawler_found": 5,
    "google_api": 6,
    "duckduckgo": 7,
}

# Confidence priority
CONFIDENCE_PRIORITY = {"high": 1, "medium": 2, "low": 3}


def log(message):
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def load_csv(filepath):
    """Load a CSV file into a dict keyed by district_id."""
    data = {}
    if Path(filepath).exists():
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                data[row["district_id"]] = row
    return data


def pick_best_result(results):
    """Given multiple results for a district, pick the best one."""
    if len(results) == 1:
        return results[0]

    # Sort by confidence then source priority
    def sort_key(r):
        conf = CONFIDENCE_PRIORITY.get(r.get("confidence", "low"), 9)
        source = r.get("source", r.get("video_status", "unknown"))
        src_pri = SOURCE_PRIORITY.get(source, 8)
        return (conf, src_pri)

    results.sort(key=sort_key)
    return results[0]


def merge_into_complete(complete, new_result):
    """Merge a new result into a complete CSV row."""
    row = complete.copy()

    # Map fields from discovery results to complete CSV format
    field_map = {
        "website_url": "website_url",
        "video_platform": "video_platform",
        "video_url": "video_url",
        "youtube_channel_id": "youtube_channel_id",
        "confidence": "confidence",
        "last_checked": "last_checked",
    }

    for src_field, dst_field in field_map.items():
        value = new_result.get(src_field, "")
        if value and value.strip():
            row[dst_field] = value.strip()

    # Build notes
    source = new_result.get("source", new_result.get("video_status", "auto"))
    existing_notes = row.get("notes", "")
    new_notes = new_result.get("notes", "")
    if new_notes:
        row["notes"] = new_notes
    elif existing_notes:
        row["notes"] = existing_notes

    # Update status
    row["video_status"] = "auto_discovered"

    return row


def result_signatures(result):
    """Return compact URL signatures used in validation-cleared notes."""
    url = result.get("video_url") or result.get("website_url") or ""
    platform = result.get("video_platform") or "website"
    parsed = urlparse(url)
    host = (parsed.hostname or "").removeprefix("www.").lower()
    path = parsed.path.strip("/")
    signatures = set()

    if "youtube.com" in host:
        if path.startswith("@"):
            signatures.add(f"yt_handle:{path.split('/')[0].lower().removeprefix('@')}")
        if path.startswith("channel/"):
            parts = path.split("/")
            if len(parts) >= 2:
                signatures.add(f"yt_channel_id:{parts[1]}")
        if path.startswith("c/"):
            parts = path.split("/")
            if len(parts) >= 2:
                signatures.add(f"yt_c:{parts[1].lower()}")
        if path.startswith("user/"):
            parts = path.split("/")
            if len(parts) >= 2:
                signatures.add(f"yt_user:{parts[1].lower()}")
        if path.startswith("embed/"):
            parts = path.split("/")
            if len(parts) >= 2:
                signatures.add(f"yt_other:embed/{parts[1].lower()}")
        if path == "watch":
            signatures.add("yt_other:watch")
    if "youtu.be" in host and path:
        signatures.add(f"yt_other:{path.lower()}")
    if host:
        signatures.add(f"{platform}:{host}")
        signatures.add(f"website:{host}")
        if "swagit.com" in host:
            signatures.add(f"swagit:{host.split('.')[0]}")
    return signatures


def is_cleared_result(row, result):
    """Return True when this exact candidate was already cleared."""
    notes = row.get("notes", "").lstrip()
    if row.get("video_status") != "pending" or not notes.startswith("Cleared:"):
        return False
    if "yt_channel_id URL shared" in notes and any(
        signature.startswith("yt_channel_id:") for signature in result_signatures(result)
    ):
        return True
    return any(signature in notes for signature in result_signatures(result))


def main():
    parser = argparse.ArgumentParser(description="Merge Discovery Results")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--report", action="store_true", help="Just print stats")

    args = parser.parse_args()

    log("Starting Merge Discovery Results")

    # Load complete dataset
    complete = load_csv(COMPLETE_FILE)
    log(f"Loaded {len(complete)} districts from districts_complete.csv")

    # Count current state
    pending_count = sum(1 for d in complete.values() if d.get("video_status") == "pending")
    verified_count = sum(1 for d in complete.values() if d.get("video_status") == "verified")
    log(f"  Verified: {verified_count}, Pending: {pending_count}")

    # Load discovery results
    crawler_results = load_csv(CRAWLER_FILE)
    directory_results = load_csv(DIRECTORY_FILE)
    search_results = load_csv(SEARCH_FILE)

    log(f"  Crawler results: {len(crawler_results)}")
    log(f"  Directory results: {len(directory_results)}")
    log(f"  Search results: {len(search_results)}")

    if args.report:
        # Just show overlap stats
        all_found = set(crawler_results.keys()) | set(directory_results.keys()) | set(search_results.keys())
        pending_ids = set(d["district_id"] for d in complete.values() if d.get("video_status") == "pending")
        new_finds = {
            did for did in (all_found & pending_ids)
            if any(
                not is_cleared_result(complete[did], result)
                for result in [directory_results.get(did), crawler_results.get(did), search_results.get(did)]
                if result
            )
        }
        log(f"\n  New districts that can be updated: {len(new_finds)}")

        # By confidence
        for source_name, source_data in [("crawler", crawler_results),
                                          ("directory", directory_results),
                                          ("search", search_results)]:
            high = sum(1 for d in source_data.values() if d.get("confidence") == "high" and d["district_id"] in pending_ids)
            med = sum(1 for d in source_data.values() if d.get("confidence") == "medium" and d["district_id"] in pending_ids)
            low = sum(1 for d in source_data.values() if d.get("confidence") == "low" and d["district_id"] in pending_ids)
            log(f"    {source_name}: {high} high, {med} medium, {low} low")
        return

    # Collect all results per district, only for pending districts
    candidates = {}  # district_id -> [results]
    for did, result in directory_results.items():
        if complete.get(did, {}).get("video_status") == "pending" and not is_cleared_result(complete[did], result):
            candidates.setdefault(did, []).append(result)

    for did, result in crawler_results.items():
        if complete.get(did, {}).get("video_status") == "pending" and not is_cleared_result(complete[did], result):
            candidates.setdefault(did, []).append(result)

    for did, result in search_results.items():
        if complete.get(did, {}).get("video_status") == "pending" and not is_cleared_result(complete[did], result):
            candidates.setdefault(did, []).append(result)

    log(f"\n  Districts with new data: {len(candidates)}")

    if not candidates:
        log("Nothing to merge.")
        return

    # Pick best result for each district and merge
    updated_count = 0
    platform_counts = {}

    for did, result_list in candidates.items():
        best = pick_best_result(result_list)
        merged = merge_into_complete(complete[did], best)
        complete[did] = merged
        updated_count += 1

        platform = best.get("video_platform", "unknown")
        platform_counts[platform] = platform_counts.get(platform, 0) + 1

    log(f"  Districts to update: {updated_count}")
    log(f"  By platform:")
    for p, c in sorted(platform_counts.items(), key=lambda x: -x[1]):
        log(f"    {p}: {c}")

    if args.dry_run:
        log("\n  DRY RUN — no files written")
        return

    # Backup existing file
    backup_path = BACKUP_FILE.format(date=datetime.now().strftime("%Y%m%d_%H%M%S"))
    import shutil
    shutil.copy2(COMPLETE_FILE, backup_path)
    log(f"  Backup saved to: {backup_path}")

    # Write updated complete file
    default_fieldnames = ["district_id", "district_name", "county", "enrollment",
                          "website_url", "video_platform", "video_url", "archive_start_year",
                          "youtube_channel_id", "notes", "confidence", "last_checked", "video_status"]
    existing_fieldnames = []
    with open(COMPLETE_FILE, "r") as f:
        existing_fieldnames = csv.DictReader(f).fieldnames or []
    fieldnames = existing_fieldnames or default_fieldnames
    for field in default_fieldnames:
        if field not in fieldnames:
            fieldnames.append(field)

    with open(COMPLETE_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for did in sorted(complete.keys()):
            row = {k: complete[did].get(k, "") for k in fieldnames}
            writer.writerow(row)

    new_pending = sum(1 for d in complete.values() if d.get("video_status") == "pending")
    new_discovered = sum(1 for d in complete.values() if d.get("video_status") == "auto_discovered")

    log(f"\n{'='*60}")
    log(f"Merge Complete!")
    log(f"  Updated: {updated_count} districts")
    log(f"  Verified: {verified_count}")
    log(f"  Auto-discovered: {new_discovered}")
    log(f"  Still pending: {new_pending}")
    log(f"  Written to: {COMPLETE_FILE}")
    log(f"{'='*60}\n")


if __name__ == "__main__":
    main()
