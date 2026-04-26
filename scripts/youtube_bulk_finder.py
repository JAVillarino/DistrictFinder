#!/usr/bin/env python3
"""
YouTube Bulk Finder - Texas School Board Video Sources

Uses YouTube Data API v3 to find district channels.
Handles 10-15% of districts and fixes missing channel URLs.

Setup:
    1. Get API key from console.cloud.google.com
    2. Create config.json with: {"youtube_api_key": "YOUR_KEY"}
    3. Install: pip install google-api-python-client

Usage:
    python youtube_bulk_finder.py --batch 125-155 --limit 30
    python youtube_bulk_finder.py --missing  # Fix 10 known missing channels
"""

import csv
import json
import argparse
import re
from datetime import datetime
from pathlib import Path

# Configuration
INPUT_FILE = "../data/districts_input.csv"
OUTPUT_FILE = "../data/districts_output.csv"
CONFIG_FILE = "config.json"
PROGRESS_FILE = "youtube_progress.json"
LOG_FILE = "youtube_finder.log"

# API quota limits (free tier)
DAILY_QUOTA_LIMIT = 10000
SEARCH_COST = 100  # Each search costs 100 units
MAX_DAILY_SEARCHES = 95  # Leave margin

# Districts with confirmed YouTube but missing channel URLs
MISSING_CHANNELS = [
    "Conroe ISD",
    "Midland ISD",
    "Southwest ISD",
    "Harlandale ISD",
    "Schertz-Cibolo-Universal City ISD",
    "Edgewood ISD",
    "United ISD",
    "La Porte ISD",
    "Canutillo ISD",
    "Princeton ISD"
]


def log(message):
    """Log message to console and file"""
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def load_config():
    """Load configuration from config.json"""
    if not Path(CONFIG_FILE).exists():
        log(f"ERROR: {CONFIG_FILE} not found!")
        log("Please create config.json with: {\"youtube_api_key\": \"YOUR_KEY\"}")
        log("Get your key from: https://console.cloud.google.com")
        return None

    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    if "youtube_api_key" not in config:
        log("ERROR: youtube_api_key not found in config.json")
        return None

    return config


def load_progress():
    """Load progress from JSON file"""
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {
        "processed_ids": [],
        "quota_used_today": 0,
        "last_reset_date": datetime.now().strftime("%Y-%m-%d")
    }


def save_progress(progress):
    """Save progress to JSON file"""
    # Reset quota if new day
    today = datetime.now().strftime("%Y-%m-%d")
    if progress["last_reset_date"] != today:
        progress["quota_used_today"] = 0
        progress["last_reset_date"] = today

    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def check_quota(progress):
    """Check if we're within API quota limits"""
    if progress["quota_used_today"] >= (MAX_DAILY_SEARCHES * SEARCH_COST):
        log(f"⚠️  Daily quota limit reached ({progress['quota_used_today']}/{DAILY_QUOTA_LIMIT})")
        log(f"Quota will reset at midnight. Resume tomorrow.")
        return False
    return True


