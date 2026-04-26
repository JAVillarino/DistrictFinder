#!/usr/bin/env python3
"""
Validation Pipeline - Texas School Board Video Sources

Validates ALL entries (script-generated and agent-generated) with automated confidence scoring.

Three-Layer Validation:
    1. HTTP Check (30 pts)
    2. Content Keywords (40 pts)
    3. Archive Depth (30 pts)

Confidence Levels:
    ≥85 pts = HIGH (auto-approve)
    60-84 pts = MEDIUM (agent review)
    <60 pts = LOW

Usage:
    python validation_pipeline.py  # Validate all entries
    python validation_pipeline.py --batch 125-155
    python validation_pipeline.py --latest-batch  # Last 30 districts
"""

import csv
import requests
from bs4 import BeautifulSoup
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
INPUT_FILE = "../data/districts_output.csv"
OUTPUT_FILE = "../Initial push/district_video_sources_validated.csv"
QUEUE_FILE = "agent_queue.csv"
LOG_FILE = "validation.log"

REQUEST_TIMEOUT = 10
DELAY_BETWEEN_REQUESTS = 0.5
USER_AGENT = "Mozilla/5.0 (educational research project)"

# Scoring thresholds
HIGH_THRESHOLD = 85
MEDIUM_THRESHOLD = 60

# Keywords for content validation
VIDEO_KEYWORDS = {
    'player': ['iframe', 'video', 'embed', 'player', 'swagit', 'granicus', 'youtube'],  # 20 pts
    'board': ['board', 'meeting', 'trustees', 'regular meeting'],  # 10 pts
    'archive': ['archive', 'past', 'recordings', 'previous', 'watch']  # 10 pts
}


def log(message):
    """Log message to console and file"""
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def check_http_status(url):
    """
    Check if URL is accessible.
    Returns (status_code, is_live, response_text)
    """
    if not url or url == "":
        return (None, False, "")

    try:
        # Try HEAD first
        response = requests.head(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT}
        )

        # If 405, try GET
        if response.status_code == 405:
            response = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                headers={"User-Agent": USER_AGENT}
            )

        is_live = response.status_code < 400
        content = response.text if response.status_code == 200 else ""

        return (response.status_code, is_live, content)

    except requests.exceptions.Timeout:
        return (None, False, "")
    except requests.exceptions.ConnectionError:
        return (None, False, "")
    except Exception as e:
        log(f"  Error: {e}")
        return (None, False, "")


def score_content_keywords(html_content):
    """
    Score content based on keyword presence.
    Returns score (0-40 points)
    """
    if not html_content:
        return 0

    html_lower = html_content.lower()
    score = 0

    # Video player keywords (20 pts)
    if any(keyword in html_lower for keyword in VIDEO_KEYWORDS['player']):
        score += 20

    # Board meeting keywords (10 pts)
    if any(keyword in html_lower for keyword in VIDEO_KEYWORDS['board']):
        score += 10

    # Archive keywords (10 pts)
    if any(keyword in html_lower for keyword in VIDEO_KEYWORDS['archive']):
        score += 10

    return score


def estimate_archive_depth(html_content, platform):
    """
    Estimate archive depth (number of meetings, recency).
    Returns score (0-30 points)
    """
    score = 0

    if not html_content:
        return 0

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Count video/meeting elements
        video_elements = len(soup.find_all(['iframe', 'video', 'embed']))

        # Platform-specific patterns
        if platform == "swagit":
            # Swagit lists meetings as links
            meeting_links = soup.find_all('a', href=lambda x: x and 'video' in x.lower())
            meeting_count = len(meeting_links)

        elif platform == "granicus":
            # Granicus uses specific classes
            meeting_items = soup.find_all(class_=lambda x: x and 'meeting' in str(x).lower())
            meeting_count = len(meeting_items)

        elif platform == "youtube":
            # YouTube embeds
            meeting_count = len(soup.find_all('iframe', src=lambda x: x and 'youtube.com' in str(x)))

        else:
            # Generic: count video elements
            meeting_count = video_elements

        # Score based on meeting count
        if meeting_count >= 3:
            score += 15  # Has archive
        elif meeting_count >= 1:
            score += 8   # Limited archive

        # Check for recent content (dates within last 6 months)
        text_content = soup.get_text()
        current_year = datetime.now().year
        recent_months = ['january', 'february', 'march', 'april', 'may', 'june',
                        'july', 'august', 'september', 'october', 'november', 'december']

        # Look for current year and recent months
        if str(current_year) in text_content.lower():
            recent_month_found = any(month in text_content.lower() for month in recent_months[-6:])
            if recent_month_found:
                score += 15  # Recent content

    except Exception as e:
        log(f"  Warning: Could not parse HTML: {e}")
        return 0

    return score


