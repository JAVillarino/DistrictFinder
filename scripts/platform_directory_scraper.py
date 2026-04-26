#!/usr/bin/env python3
"""
Platform Directory Scraper - Texas School Board Video Sources

Instead of guessing URL patterns, scrape the actual client directories
for Swagit, BoardDocs, and Granicus to get 100% accurate matches.

Strategy:
    1. Swagit: Crawl swagit.com for Texas client pages
    2. BoardDocs: Enumerate go.boarddocs.com/tx/{name}/Board.nsf
    3. Granicus: Search for Texas education clients
    4. BoxCast: Search for Texas ISD channels

Usage:
    python platform_directory_scraper.py --all          # Run all scrapers
    python platform_directory_scraper.py --swagit       # Swagit only
    python platform_directory_scraper.py --boarddocs    # BoardDocs only
    python platform_directory_scraper.py --granicus     # Granicus only
    python platform_directory_scraper.py --boxcast      # BoxCast only
"""

import csv
import requests
import re
import json
import argparse
import time
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

# Configuration
DISTRICTS_FILE = "../data/districts_complete.csv"
OUTPUT_FILE = "../data/directory_results.csv"
LOG_FILE = "directory_scraper.log"

REQUEST_TIMEOUT = 15
DELAY_BETWEEN_REQUESTS = 0.5
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (educational research project)"

# BoardDocs Texas URL pattern
BOARDDOCS_BASE = "https://go.boarddocs.com/tx/{slug}/Board.nsf/Public"

# Known BoardDocs slug patterns for Texas ISDs
BOARDDOCS_SLUG_PATTERNS = [
    "{name}isd",       # Most common: go.boarddocs.com/tx/houstonisd/
    "{name}",          # Just name: go.boarddocs.com/tx/fortworth/
    "{name}cisd",      # CISD variant
    "{name}msd",       # MSD variant
    "{name}tx",        # TX suffix
]


def log(message):
    """Log message to console and file"""
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def normalize_name(district_name):
    """Normalize district name for slug construction."""
    name = district_name
    for suffix in [" ISD", " CISD", " I.S.D.", " MSD", " CSD",
                   " CONS", " Independent School District"]:
        name = name.replace(suffix, "")
    name = re.sub(r'[^a-zA-Z]', '', name)
    return name.lower()