def search_youtube_channel(api_key, district_name):
    """
    Search for a district's YouTube channel using the API.
    Returns (channel_id, channel_handle, subscriber_count) or (None, None, None)
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError:
        log("ERROR: google-api-python-client not installed")
        log("Install with: pip install google-api-python-client")
        return (None, None, None)

    youtube = build('youtube', 'v3', developerKey=api_key)

    # Try multiple search queries
    queries = [
        f"{district_name} board meeting",
        f"{district_name} board of trustees",
        f"{district_name} ISD meetings"
    ]

    for query in queries:
        try:
            # Search for channels
            search_response = youtube.search().list(
                q=query,
                type="channel",
                part="snippet",
                maxResults=5,
                relevanceLanguage="en",
                regionCode="US"
            ).execute()

            # Check results
            for item in search_response.get("items", []):
                channel_title = item["snippet"]["title"]
                channel_id = item["snippet"]["channelId"]

                # Verify channel name matches district
                if is_channel_match(district_name, channel_title):
                    # Get channel details
                    channel_response = youtube.channels().list(
                        part="snippet,statistics,contentDetails",
                        id=channel_id
                    ).execute()

                    if channel_response["items"]:
                        channel = channel_response["items"][0]
                        stats = channel.get("statistics", {})
                        custom_url = channel["snippet"].get("customUrl", "")

                        # Extract handle from customUrl
                        handle = extract_handle(custom_url, channel_id)

                        # Verify channel has uploads
                        video_count = int(stats.get("videoCount", 0))
                        if video_count > 0:
                            # Additional verification: check recent uploads
                            if verify_recent_uploads(youtube, channel_id, district_name):
                                subscriber_count = int(stats.get("subscriberCount", 0))
                                log(f"  ✓ Found: {channel_title} ({handle}) - {subscriber_count:,} subscribers, {video_count} videos")
                                return (channel_id, handle, subscriber_count)

        except HttpError as e:
            if e.resp.status == 403:
                log(f"  ⚠️  Quota exceeded: {e}")
                return (None, None, None)
            log(f"  Error searching '{query}': {e}")
            continue
        except Exception as e:
            log(f"  Error: {e}")
            continue

    return (None, None, None)


def is_channel_match(district_name, channel_title):
    """Check if channel title matches district name"""
    # Normalize both names
    district_normalized = re.sub(r'[^a-z]', '', district_name.lower())
    channel_normalized = re.sub(r'[^a-z]', '', channel_title.lower())

    # Check if district name is in channel title
    if district_normalized in channel_normalized:
        return True

    # Check key terms
    district_words = district_name.lower().split()
    channel_words = channel_title.lower().split()

    # At least 2 words should match
    matches = sum(1 for word in district_words if word in channel_words and len(word) > 3)
    return matches >= 2


def extract_handle(custom_url, channel_id):
    """Extract @handle or format channel ID"""
    if custom_url:
        if custom_url.startswith("@"):
            return custom_url
        elif custom_url.startswith("/"):
            return f"@{custom_url[1:]}"
        else:
            return f"@{custom_url}"
    return f"channel/{channel_id}"


def verify_recent_uploads(youtube, channel_id, district_name):
    """Verify channel has recent uploads with board meeting content"""
    try:
        # Get recent uploads
        search_response = youtube.search().list(
            channelId=channel_id,
            type="video",
            part="snippet",
            maxResults=10,
            order="date"
        ).execute()

        # Check if any videos mention board meetings
        for item in search_response.get("items", []):
            title = item["snippet"]["title"].lower()
            description = item["snippet"]["description"].lower()

            if any(keyword in title or keyword in description
                   for keyword in ["board", "meeting", "trustees", "regular meeting", "special meeting"]):
                return True

    except Exception as e:
        log(f"  Warning: Could not verify uploads: {e}")

    return False


def load_existing_csv():
    """Load existing district_video_sources.csv entries"""
    existing = {}
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing[row["district_id"]] = row
    return existing


def update_csv_entry(district_id, channel_id, channel_handle):
    """Update existing CSV entry with YouTube channel info"""
    existing = load_existing_csv()

    if district_id in existing:
        entry = existing[district_id]
        entry["video_platform"] = "youtube"
        entry["video_url"] = f"https://www.youtube.com/{channel_handle}"
        entry["youtube_channel_id"] = channel_handle
        entry["confidence"] = "high"
        entry["notes"] = f"YouTube channel found via API: {channel_handle}. {entry.get('notes', '')}"
        entry["last_checked"] = datetime.now().strftime("%Y-%m-%d")

        # Write back
        fieldnames = list(entry.keys())
        with open(OUTPUT_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(existing.values())

        log(f"  Updated CSV entry for {district_id}")


def process_missing_channels(config, progress):
    """Process the 10 known districts with missing YouTube channels"""
    api_key = config["youtube_api_key"]

    log(f"Processing {len(MISSING_CHANNELS)} districts with missing YouTube channels")
    log(f"Current quota used: {progress['quota_used_today']}/{DAILY_QUOTA_LIMIT}")

    found_count = 0
    not_found_count = 0

    # Load existing CSV to get district IDs
    existing = load_existing_csv()

    for district_name in MISSING_CHANNELS:
        if not check_quota(progress):
            break

        log(f"Searching for: {district_name}")

        # Find district ID
        district_id = None
        for did, entry in existing.items():
            if entry["district_name"] == district_name:
                district_id = did
                break

        if not district_id:
            log(f"  ⚠️  District ID not found in CSV")
            continue

        # Search YouTube
        channel_id, channel_handle, subscribers = search_youtube_channel(api_key, district_name)

        # Update quota
        progress["quota_used_today"] += SEARCH_COST * 3  # 3 queries per district max
        save_progress(progress)

        if channel_id:
            update_csv_entry(district_id, channel_id, channel_handle)
            found_count += 1
        else:
            log(f"  ✗ Channel not found")
            not_found_count += 1

    log(f"\nSummary: Found {found_count}/{len(MISSING_CHANNELS)} channels")
    log(f"Quota used: {progress['quota_used_today']}/{DAILY_QUOTA_LIMIT}")


def main():
    parser = argparse.ArgumentParser(description="YouTube Bulk Finder for Texas School Districts")
    parser.add_argument("--missing", action="store_true", help="Process 10 known missing channels")
    parser.add_argument("--batch", help="Batch range (e.g., 125-155)", type=str)
    parser.add_argument("--limit", help="Max districts to process (quota management)", type=int, default=30)

    args = parser.parse_args()

    # Load config
    config = load_config()
    if not config:
        return

    # Load progress
    progress = load_progress()

    # Check quota
    if not check_quota(progress):
        return

    log("Starting YouTube Bulk Finder")
    log(f"API quota: {progress['quota_used_today']}/{DAILY_QUOTA_LIMIT} used today")

    if args.missing:
        process_missing_channels(config, progress)
    else:
        log("Note: Batch processing not yet implemented. Use --missing for now.")
        log("This will be added in Phase 2 after testing on missing channels.")


if __name__ == "__main__":
    main()