def calculate_confidence(url, platform, notes):
    """
    Calculate overall confidence score.
    Score breakdown:
        - HTTP status (30 pts)
        - Content keywords (40 pts)
        - Archive depth (30 pts)
    Total: 100 pts
    """
    score = 0

    # Layer 1: HTTP Check (30 pts)
    status_code, is_live, content = check_http_status(url)

    if is_live:
        score += 30
        log(f"    HTTP: {status_code} ✓ (+30 pts)")
    else:
        log(f"    HTTP: Failed ✗ (0 pts)")
        return 0  # Dead link = automatic failure

    # Layer 2: Content Keywords (40 pts)
    keyword_score = score_content_keywords(content)
    score += keyword_score
    log(f"    Keywords: +{keyword_score} pts")

    # Layer 3: Archive Depth (30 pts)
    archive_score = estimate_archive_depth(content, platform)
    score += archive_score
    log(f"    Archive: +{archive_score} pts")

    return score


def validate_entry(row):
    """Validate a single CSV entry"""
    district_name = row.get("district_name", "Unknown")
    video_platform = row.get("video_platform", "")
    video_url = row.get("video_url", "")
    current_confidence = row.get("confidence", "")

    log(f"Validating: {district_name} ({video_platform})")

    # Skip entries without videos
    if video_platform in ["none_found", ""] or video_url == "":
        row["validation_score"] = 0
        row["validation_result"] = "skipped"
        row["validated_at"] = datetime.now().strftime("%Y-%m-%d")
        return row

    # Calculate confidence score
    score = calculate_confidence(video_url, video_platform, row.get("notes", ""))

    # Determine confidence level
    if score >= HIGH_THRESHOLD:
        new_confidence = "high"
        result = "HIGH"
    elif score >= MEDIUM_THRESHOLD:
        new_confidence = "medium"
        result = "MEDIUM"
    else:
        new_confidence = "low"
        result = "LOW"

    # Update row
    row["validation_score"] = score
    row["validation_result"] = result
    row["confidence"] = new_confidence
    row["validated_at"] = datetime.now().strftime("%Y-%m-%d")

    log(f"  Score: {score}/100 → {result}")

    # If confidence was downgraded, log warning
    if current_confidence == "high" and new_confidence != "high":
        log(f"  ⚠️  DOWNGRADED from HIGH to {new_confidence.upper()}")

    return row


def queue_for_agent(row):
    """Add low-confidence entry to agent review queue"""
    queue_exists = Path(QUEUE_FILE).exists()

    with open(QUEUE_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not queue_exists:
            writer.writeheader()
        writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Validation Pipeline for Texas School Districts")
    parser.add_argument("--batch", help="Batch range (e.g., 125-155)", type=str)
    parser.add_argument("--latest-batch", action="store_true", help="Validate last 30 districts")

    args = parser.parse_args()

    log("Starting Validation Pipeline")
    log(f"Thresholds: HIGH ≥{HIGH_THRESHOLD}, MEDIUM ≥{MEDIUM_THRESHOLD}")

    # Load entries
    with open(INPUT_FILE, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Filter by batch if specified
    if args.batch:
        parts = args.batch.split("-")
        if len(parts) == 2:
            batch_start = int(parts[0])
            batch_end = int(parts[1])
            rows = [r for r in rows if batch_start <= int(r.get("district_id", "0")[:6] or "0") <= batch_end]
            log(f"Processing batch: {len(rows)} districts")
    elif args.latest_batch:
        rows = rows[-30:]
        log(f"Processing latest batch: {len(rows)} districts")

    log(f"Total districts to validate: {len(rows)}")

    # Validate each entry
    validated_rows = []
    high_count = 0
    medium_count = 0
    low_count = 0
    skipped_count = 0

    for i, row in enumerate(rows):
        validated_row = validate_entry(row)
        validated_rows.append(validated_row)

        result = validated_row.get("validation_result", "skipped")
        if result == "HIGH":
            high_count += 1
        elif result == "MEDIUM":
            medium_count += 1
            queue_for_agent(validated_row)
        elif result == "LOW":
            low_count += 1
            queue_for_agent(validated_row)
        else:
            skipped_count += 1

        # Progress logging
        if (i + 1) % 10 == 0:
            log(f"Progress: {i+1}/{len(rows)} - HIGH: {high_count}, MED: {medium_count}, LOW: {low_count}")

        # Rate limiting
        time.sleep(DELAY_BETWEEN_REQUESTS)

    # Write output
    if validated_rows:
        fieldnames = list(validated_rows[0].keys())
        with open(OUTPUT_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(validated_rows)

    # Summary
    log(f"\n{'='*60}")
    log(f"Validation Complete!")
    log(f"  Total: {len(rows)}")
    log(f"  HIGH: {high_count} ({high_count/len(rows)*100:.1f}%)")
    log(f"  MEDIUM: {medium_count} ({medium_count/len(rows)*100:.1f}%)")
    log(f"  LOW: {low_count} ({low_count/len(rows)*100:.1f}%)")
    log(f"  Skipped: {skipped_count}")
    log(f"\n  Output: {OUTPUT_FILE}")
    log(f"  Agent Queue: {QUEUE_FILE} ({medium_count + low_count} entries)")
    log(f"{'='*60}\n")


if __name__ == "__main__":
    main()
