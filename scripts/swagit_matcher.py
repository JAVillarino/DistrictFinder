#!/usr/bin/env python3
"""
Swagit Pattern Matcher - Texas School Board Video Sources

Handles 35% of all districts by testing predictable Swagit URL patterns.
Swagit URLs follow patterns like: {districtname}isd.new.swagit.com

Usage:
    python swagit_matcher.py --batch 125-155
    python swagit_matcher.py --resume
"""

import csv
import requests
import re
import json
import argparse
from datetime import datetime
from pathlib import Path

# Configuration
INPUT_FILE = "../data/districts_input.csv"
OUTPUT_FILE = "../data/districts_output.csv"
PROGRESS_FILE = "swagit_progress.json"
LOG_FILE = "swagit_matcher.log"

REQUEST_TIMEOUT = 10
DELAY_BETWEEN_REQUESTS = 0.5
USER_AGENT = "Mozilla/5.0 (educational research project)"

# Swagit URL patterns (in order of probability)
SWAGIT_PATTERNS = [
    "{name}isd.new.swagit.com",       # Most common
    "{name}isdtx.new.swagit.com",     # Texas-specific
    "{name}isd.swagit.com",           # Legacy
    "{name}isdtx.swagit.com",         # Legacy TX
    "{name}isdtx.v3.swagit.com",      # Version 3
]

# Keywords for content validation
VIDEO_KEYWORDS = ["swagit", "board", "meeting", "video", "trustees"]
VIDEO_PLAYER_ELEMENTS = ["iframe", "embed", "video"]


def log(message):
    """Log message to console and file"""
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def normalize_district_name(district_name):
    """
    Normalize district name for URL construction.
    Examples:
        "Fort Worth ISD" → "fortworth"
        "Houston ISD" → "houston"
        "Cypress-Fairbanks ISD" → "cypressfairbanks"
    """
    # Remove "ISD" suffix
    name = district_name.replace(" ISD", "").replace(" I.S.D.", "")

    # Remove common suffixes
    name = name.replace(" Independent School District", "")
    name = name.replace(" CISD", "").replace(" MSD", "")

    # Remove punctuation and spaces
    name = re.sub(r'[^a-zA-Z]', '', name)

    # Lowercase
    return name.lower()


def test_swagit_url(district_name):
    """
    Test all Swagit URL patterns for a district.
    Returns (url, confidence_score) or (None, 0)
    """
    normalized = normalize_district_name(district_name)

    for pattern in SWAGIT_PATTERNS:
        url = f"https://{pattern.format(name=normalized)}/"

        try:
            # Try HEAD first (faster)
            response = requests.head(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                headers={"User-Agent": USER_AGENT}
            )

            # If 405 (Method Not Allowed), try GET
            if response.status_code == 405:
                response = requests.get(
                    url,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                    headers={"User-Agent": USER_AGENT}
                )

            # Check if successful
            if response.status_code < 400:
                # Verify content if we have it
                if response.status_code == 200 and response.text:
                    score = calculate_confidence(response.text, url)
                    return (url, score)
                else:
                    # HEAD request successful, assume valid
                    return (url, 85)  # Base confidence for pattern match

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.TooManyRedirects):
            continue
        except Exception as e:
            log(f"  Error testing {url}: {str(e)}")
            continue

    return (None, 0)


def calculate_confidence(html_content, url):
    """
    Calculate confidence score based on page content.
    Score breakdown:
        - HTTP 200: 30 pts (already verified)
        - Swagit keywords: 20 pts
        - Board/meeting keywords: 10 pts
        - Video player elements: 20 pts
        - URL pattern match: 20 pts
    Total possible: 100 pts
    """
    score = 30  # Base score for successful HTTP response

    html_lower = html_content.lower()

    # Check for swagit-specific keywords (20 pts)
    if "swagit" in html_lower:
        score += 20

    # Check for board meeting keywords (10 pts)
    board_keywords = ["board", "meeting", "trustees"]
    if any(keyword in html_lower for keyword in board_keywords):
        score += 10

    # Check for video player elements (20 pts)
    if any(element in html_lower for element in VIDEO_PLAYER_ELEMENTS):
        score += 20

    # URL pattern bonus (20 pts)
    if "swagit.com" in url:
        score += 20

    return min(score, 100)  # Cap at 100


def load_progress():
    """Load progress from JSON file"""
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"processed_ids": [], "last_batch": None}


def save_progress(progress):
    """Save progress to JSON file"""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def load_existing_csv():
    """Load existing district_video_sources.csv entries"""
    existing = {}
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing[row["district_id"]] = row
    return existing


