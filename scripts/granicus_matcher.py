#!/usr/bin/env python3
"""
Granicus Pattern Matcher - Texas School Board Video Sources

Handles 5-7% of districts by testing predictable Granicus URL patterns.
Granicus URLs follow patterns like: {districtname}.granicus.com

Usage:
    python granicus_matcher.py --batch 125-155
    python granicus_matcher.py --resume
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
PROGRESS_FILE = "granicus_progress.json"
LOG_FILE = "granicus_matcher.log"

REQUEST_TIMEOUT = 10
DELAY_BETWEEN_REQUESTS = 0.5
USER_AGENT = "Mozilla/5.0 (educational research project)"

# Granicus URL patterns
GRANICUS_PATTERNS = [
    "{name}.granicus.com/",
    "{name}isd.granicus.com/player/",
    "{name}tx.iqm2.com/Citizens/",
    "{name}schoolstx.iqm2.com/Citizens/",
]


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
    """
    # Remove "ISD" suffix
    name = district_name.replace(" ISD", "").replace(" I.S.D.", "")
    name = name.replace(" Independent School District", "")
    name = name.replace(" CISD", "").replace(" MSD", "")

    # Remove punctuation and spaces
    name = re.sub(r'[^a-zA-Z]', '', name)

    # Lowercase
    return name.lower()


def test_granicus_url(district_name):
    """
    Test all Granicus URL patterns for a district.
    Returns (url, confidence_score) or (None, 0)
    """
    normalized = normalize_district_name(district_name)

    for pattern in GRANICUS_PATTERNS:
        url = f"https://{pattern.format(name=normalized)}"

        try:
            response = requests.head(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                headers={"User-Agent": USER_AGENT}
            )

            if response.status_code == 405:
                response = requests.get(
                    url,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                    headers={"User-Agent": USER_AGENT}
                )

            if response.status_code < 400:
                if response.status_code == 200 and response.text:
                    score = calculate_confidence(response.text, url)
                    return (url, score)
                else:
                    return (url, 85)

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.TooManyRedirects):
            continue
        except Exception as e:
            log(f"  Error testing {url}: {str(e)}")
            continue

    return (None, 0)


def calculate_confidence(html_content, url):
    """Calculate confidence score based on page content"""
    score = 30  # Base score for successful HTTP

    html_lower = html_content.lower()

    # Granicus keywords (20 pts)
    if "granicus" in html_lower or "iqm2" in html_lower:
        score += 20

    # Board meeting keywords (10 pts)
    if any(k in html_lower for k in ["board", "meeting", "trustees"]):
        score += 10

    # Video player elements (20 pts)
    if any(e in html_lower for e in ["iframe", "video", "embed"]):
        score += 20

    # URL pattern (20 pts)
    if "granicus.com" in url or "iqm2.com" in url:
        score += 20

    return min(score, 100)


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

    entry = {
        "district_id": district_id,
        "district_name": district_name,
        "county": county,
        "enrollment": enrollment,
        "website_url": f"https://{normalize_district_name(district_name)}isd.net",
        "video_platform": "granicus",
        "video_url": url,
        "archive_start_year": "",
        "youtube_channel_id": "",
        "notes": f"Found via pattern matching. Granicus platform at {url}. Automated discovery.",
        "confidence": "high" if confidence >= 85 else "medium",
        "last_checked": datetime.now().strftime("%Y-%m-%d")
    }

    existing[district_id] = entry

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
    progress = load_progress() if resume else {"processed_ids": [], "last_batch": None}

    with open(INPUT_FILE, "r") as f:
        reader = csv.DictReader(f)
        districts = list(reader)

    if batch_start and batch_end:
        districts = [d for d in districts if batch_start <= int(d.get("district_id", "0")[:6] or "0") <= batch_end]
        log(f"Processing batch: districts {batch_start}-{batch_end} ({len(districts)} districts)")
    else:
        log(f"Processing all {len(districts)} districts")

    if resume:
        districts = [d for d in districts if d["district_id"] not in progress["processed_ids"]]
        log(f"Resuming: {len(districts)} districts remaining")

    found_count = 0
    not_found_count = 0

    for i, district in enumerate(districts):
        district_id = district["district_id"]
        district_name = district["district_name"]
        county = district.get("county", "")
        enrollment = district.get("enrollment", "")

        log(f"Processing [{i+1}/{len(districts)}]: {district_name} ({district_id})")

        url, confidence = test_granicus_url(district_name)

        if url and confidence >= 60:
            log(f"  ✓ FOUND: {url} (confidence: {confidence})")
            write_to_csv(district_id, district_name, county, enrollment, url, confidence)
            found_count += 1
        else:
            log(f"  ✗ Not found on Granicus")
            not_found_count += 1

        progress["processed_ids"].append(district_id)

        if (i + 1) % 10 == 0:
            save_progress(progress)
            log(f"Progress saved: {i+1}/{len(districts)} processed")

        import time
        time.sleep(DELAY_BETWEEN_REQUESTS)

    save_progress(progress)

    log(f"\n{'='*60}")
    log(f"Granicus Pattern Matching Complete!")
    log(f"  Total processed: {len(districts)}")
    log(f"  Found on Granicus: {found_count} ({found_count/len(districts)*100:.1f}%)")
    log(f"  Not found: {not_found_count}")
    log(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Granicus Pattern Matcher for Texas School Districts")
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

    log("Starting Granicus Pattern Matcher")
    process_districts(batch_start, batch_end, args.resume)


if __name__ == "__main__":
    main()
