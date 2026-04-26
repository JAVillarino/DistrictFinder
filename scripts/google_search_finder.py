#!/usr/bin/env python3
"""
Google Search Finder - Texas School Board Video Sources

Uses Google Custom Search API to find board meeting video sources
for districts that the pattern matchers and crawler couldn't resolve.

More flexible than platform-specific searches — catches custom websites,
regional media hosts, Facebook Live archives, and uncommon platforms.

Setup:
    1. Create a Custom Search Engine at https://programmablesearchengine.google.com/
       - Search the entire web (or restrict to video/education sites)
       - Get the Search Engine ID (cx)
    2. Get API key from https://console.cloud.google.com
       - Enable "Custom Search API"
    3. Add to config.json:
       {
           "google_api_key": "YOUR_KEY",
           "google_cx": "YOUR_SEARCH_ENGINE_ID"
       }

Quota: 100 free queries/day, $5 per 1000 queries after that.

Usage:
    python google_search_finder.py                    # Process pending
    python google_search_finder.py --batch 1-50       # Batch mode
    python google_search_finder.py --resume           # Resume
    python google_search_finder.py --district 101912  # Single district
    python google_search_finder.py --limit 50         # Max districts
    python google_search_finder.py --no-api           # Fallback: requests-based search (no API key needed)
"""

import csv
import requests
import re
import json
import argparse
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from bs4 import BeautifulSoup

# Configuration
INPUT_FILE = "../data/districts_complete.csv"
OUTPUT_FILE = "../data/search_results.csv"
CONFIG_FILE = "config.json"
PROGRESS_FILE = "search_progress.json"
LOG_FILE = "google_search.log"

REQUEST_TIMEOUT = 12
DELAY_BETWEEN_REQUESTS = 1.0  # Respectful rate limiting for Google
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (educational research project)"

# Google Custom Search API
GOOGLE_API_URL = "https://www.googleapis.com/customsearch/v1"
DAILY_QUOTA = 100  # Free tier

# Search query templates (ordered by specificity)
SEARCH_QUERIES = [
    '"{district_name}" "board meeting" (video OR recording OR livestream OR archive)',
    '"{district_name}" "board of trustees" (video OR youtube OR swagit OR granicus)',
    '"{district_name}" Texas school board meeting video',
]

# Fallback queries for non-API mode
FALLBACK_QUERIES = [
    'site:youtube.com "{district_name}" board meeting',
    'site:swagit.com "{district_name}"',
    'site:granicus.com "{district_name}"',
    'site:boxcast.tv "{district_name}"',
    '"{district_name}" board meeting video archive',
]

# Platform detection from URLs
URL_PLATFORM_MAP = {
    "swagit.com": "swagit",
    "granicus.com": "granicus",
    "iqm2.com": "granicus",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "boarddocs.com": "boarddocs",
    "boardbook.org": "boardbook",
    "boxcast.tv": "boxcast",
    "boxcast.com": "boxcast",
    "vimeo.com": "vimeo",
    "facebook.com": "facebook_live",
    "zoom.us": "zoom",
    "panopto.com": "panopto",
    "diligent.com": "diligent",
    "citizenportal.ai": "citizenportal",
    "livestream.com": "livestream",
}

# Domains to skip (not useful results)
SKIP_DOMAINS = [
    "indeed.com", "glassdoor.com", "salary.com", "ziprecruiter.com",
    "linkedin.com", "twitter.com", "instagram.com", "tiktok.com",
    "wikipedia.org", "yelp.com", "niche.com", "greatschools.org",
    "usnews.com", "realtor.com", "zillow.com", "trulia.com",
    "pinterest.com", "reddit.com",
]


def log(message):
    """Log message to console and file"""
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def load_config():
    """Load configuration from config.json."""
    if not Path(CONFIG_FILE).exists():
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def load_progress():
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {
        "processed_ids": [],
        "quota_used_today": 0,
        "last_reset_date": datetime.now().strftime("%Y-%m-%d"),
        "stats": {"found": 0, "not_found": 0},
    }


def save_progress(progress):
    today = datetime.now().strftime("%Y-%m-%d")
    if progress["last_reset_date"] != today:
        progress["quota_used_today"] = 0
        progress["last_reset_date"] = today
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def load_results():
    results = {}
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                results[row["district_id"]] = row
    return results


def save_results(results):
    if not results:
        return
    fieldnames = ["district_id", "district_name", "county", "enrollment",
                  "video_platform", "video_url", "youtube_channel_id",
                  "notes", "confidence", "last_checked", "source",
                  "search_query", "result_rank"]
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results.values():
            writer.writerow(row)