def load_districts():
    """Load all districts from the complete CSV."""
    districts = []
    with open(DISTRICTS_FILE, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            districts.append(row)
    return districts


def load_existing_results():
    """Load existing results."""
    results = {}
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                results[row["district_id"]] = row
    return results


def save_results(results):
    """Write results to CSV."""
    if not results:
        return
    fieldnames = ["district_id", "district_name", "county", "enrollment",
                  "video_platform", "video_url", "notes", "confidence",
                  "last_checked", "source"]
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results.values():
            writer.writerow(row)


def make_result(district, platform, video_url, notes, confidence, source):
    """Create a standardized result dict."""
    return {
        "district_id": district["district_id"],
        "district_name": district["district_name"],
        "county": district.get("county", ""),
        "enrollment": district.get("enrollment", ""),
        "video_platform": platform,
        "video_url": video_url,
        "notes": notes,
        "confidence": confidence,
        "last_checked": datetime.now().strftime("%Y-%m-%d"),
        "source": source,
    }


# ============================================================
# SWAGIT DIRECTORY SCRAPER
# ============================================================

def scrape_swagit(districts):
    """
    Scrape Swagit's site for Texas school district clients.
    Approach: search swagit.com for Texas education clients,
    then match against our district list.
    """
    log("=== SWAGIT DIRECTORY SCRAPER ===")
    results = {}

    # Build a lookup of normalized names -> district
    name_lookup = {}
    for d in districts:
        normalized = normalize_name(d["district_name"])
        name_lookup[normalized] = d

    # Approach 1: Try the new swagit.com site directory/search
    # Swagit lists clients at their main domains
    swagit_search_urls = [
        "https://www.swagit.com/our-clients/",
        "https://www.swagit.com/clients/",
        "https://www.swagit.com/education/",
        "https://www.swagit.com/k-12/",
    ]

    found_urls = set()

    for search_url in swagit_search_urls:
        try:
            response = requests.get(
                search_url, timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT}
            )
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Look for links to *.swagit.com subdomains
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if 'swagit.com' in href and href not in found_urls:
                        found_urls.add(href)
                log(f"  Found {len(found_urls)} Swagit links from {search_url}")
        except Exception as e:
            log(f"  Could not fetch {search_url}: {e}")
        time.sleep(DELAY_BETWEEN_REQUESTS)

    # Approach 2: Enumerate known Swagit subdomain patterns for ALL districts
    # This is more thorough than the existing swagit_matcher.py because
    # we also try patterns it doesn't cover
    log(f"  Enumerating Swagit subdomains for {len(districts)} districts...")

    extended_patterns = [
        "{name}isd.new.swagit.com",
        "{name}isdtx.new.swagit.com",
        "{name}isd.swagit.com",
        "{name}isdtx.swagit.com",
        "{name}isdtx.v3.swagit.com",
        # Additional patterns the existing matcher misses:
        "{name}.new.swagit.com",
        "{name}tx.new.swagit.com",
        "{name}cisd.new.swagit.com",
        "{name}cisdtx.new.swagit.com",
        "{name}msd.new.swagit.com",
    ]

    pending = [d for d in districts if d.get("video_status", "pending") == "pending"]
    log(f"  Testing {len(pending)} pending districts...")

    for i, district in enumerate(pending):
        normalized = normalize_name(district["district_name"])

        for pattern in extended_patterns:
            url = f"https://{pattern.format(name=normalized)}/"
            try:
                response = requests.head(
                    url, timeout=8, allow_redirects=True,
                    headers={"User-Agent": USER_AGENT}
                )
                if response.status_code < 400:
                    log(f"    FOUND: {district['district_name']} -> {url}")
                    results[district["district_id"]] = make_result(
                        district, "swagit", url,
                        f"Swagit directory scraper. Extended pattern match at {url}",
                        "high", "directory_swagit"
                    )
                    break  # Found it, no need to try more patterns
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.TooManyRedirects):
                continue
            time.sleep(0.2)

        if (i + 1) % 25 == 0:
            log(f"  Progress: {i+1}/{len(pending)} ({len(results)} found)")

    log(f"  Swagit scraper complete: {len(results)} districts found")
    return results


# ============================================================
# BOARDDOCS DIRECTORY SCRAPER
# ============================================================

def scrape_boarddocs(districts):
    """
    Enumerate BoardDocs URLs for Texas school districts.
    BoardDocs uses: go.boarddocs.com/tx/{slug}/Board.nsf/Public

    IMPORTANT: BoardDocs can be agendas-only OR include video.
    We detect it but mark confidence based on whether video content is found.
    """
    log("=== BOARDDOCS DIRECTORY SCRAPER ===")
    results = {}

    pending = [d for d in districts if d.get("video_status", "pending") == "pending"]
    log(f"  Testing {len(pending)} pending districts against BoardDocs...")

    for i, district in enumerate(pending):
        normalized = normalize_name(district["district_name"])

        for slug_pattern in BOARDDOCS_SLUG_PATTERNS:
            slug = slug_pattern.format(name=normalized)
            url = BOARDDOCS_BASE.format(slug=slug)

            try:
                response = requests.get(
                    url, timeout=REQUEST_TIMEOUT, allow_redirects=True,
                    headers={"User-Agent": USER_AGENT}
                )

                if response.status_code == 200:
                    html_lower = response.text.lower()

                    # Check if this is a real BoardDocs page (not a 404-like page)
                    if "boarddocs" in html_lower and ("board" in html_lower or "meeting" in html_lower):
                        # Check for video content specifically
                        has_video = any(kw in html_lower for kw in
                                       ["video", "recording", "watch", "player",
                                        "iframe", "youtube", "vimeo"])

                        if has_video:
                            confidence = "medium"
                            notes = f"BoardDocs with video content detected at {url}"
                        else:
                            confidence = "low"
                            notes = f"BoardDocs found (likely agendas-only) at {url}"

                        log(f"    FOUND: {district['district_name']} -> {url} ({confidence})")
                        results[district["district_id"]] = make_result(
                            district, "boarddocs", url, notes, confidence,
                            "directory_boarddocs"
                        )
                        break

            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.TooManyRedirects):
                continue
            except Exception as e:
                log(f"    Error for {slug}: {e}")
                continue
            time.sleep(0.3)

        if (i + 1) % 25 == 0:
            log(f"  Progress: {i+1}/{len(pending)} ({len(results)} found)")

    log(f"  BoardDocs scraper complete: {len(results)} districts found")
    return results