def write_to_csv(district_id, district_name, county, enrollment, url, confidence):
    """Append or update entry in district_video_sources.csv"""
    existing = load_existing_csv()

    # Create new entry
    entry = {
        "district_id": district_id,
        "district_name": district_name,
        "county": county,
        "enrollment": enrollment,
        "website_url": f"https://{normalize_district_name(district_name)}isd.net",  # Educated guess
        "video_platform": "swagit",
        "video_url": url,
        "archive_start_year": "",  # To be filled by validation_pipeline
        "youtube_channel_id": "",
        "notes": f"Found via pattern matching. Swagit platform at {url}. Automated discovery.",
        "confidence": "high" if confidence >= 85 else "medium",
        "last_checked": datetime.now().strftime("%Y-%m-%d")
    }

    # Update or add
    existing[district_id] = entry

    # Write all entries back
    if existing:
        fieldnames = ["district_id", "district_name", "county", "enrollment", "website_url",
                     "video_platform", "video_url", "archive_start_year", "youtube_channel_id",
                     "notes", "confidence", "last_checked"]

        with open(OUTPUT_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(existing.values())


def process_districts(batch_start=None, batch_end=None, resume=False):
    """Process districts from starter CSV"""
    # Load progress
    progress = load_progress() if resume else {"processed_ids": [], "last_batch": None}

    # Load input districts
    with open(INPUT_FILE, "r") as f:
        reader = csv.DictReader(f)
        districts = list(reader)

    # Filter by batch if specified (batch refers to row numbers in CSV, 1-indexed)
    if batch_start is not None and batch_end is not None:
        # Convert to 0-indexed and slice the list
        # batch_start=131 means row 131 in CSV (after header), which is index 130 in the list
        start_idx = batch_start - 1
        end_idx = batch_end  # end is exclusive in Python slicing, so batch_end 150 means up to index 150 (row 150 inclusive)
        districts = districts[start_idx:end_idx]
        log(f"Processing batch: rows {batch_start}-{batch_end} ({len(districts)} districts)")
    else:
        log(f"Processing all {len(districts)} districts")

    # Skip already processed if resuming
    if resume:
        districts = [d for d in districts if d["district_id"] not in progress["processed_ids"]]
        log(f"Resuming: {len(districts)} districts remaining")

    # Process each district
    found_count = 0
    not_found_count = 0

    for i, district in enumerate(districts):
        district_id = district["district_id"]
        district_name = district["district_name"]
        county = district.get("county", "")
        enrollment = district.get("enrollment", "")

        log(f"Processing [{i+1}/{len(districts)}]: {district_name} ({district_id})")

        # Test Swagit patterns
        url, confidence = test_swagit_url(district_name)

        if url and confidence >= 60:  # Minimum threshold
            log(f"  ✓ FOUND: {url} (confidence: {confidence})")
            write_to_csv(district_id, district_name, county, enrollment, url, confidence)
            found_count += 1
        else:
            log(f"  ✗ Not found on Swagit")
            not_found_count += 1

        # Update progress
        progress["processed_ids"].append(district_id)

        # Save progress every 10 districts
        if (i + 1) % 10 == 0:
            save_progress(progress)
            log(f"Progress saved: {i+1}/{len(districts)} processed (Found: {found_count}, Not found: {not_found_count})")

        # Rate limiting
        import time
        time.sleep(DELAY_BETWEEN_REQUESTS)

    # Final save
    save_progress(progress)

    # Summary
    log(f"\n{'='*60}")
    log(f"Swagit Pattern Matching Complete!")
    log(f"  Total processed: {len(districts)}")
    if len(districts) > 0:
        log(f"  Found on Swagit: {found_count} ({found_count/len(districts)*100:.1f}%)")
    else:
        log(f"  Found on Swagit: {found_count} (0.0%)")
    log(f"  Not found: {not_found_count}")
    log(f"  Output written to: {OUTPUT_FILE}")
    log(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Swagit Pattern Matcher for Texas School Districts")
    parser.add_argument("--batch", help="Batch range (e.g., 125-155)", type=str)
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")

    args = parser.parse_args()

    batch_start = None
    batch_end = None

    if args.batch:
        parts = args.batch.split("-")
        if len(parts) == 2:
            batch_start = int(parts[0])
            batch_end = int(parts[1])

    log("Starting Swagit Pattern Matcher")
    log(f"Confidence threshold: ≥85 for HIGH, ≥60 for MEDIUM")

    process_districts(batch_start, batch_end, args.resume)


if __name__ == "__main__":
    main()
