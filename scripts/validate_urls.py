#!/usr/bin/env python3
"""
URL Validation Script for Texas School Board Video Sources

Run this after the discovery phase to verify URLs are live.
"""

import csv
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time

INPUT_FILE = "district_video_sources.csv"
OUTPUT_FILE = "district_video_sources_validated.csv"
LOG_FILE = "validation_log.txt"

# Be respectful - don't hammer servers
REQUEST_TIMEOUT = 10
MAX_WORKERS = 5
DELAY_BETWEEN_REQUESTS = 0.5

def log(message):
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")

def check_url(url):
    """
    Check if URL is accessible.
    Returns (status_code, is_live, error_message)
    """
    if not url or url == "":
        return (None, False, "empty_url")
    
    try:
        response = requests.head(
            url, 
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (educational research project)"}
        )
        
        if response.status_code == 405:
            # Some servers don't allow HEAD, try GET
            response = requests.get(
                url, 
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (educational research project)"}
            )
        
        is_live = response.status_code < 400
        return (response.status_code, is_live, None)
    
    except requests.exceptions.Timeout:
        return (None, False, "timeout")
    except requests.exceptions.ConnectionError:
        return (None, False, "connection_error")
    except requests.exceptions.TooManyRedirects:
        return (None, False, "too_many_redirects")
    except Exception as e:
        return (None, False, str(e))

def validate_row(row):
    """Validate a single row's video URL"""
    district_name = row.get("district_name", "Unknown")
    video_url = row.get("video_url", "")
    
    time.sleep(DELAY_BETWEEN_REQUESTS)  # Rate limiting
    
    status_code, is_live, error = check_url(video_url)
    
    row["url_status_code"] = status_code
    row["url_is_live"] = is_live
    row["url_error"] = error
    row["validated_at"] = datetime.now().isoformat()
    
    return row

def main():
    log("Starting URL validation")
    
    # Read input
    with open(INPUT_FILE, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    log(f"Loaded {len(rows)} districts to validate")
    
    # Validate URLs
    validated_rows = []
    live_count = 0
    dead_count = 0
    skipped_count = 0
    
    for i, row in enumerate(rows):
        if row.get("video_platform") in ["none_found", "website_down", ""]:
            row["url_status_code"] = None
            row["url_is_live"] = None
            row["url_error"] = "skipped"
            row["validated_at"] = datetime.now().isoformat()
            skipped_count += 1
        else:
            row = validate_row(row)
            if row["url_is_live"]:
                live_count += 1
            else:
                dead_count += 1
        
        validated_rows.append(row)
        
        # Progress logging
        if (i + 1) % 50 == 0:
            log(f"Progress: {i + 1}/{len(rows)} validated. Live: {live_count}, Dead: {dead_count}, Skipped: {skipped_count}")
    
    # Write output
    if validated_rows:
        fieldnames = validated_rows[0].keys()
        with open(OUTPUT_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(validated_rows)
    
    # Final summary
    log(f"Validation complete!")
    log(f"  Total: {len(rows)}")
    log(f"  Live URLs: {live_count}")
    log(f"  Dead URLs: {dead_count}")
    log(f"  Skipped: {skipped_count}")
    log(f"Output written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