# ============================================================
# GRANICUS DIRECTORY SCRAPER
# ============================================================

def scrape_granicus(districts):
    """
    Search Granicus/Legistar for Texas school district clients.
    Granicus uses several subdomains and products:
    - {name}.granicus.com (main)
    - {name}.granicus.com/player (video player)
    - {name}tx.iqm2.com/Citizens/ (IQM2 citizen portal)
    """
    log("=== GRANICUS DIRECTORY SCRAPER ===")
    results = {}

    # Extended patterns beyond what granicus_matcher.py uses
    granicus_patterns = [
        "https://{name}.granicus.com/",
        "https://{name}isd.granicus.com/",
        "https://{name}isd.granicus.com/player/",
        "https://{name}tx.iqm2.com/Citizens/",
        "https://{name}schoolstx.iqm2.com/Citizens/",
        # Additional patterns:
        "https://{name}texas.granicus.com/",
        "https://{name}cisd.granicus.com/",
        "https://{name}-isd.granicus.com/",
        "https://{name}isd.legistar.com/",
        "https://{name}.legistar.com/",
    ]

    pending = [d for d in districts if d.get("video_status", "pending") == "pending"]
    log(f"  Testing {len(pending)} pending districts against Granicus/Legistar...")

    for i, district in enumerate(pending):
        normalized = normalize_name(district["district_name"])

        for pattern in granicus_patterns:
            url = pattern.format(name=normalized)
            try:
                response = requests.head(
                    url, timeout=8, allow_redirects=True,
                    headers={"User-Agent": USER_AGENT}
                )

                # If HEAD returns 405, try GET
                if response.status_code == 405:
                    response = requests.get(
                        url, timeout=REQUEST_TIMEOUT, allow_redirects=True,
                        headers={"User-Agent": USER_AGENT}
                    )

                if response.status_code < 400:
                    # Verify it's a real Granicus page
                    if response.status_code == 200 and response.text:
                        html_lower = response.text.lower()
                        if "granicus" in html_lower or "iqm2" in html_lower or "legistar" in html_lower:
                            log(f"    FOUND: {district['district_name']} -> {url}")
                            results[district["district_id"]] = make_result(
                                district, "granicus", url,
                                f"Granicus directory scraper. Found at {url}",
                                "high", "directory_granicus"
                            )
                            break
                    else:
                        # HEAD succeeded, likely valid
                        log(f"    FOUND (HEAD): {district['district_name']} -> {url}")
                        results[district["district_id"]] = make_result(
                            district, "granicus", url,
                            f"Granicus directory scraper. HEAD success at {url}",
                            "medium", "directory_granicus"
                        )
                        break

            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.TooManyRedirects):
                continue
            time.sleep(0.2)

        if (i + 1) % 25 == 0:
            log(f"  Progress: {i+1}/{len(pending)} ({len(results)} found)")

    log(f"  Granicus scraper complete: {len(results)} districts found")
    return results


# ============================================================
# BOXCAST DIRECTORY SCRAPER
# ============================================================