def detect_platform_from_url(url):
    """Identify platform from a URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    for pattern, platform in URL_PLATFORM_MAP.items():
        if pattern in domain:
            return platform
    return None


def is_relevant_result(url, title, snippet, district_name):
    """Filter out irrelevant search results."""
    domain = urlparse(url).netloc.lower()

    # Skip known irrelevant domains
    for skip in SKIP_DOMAINS:
        if skip in domain:
            return False

    # Check if result mentions the district
    text = (title + " " + snippet).lower()
    name_parts = district_name.lower().replace(" isd", "").replace(" cisd", "").split()
    # At least one significant word from district name should appear
    if not any(part in text for part in name_parts if len(part) > 3):
        return False

    # Check for video/meeting relevance
    video_terms = ["video", "meeting", "board", "recording", "livestream",
                   "live stream", "archive", "watch", "broadcast", "stream"]
    if any(term in text for term in video_terms):
        return True

    # Known video platforms are always relevant
    if detect_platform_from_url(url):
        return True

    return False


def extract_youtube_handle(url):
    """Extract YouTube channel handle from a URL."""
    match = re.search(r'youtube\.com/(@[a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    match = re.search(r'youtube\.com/channel/(UC[a-zA-Z0-9_-]+)', url)
    if match:
        return f"channel/{match.group(1)}"
    match = re.search(r'youtube\.com/c/([a-zA-Z0-9_-]+)', url)
    if match:
        return f"@{match.group(1)}"
    return None


# ============================================================
# GOOGLE CUSTOM SEARCH API
# ============================================================

def google_api_search(query, api_key, cx):
    """
    Search using Google Custom Search API.
    Returns list of {url, title, snippet} dicts.
    """
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": 10,
    }

    try:
        response = requests.get(GOOGLE_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data.get("items", []):
                results.append({
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                })
            return results
        elif response.status_code == 429:
            log("    API quota exceeded")
            return None
        else:
            log(f"    API error: {response.status_code}")
            return []
    except Exception as e:
        log(f"    API error: {e}")
        return []


# ============================================================
# FALLBACK: DuckDuckGo HTML search (no API key needed)
# ============================================================

def duckduckgo_search(query):
    """
    Fallback search using DuckDuckGo HTML.
    Returns list of {url, title, snippet} dicts.
    """
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    try:
        response = requests.get(
            search_url, timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT}
        )
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        results = []

        for result in soup.find_all('div', class_='result'):
            link_tag = result.find('a', class_='result__a')
            snippet_tag = result.find('a', class_='result__snippet')

            if link_tag:
                url = link_tag.get('href', '')
                # DuckDuckGo wraps URLs in a redirect — extract the real URL
                if 'uddg=' in url:
                    match = re.search(r'uddg=([^&]+)', url)
                    if match:
                        from urllib.parse import unquote
                        url = unquote(match.group(1))

                title = link_tag.get_text(strip=True)
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                if url and url.startswith('http'):
                    results.append({
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                    })

        return results

    except Exception as e:
        log(f"    DuckDuckGo error: {e}")
        return []


# ============================================================
# PROCESS DISTRICT
# ============================================================

def process_district(district, config, use_api=True, progress=None):
    """
    Search for a district's video sources using Google/DuckDuckGo.
    Returns result dict or None.
    """
    district_name = district["district_name"]
    best_result = None
    best_score = 0

    queries = SEARCH_QUERIES if use_api else FALLBACK_QUERIES

    for qi, query_template in enumerate(queries):
        query = query_template.format(district_name=district_name)
        log(f"    Query {qi+1}: {query[:80]}...")

        # Search
        if use_api:
            api_key = config.get("google_api_key")
            cx = config.get("google_cx")
            search_results = google_api_search(query, api_key, cx)
            if progress:
                progress["quota_used_today"] += 1
        else:
            search_results = duckduckgo_search(query)

        if search_results is None:
            # Quota exceeded
            return None

        if not search_results:
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        # Score results
        for rank, sr in enumerate(search_results):
            url = sr["url"]
            title = sr["title"]
            snippet = sr["snippet"]

            if not is_relevant_result(url, title, snippet, district_name):
                continue

            platform = detect_platform_from_url(url)
            score = 0

            # Known platform (40 pts)
            if platform:
                score += 40
                # High-value platforms
                if platform in ("swagit", "granicus", "youtube"):
                    score += 15

            # Rank bonus (top results more relevant)
            score += max(0, 20 - rank * 3)

            # Video keywords in title/snippet (20 pts)
            text = (title + " " + snippet).lower()
            if any(kw in text for kw in ["video", "recording", "livestream", "watch", "archive"]):
                score += 20

            # Meeting keywords (10 pts)
            if any(kw in text for kw in ["board meeting", "trustees", "school board"]):
                score += 10

            if score > best_score:
                best_score = score
                yt_handle = extract_youtube_handle(url) if platform == "youtube" else ""

                best_result = {
                    "district_id": district["district_id"],
                    "district_name": district_name,
                    "county": district.get("county", ""),
                    "enrollment": district.get("enrollment", ""),
                    "video_platform": platform or "website_archive",
                    "video_url": url,
                    "youtube_channel_id": yt_handle,
                    "notes": f"Google search found: {title[:100]}. Query: {query[:60]}",
                    "confidence": "high" if best_score >= 70 else "medium" if best_score >= 40 else "low",
                    "last_checked": datetime.now().strftime("%Y-%m-%d"),
                    "source": "google_api" if use_api else "duckduckgo",
                    "search_query": query[:100],
                    "result_rank": rank + 1,
                }

        # If we found a high-confidence result, no need for more queries
        if best_score >= 70:
            break

        time.sleep(DELAY_BETWEEN_REQUESTS)

    if best_result:
        log(f"    FOUND: {best_result['video_platform']} at {best_result['video_url']} "
            f"(score: {best_score}, confidence: {best_result['confidence']})")
    else:
        log(f"    No video sources found")

    return best_result


# ============================================================
# MAIN
# ============================================================

def process_districts(batch_start=None, batch_end=None, resume=False,
                      single_id=None, limit=None, use_api=True):
    """Process districts."""
    config = load_config()
    progress = load_progress() if resume else {
        "processed_ids": [], "quota_used_today": 0,
        "last_reset_date": datetime.now().strftime("%Y-%m-%d"),
        "stats": {"found": 0, "not_found": 0},
    }
    results = load_results()

    # Check API config
    if use_api:
        if not config.get("google_api_key") or not config.get("google_cx"):
            log("WARNING: google_api_key or google_cx not in config.json")
            log("Falling back to DuckDuckGo search (no API key needed)")
            log("For better results, set up Google Custom Search API.")
            use_api = False

    # Load input
    with open(INPUT_FILE, "r") as f:
        reader = csv.DictReader(f)
        districts = list(reader)

    # Filter
    if single_id:
        districts = [d for d in districts if d["district_id"] == single_id]
    else:
        districts = [d for d in districts if d.get("video_status", "pending") == "pending"]

    if batch_start is not None and batch_end is not None:
        start_idx = batch_start - 1
        end_idx = batch_end
        districts = districts[start_idx:end_idx]

    if resume:
        districts = [d for d in districts if d["district_id"] not in progress["processed_ids"]]

    if limit:
        districts = districts[:limit]

    log(f"Processing {len(districts)} districts (mode: {'Google API' if use_api else 'DuckDuckGo'})")

    if use_api:
        remaining_quota = DAILY_QUOTA - progress["quota_used_today"]
        # Each district uses up to 3 queries
        max_districts = remaining_quota // 3
        if len(districts) > max_districts:
            log(f"WARNING: Only enough quota for ~{max_districts} districts today")
            districts = districts[:max_districts]

    found_count = progress["stats"]["found"]
    not_found_count = progress["stats"]["not_found"]

    for i, district in enumerate(districts):
        log(f"[{i+1}/{len(districts)}] {district['district_name']} ({district['district_id']})")

        result = process_district(district, config, use_api, progress)

        if result:
            results[district["district_id"]] = result
            found_count += 1
        else:
            not_found_count += 1

        progress["processed_ids"].append(district["district_id"])
        progress["stats"]["found"] = found_count
        progress["stats"]["not_found"] = not_found_count

        if (i + 1) % 10 == 0:
            save_progress(progress)
            save_results(results)
            log(f"Checkpoint: {i+1}/{len(districts)} (Found: {found_count}, Not found: {not_found_count})")

        time.sleep(DELAY_BETWEEN_REQUESTS)

    save_progress(progress)
    save_results(results)

    total = found_count + not_found_count
    log(f"\n{'='*60}")
    log(f"Google Search Finder Complete!")
    log(f"  Total processed: {total}")
    if total > 0:
        log(f"  Found: {found_count} ({found_count/total*100:.1f}%)")
    log(f"  Not found: {not_found_count}")
    if use_api:
        log(f"  API quota used today: {progress['quota_used_today']}/{DAILY_QUOTA}")
    log(f"  Results: {OUTPUT_FILE}")
    log(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Google Search Finder for Texas School Districts")
    parser.add_argument("--batch", help="Batch range (e.g., 1-50)", type=str)
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--district", help="Single district ID", type=str)
    parser.add_argument("--limit", help="Max districts to process", type=int)
    parser.add_argument("--no-api", action="store_true",
                        help="Use DuckDuckGo instead of Google API (no key needed)")

    args = parser.parse_args()

    batch_start = None
    batch_end = None
    if args.batch:
        parts = args.batch.split("-")
        if len(parts) == 2:
            batch_start = int(parts[0])
            batch_end = int(parts[1])

    use_api = not args.no_api

    log("Starting Google Search Finder")
    process_districts(batch_start, batch_end, args.resume,
                      args.district, args.limit, use_api)


if __name__ == "__main__":
    main()