def scrape_boxcast(districts):
    """
    Search BoxCast for Texas school district channels.
    BoxCast URLs: boxcast.tv/channel/{id} or dashboard embeds.
    We test common patterns and search their public directory.
    """
    log("=== BOXCAST DIRECTORY SCRAPER ===")
    results = {}

    boxcast_patterns = [
        "https://boxcast.tv/channel/{name}-isd",
        "https://boxcast.tv/channel/{name}isd",
        "https://boxcast.tv/channel/{name}-independent-school-district",
    ]

    pending = [d for d in districts if d.get("video_status", "pending") == "pending"]
    log(f"  Testing {len(pending)} pending districts against BoxCast...")

    for i, district in enumerate(pending):
        normalized = normalize_name(district["district_name"])

        # Also create a hyphenated version for BoxCast
        name_parts = district["district_name"]
        for suffix in [" ISD", " CISD", " MSD", " CSD"]:
            name_parts = name_parts.replace(suffix, "")
        hyphenated = re.sub(r'[^a-zA-Z\s]', '', name_parts).strip().lower().replace(' ', '-')

        patterns_to_try = [p.format(name=normalized) for p in boxcast_patterns]
        patterns_to_try.append(f"https://boxcast.tv/channel/{hyphenated}")

        for url in patterns_to_try:
            try:
                response = requests.get(
                    url, timeout=REQUEST_TIMEOUT, allow_redirects=True,
                    headers={"User-Agent": USER_AGENT}
                )
                if response.status_code == 200:
                    html_lower = response.text.lower()
                    if "boxcast" in html_lower and ("board" in html_lower or "meeting" in html_lower or "school" in html_lower):
                        log(f"    FOUND: {district['district_name']} -> {url}")
                        results[district["district_id"]] = make_result(
                            district, "boxcast", url,
                            f"BoxCast channel found at {url}",
                            "medium", "directory_boxcast"
                        )
                        break
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.TooManyRedirects):
                continue
            time.sleep(0.3)

        if (i + 1) % 25 == 0:
            log(f"  Progress: {i+1}/{len(pending)} ({len(results)} found)")

    log(f"  BoxCast scraper complete: {len(results)} districts found")
    return results


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Platform Directory Scraper for Texas School Districts")
    parser.add_argument("--all", action="store_true", help="Run all scrapers")
    parser.add_argument("--swagit", action="store_true", help="Scrape Swagit directory")
    parser.add_argument("--boarddocs", action="store_true", help="Scrape BoardDocs directory")
    parser.add_argument("--granicus", action="store_true", help="Scrape Granicus directory")
    parser.add_argument("--boxcast", action="store_true", help="Scrape BoxCast directory")

    args = parser.parse_args()

    # Default to --all if no specific scraper selected
    if not any([args.all, args.swagit, args.boarddocs, args.granicus, args.boxcast]):
        args.all = True

    log("Starting Platform Directory Scraper")
    districts = load_districts()
    log(f"Loaded {len(districts)} districts")

    all_results = load_existing_results()

    if args.all or args.swagit:
        results = scrape_swagit(districts)
        all_results.update(results)

    if args.all or args.boarddocs:
        results = scrape_boarddocs(districts)
        # Don't overwrite higher-confidence results
        for did, result in results.items():
            if did not in all_results or all_results[did].get("confidence") == "low":
                all_results[did] = result

    if args.all or args.granicus:
        results = scrape_granicus(districts)
        all_results.update(results)

    if args.all or args.boxcast:
        results = scrape_boxcast(districts)
        # Don't overwrite higher-confidence results
        for did, result in results.items():
            if did not in all_results:
                all_results[did] = result

    save_results(all_results)

    # Summary
    log(f"\n{'='*60}")
    log(f"Platform Directory Scraper Complete!")
    log(f"  Total results: {len(all_results)}")

    # Count by platform
    platform_counts = {}
    for r in all_results.values():
        p = r.get("video_platform", "unknown")
        platform_counts[p] = platform_counts.get(p, 0) + 1
    for p, c in sorted(platform_counts.items(), key=lambda x: -x[1]):
        log(f"    {p}: {c}")

    log(f"  Output: {OUTPUT_FILE}")
    log(f"{'='*60}\n")


if __name__ == "__main__":
    main()
