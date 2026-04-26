#!/usr/bin/env python3
"""
Universal District Website Crawler - Texas School Board Video Sources

Crawls each district's website to find embedded video platforms,
YouTube channels, livestream links, and meeting archive pages.

Covers platforms the pattern matchers miss: BoardDocs, Diligent, Panopto,
Boxcast, Vimeo, embedded YouTube, website_archive, and custom solutions.

Strategy:
    1. Discover district website URL (construct from name or search)
    2. Find the board/meetings page (crawl common paths)
    3. Parse HTML for video platform signatures
    4. Score confidence based on what's found

Usage:
    python website_crawler.py                    # Process all pending
    python website_crawler.py --batch 1-50       # Process rows 1-50
    python website_crawler.py --resume           # Resume from checkpoint
    python website_crawler.py --district 101912  # Single district
"""

import csv
import requests
import re
import json
import argparse
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# Configuration
INPUT_FILE = "../data/districts_complete.csv"
OUTPUT_FILE = "../data/crawler_results.csv"
PROGRESS_FILE = "crawler_progress.json"
LOG_FILE = "website_crawler.log"

REQUEST_TIMEOUT = 12
DELAY_BETWEEN_REQUESTS = 0.5
MAX_PAGES_PER_DISTRICT = 8
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (educational research project)"

# Common paths where board meeting info lives
BOARD_PATHS = [
    "/board",
    "/board-of-trustees",
    "/school-board",
    "/board-meetings",
    "/boardoftrustees",
    "/meetings",
    "/board/meetings",
    "/board-of-trustees/meetings",
    "/board/board-meetings",
    "/live-feed",
    "/live",
    "/livestream",
    "/board/live-stream",
    "/board-meeting-videos",
    "/board/video-archive",
    "/board/meeting-recordings",
    "/board-of-trustees/meeting-recordings",
    "/board-of-trustees/board-meetings",
]

# Common website URL patterns for Texas ISDs
WEBSITE_PATTERNS = [
    "https://www.{name}isd.net",
    "https://www.{name}isd.org",
    "https://www.{name}isd.com",
    "https://www.{name}.k12.tx.us",
    "https://{name}isd.net",
    "https://{name}isd.org",
    "https://www.{name}cisd.org",
    "https://www.{name}cisd.net",
    "https://www.{name}msd.org",
]

# Platform detection signatures
# Each entry: (platform_name, [(pattern, where_to_look), ...])
PLATFORM_SIGNATURES = {
    "swagit": {
        "url_patterns": [r"swagit\.com"],
        "html_patterns": [r"swagit\.com", r"swagit"],
    },
    "granicus": {
        "url_patterns": [r"granicus\.com", r"iqm2\.com"],
        "html_patterns": [r"granicus\.com", r"iqm2\.com", r"granicus"],
    },
    "youtube": {
        "url_patterns": [r"youtube\.com/(channel|c|@|user)", r"youtu\.be"],
        "html_patterns": [r"youtube\.com/embed", r"youtube\.com/(channel|c|@|user)", r"youtube\.com/live"],
    },
    "boarddocs": {
        "url_patterns": [r"go\.boarddocs\.com"],
        "html_patterns": [r"boarddocs\.com", r"BoardDocs"],
    },
    "boardbook": {
        "url_patterns": [r"meetings\.boardbook\.org"],
        "html_patterns": [r"boardbook\.org", r"BoardBook"],
    },
    "boxcast": {
        "url_patterns": [r"boxcast\.(tv|com)"],
        "html_patterns": [r"boxcast\.(tv|com)", r"boxcast"],
    },
    "vimeo": {
        "url_patterns": [r"vimeo\.com"],
        "html_patterns": [r"player\.vimeo\.com", r"vimeo\.com"],
    },
    "diligent": {
        "url_patterns": [r"diligent\.(com|net)"],
        "html_patterns": [r"diligent", r"BoardEffect"],
    },
    "panopto": {
        "url_patterns": [r"panopto\.com"],
        "html_patterns": [r"panopto\.com", r"Panopto"],
    },
    "citizenportal": {
        "url_patterns": [r"citizenportal\.ai"],
        "html_patterns": [r"citizenportal", r"CitizenPortal"],
    },
    "zoom": {
        "url_patterns": [r"zoom\.us"],
        "html_patterns": [r"zoom\.us/rec", r"zoom\.us/j"],
    },
    "facebook_live": {
        "url_patterns": [r"facebook\.com/.*/videos"],
        "html_patterns": [r"facebook\.com/plugins/video", r"facebook\.com/.*/live"],
    },
}

# Keywords that indicate video/meeting content
VIDEO_KEYWORDS = ["video", "watch", "recording", "livestream", "live stream",
                  "live feed", "broadcast", "replay", "webcast", "stream"]
MEETING_KEYWORDS = ["board meeting", "trustees", "regular meeting", "special meeting",
                    "board of trustees", "school board"]
ARCHIVE_KEYWORDS = ["archive", "past meetings", "previous meetings", "recordings",
                    "meeting archive", "video archive", "past recordings"]


def log(message):
    """Log message to console and file"""
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def normalize_name(district_name):
    """Normalize district name for URL construction."""
    name = district_name
    for suffix in [" ISD", " CISD", " I.S.D.", " MSD", " CSD",
                   " CONS", " Independent School District"]:
        name = name.replace(suffix, "")
    name = re.sub(r'[^a-zA-Z]', '', name)
    return name.lower()


def discover_website(district_name, known_url=None):
    """
    Find the district's website URL.
    Returns (url, was_discovered) or (None, False).
    """
    # Use known URL if available
    if known_url and known_url.strip():
        return (known_url.strip(), False)

    normalized = normalize_name(district_name)

    for pattern in WEBSITE_PATTERNS:
        url = pattern.format(name=normalized)
        try:
            response = requests.head(
                url, timeout=8, allow_redirects=True,
                headers={"User-Agent": USER_AGENT}
            )
            if response.status_code < 400:
                log(f"    Website found: {url}")
                return (url, True)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.TooManyRedirects):
            continue
        time.sleep(0.2)

    return (None, False)


def fetch_page(url):
    """Fetch a page and return (response_text, final_url) or (None, None)."""
    try:
        response = requests.get(
            url, timeout=REQUEST_TIMEOUT, allow_redirects=True,
            headers={"User-Agent": USER_AGENT}
        )
        if response.status_code < 400:
            return (response.text, response.url)
    except (requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.TooManyRedirects):
        pass
    except Exception as e:
        log(f"    Fetch error for {url}: {e}")
    return (None, None)


def find_board_pages(base_url):
    """
    Find board/meeting pages by crawling common paths and the homepage.
    Returns list of (url, html_content) tuples.
    """
    found_pages = []

    # 1. Try common board paths directly
    for path in BOARD_PATHS:
        url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
        html, final_url = fetch_page(url)
        if html:
            found_pages.append((final_url, html))
            if len(found_pages) >= MAX_PAGES_PER_DISTRICT:
                return found_pages
        time.sleep(0.3)

    # 2. If we found fewer than 2 pages, try crawling the homepage for board links
    if len(found_pages) < 2:
        homepage_html, _ = fetch_page(base_url)
        if homepage_html:
            soup = BeautifulSoup(homepage_html, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text(strip=True).lower()

                # Look for links mentioning board/meetings/video
                if any(kw in text for kw in ['board', 'meeting', 'trustee', 'video', 'live', 'stream']):
                    full_url = urljoin(base_url, href)
                    # Only follow internal links
                    if urlparse(full_url).netloc == urlparse(base_url).netloc:
                        if full_url not in [p[0] for p in found_pages]:
                            html, final_url = fetch_page(full_url)
                            if html:
                                found_pages.append((final_url, html))
                                if len(found_pages) >= MAX_PAGES_PER_DISTRICT:
                                    return found_pages
                            time.sleep(0.3)

    return found_pages


def detect_platforms(html_content, page_url):
    """
    Detect video platforms in page HTML.
    Returns list of (platform, video_url, confidence_boost) tuples.
    """
    detections = []
    html_lower = html_content.lower()

    for platform, sigs in PLATFORM_SIGNATURES.items():
        # Check HTML content for platform signatures
        for pattern in sigs["html_patterns"]:
            if re.search(pattern, html_content, re.IGNORECASE):
                # Try to extract the actual video URL
                video_url = extract_video_url(html_content, platform, page_url)
                detections.append((platform, video_url or page_url, 0))
                break

    return detections


def extract_video_url(html_content, platform, page_url):
    """Extract the actual video/embed URL for a detected platform."""
    soup = BeautifulSoup(html_content, 'html.parser')

    if platform == "youtube":
        # Look for YouTube iframes
        for iframe in soup.find_all('iframe', src=True):
            src = iframe['src']
            if 'youtube.com' in src or 'youtu.be' in src:
                # Try to extract channel URL from embed
                match = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]+)', src)
                if match:
                    return f"https://www.youtube.com/embed/{match.group(1)}"

        # Look for YouTube links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if re.search(r'youtube\.com/(channel|c|@|user)/[a-zA-Z0-9_@-]+', href):
                return href
            if re.search(r'youtube\.com/@[a-zA-Z0-9_-]+', href):
                return href

        # Look for YouTube links in text
        match = re.search(r'(https?://(?:www\.)?youtube\.com/(?:channel|c|@|user)/[a-zA-Z0-9_@-]+)', html_content)
        if match:
            return match.group(1)

    elif platform == "swagit":
        match = re.search(r'(https?://[a-zA-Z0-9.-]+\.swagit\.com[^\s"\'<>]*)', html_content)
        if match:
            return match.group(1)

    elif platform == "granicus":
        match = re.search(r'(https?://[a-zA-Z0-9.-]+\.(?:granicus\.com|iqm2\.com)[^\s"\'<>]*)', html_content)
        if match:
            return match.group(1)

    elif platform == "boarddocs":
        match = re.search(r'(https?://go\.boarddocs\.com/tx/[a-zA-Z0-9]+/Board\.nsf[^\s"\'<>]*)', html_content)
        if match:
            return match.group(1)

    elif platform == "boardbook":
        match = re.search(r'(https?://meetings\.boardbook\.org/[^\s"\'<>]*)', html_content)
        if match:
            return match.group(1)

    elif platform == "boxcast":
        match = re.search(r'(https?://[a-zA-Z0-9.-]+\.boxcast\.(?:tv|com)[^\s"\'<>]*)', html_content)
        if match:
            return match.group(1)
        # Also check for boxcast embed IDs
        match = re.search(r'boxcast[^\s"\'<>]*(?:channel|broadcast)[^\s"\'<>]*', html_content)
        if match:
            return page_url  # Use the page URL since embed doesn't have standalone URL

    elif platform == "vimeo":
        for iframe in soup.find_all('iframe', src=True):
            if 'vimeo.com' in iframe['src']:
                return iframe['src']
        match = re.search(r'(https?://(?:player\.)?vimeo\.com/[^\s"\'<>]+)', html_content)
        if match:
            return match.group(1)

    elif platform == "facebook_live":
        match = re.search(r'(https?://(?:www\.)?facebook\.com/[^\s"\'<>]+/videos[^\s"\'<>]*)', html_content)
        if match:
            return match.group(1)

    elif platform == "zoom":
        match = re.search(r'(https?://[a-zA-Z0-9.-]*zoom\.us/rec/[^\s"\'<>]+)', html_content)
        if match:
            return match.group(1)

    return None


def extract_youtube_channel(html_content):
    """
    Specifically extract YouTube channel URLs/handles from page content.
    Returns (@handle, channel_url) or (None, None).
    """
    # Pattern: youtube.com/@handle
    match = re.search(r'youtube\.com/(@[a-zA-Z0-9_-]+)', html_content)
    if match:
        handle = match.group(1)
        return (handle, f"https://www.youtube.com/{handle}")

    # Pattern: youtube.com/channel/UCxxxxxx
    match = re.search(r'youtube\.com/channel/(UC[a-zA-Z0-9_-]+)', html_content)
    if match:
        return (f"channel/{match.group(1)}", f"https://www.youtube.com/channel/{match.group(1)}")

    # Pattern: youtube.com/c/ChannelName
    match = re.search(r'youtube\.com/c/([a-zA-Z0-9_-]+)', html_content)
    if match:
        return (f"@{match.group(1)}", f"https://www.youtube.com/c/{match.group(1)}")

    # Pattern: youtube.com/user/Username
    match = re.search(r'youtube\.com/user/([a-zA-Z0-9_-]+)', html_content)
    if match:
        return (f"@{match.group(1)}", f"https://www.youtube.com/user/{match.group(1)}")

    return (None, None)


def score_result(detections, pages_html, has_video_keywords, has_meeting_keywords, has_archive_keywords):
    """
    Calculate confidence score for a district's findings.
    Returns (score, confidence_level).
    """
    score = 0

    # Found a known platform (30 pts)
    if detections:
        score += 30
        # Extracted an actual video URL vs just detected platform name (10 pts)
        best = detections[0]
        if best[1] and best[1] != "":
            score += 10

    # Video-related keywords found (20 pts)
    if has_video_keywords:
        score += 20

    # Meeting keywords found (10 pts)
    if has_meeting_keywords:
        score += 10

    # Archive keywords suggest actual recordings exist (15 pts)
    if has_archive_keywords:
        score += 15

    # Multiple pages found with video content (15 pts)
    video_pages = sum(1 for html in pages_html
                      if any(kw in html.lower() for kw in VIDEO_KEYWORDS))
    if video_pages >= 2:
        score += 15
    elif video_pages == 1:
        score += 8

    score = min(score, 100)

    if score >= 85:
        return (score, "high")
    elif score >= 60:
        return (score, "medium")
    else:
        return (score, "low")


def process_district(district):
    """
    Process a single district: discover website, crawl for video platforms.
    Returns result dict or None if nothing found.
    """
    district_id = district["district_id"]
    district_name = district["district_name"]
    county = district.get("county", "")
    enrollment = district.get("enrollment", "")
    known_url = district.get("website_url", "")

    log(f"  Discovering website for {district_name}...")

    # Step 1: Find the district website
    website_url, was_discovered = discover_website(district_name, known_url)
    if not website_url:
        log(f"    No website found")
        return None

    # Step 2: Find board/meeting pages
    log(f"    Crawling {website_url} for board pages...")
    board_pages = find_board_pages(website_url)

    if not board_pages:
        log(f"    No board pages found")
        return None

    log(f"    Found {len(board_pages)} board-related pages")

    # Step 3: Detect platforms across all pages
    all_detections = []
    all_html = []
    has_video_kw = False
    has_meeting_kw = False
    has_archive_kw = False

    for page_url, html in board_pages:
        html_lower = html.lower()
        all_html.append(html)

        # Detect platforms
        detections = detect_platforms(html, page_url)
        all_detections.extend(detections)

        # Check keywords
        if any(kw in html_lower for kw in VIDEO_KEYWORDS):
            has_video_kw = True
        if any(kw in html_lower for kw in MEETING_KEYWORDS):
            has_meeting_kw = True
        if any(kw in html_lower for kw in ARCHIVE_KEYWORDS):
            has_archive_kw = True

    # Step 4: Extract YouTube channel if found
    yt_handle = None
    yt_url = None
    for html in all_html:
        handle, channel_url = extract_youtube_channel(html)
        if handle:
            yt_handle = handle
            yt_url = channel_url
            break

    # Step 5: Determine best platform
    if not all_detections and not yt_handle:
        if has_video_kw or has_archive_kw:
            # Found video keywords but no known platform — likely website_archive
            platform = "website_archive"
            video_url = board_pages[0][0]  # URL of first board page
        else:
            log(f"    No video platforms detected")
            return None
    elif yt_handle and not any(d[0] not in ("youtube",) for d in all_detections):
        platform = "youtube"
        video_url = yt_url
    elif all_detections:
        # Prioritize: swagit > granicus > youtube > boarddocs > others
        priority = ["swagit", "granicus", "youtube", "boxcast", "vimeo",
                     "panopto", "diligent", "boarddocs", "boardbook",
                     "facebook_live", "zoom", "citizenportal"]
        best = None
        for p in priority:
            for det in all_detections:
                if det[0] == p:
                    best = det
                    break
            if best:
                break
        if not best:
            best = all_detections[0]
        platform = best[0]
        video_url = best[1]
    else:
        platform = "youtube"
        video_url = yt_url

    # Step 6: Score
    score, confidence = score_result(
        all_detections, [h for _, h in board_pages],
        has_video_kw, has_meeting_kw, has_archive_kw
    )

    # Build notes
    platforms_found = list(set(d[0] for d in all_detections))
    if yt_handle and "youtube" not in platforms_found:
        platforms_found.append("youtube")
    pages_crawled = len(board_pages)
    notes = f"Crawler found: {', '.join(platforms_found) if platforms_found else platform}. " \
            f"Crawled {pages_crawled} pages. Score: {score}/100."

    result = {
        "district_id": district_id,
        "district_name": district_name,
        "county": county,
        "enrollment": enrollment,
        "website_url": website_url,
        "video_platform": platform,
        "video_url": video_url,
        "archive_start_year": "",
        "youtube_channel_id": yt_handle or "",
        "notes": notes,
        "confidence": confidence,
        "last_checked": datetime.now().strftime("%Y-%m-%d"),
        "video_status": "crawler_found",
        "score": score,
    }

    log(f"    FOUND: {platform} at {video_url} (confidence: {confidence}, score: {score})")
    return result


def load_progress():
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"processed_ids": [], "stats": {"found": 0, "not_found": 0}}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def load_results():
    """Load existing crawler results."""
    results = {}
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                results[row["district_id"]] = row
    return results


def save_results(results):
    """Write all results to CSV."""
    if not results:
        return
    fieldnames = ["district_id", "district_name", "county", "enrollment",
                  "website_url", "video_platform", "video_url", "archive_start_year",
                  "youtube_channel_id", "notes", "confidence", "last_checked",
                  "video_status", "score"]
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results.values():
            writer.writerow(row)


def process_districts(batch_start=None, batch_end=None, resume=False, single_id=None):
    """Process districts from the complete CSV."""
    progress = load_progress() if resume else {"processed_ids": [], "stats": {"found": 0, "not_found": 0}}
    results = load_results()

    # Load input
    with open(INPUT_FILE, "r") as f:
        reader = csv.DictReader(f)
        districts = list(reader)

    # Filter to pending only (don't re-crawl verified districts)
    if single_id:
        districts = [d for d in districts if d["district_id"] == single_id]
        log(f"Processing single district: {single_id}")
    else:
        districts = [d for d in districts if d.get("video_status", "pending") == "pending"]
        log(f"Found {len(districts)} pending districts")

    # Batch filter
    if batch_start is not None and batch_end is not None:
        start_idx = batch_start - 1
        end_idx = batch_end
        districts = districts[start_idx:end_idx]
        log(f"Processing batch: rows {batch_start}-{batch_end} ({len(districts)} districts)")

    # Skip already processed if resuming
    if resume:
        districts = [d for d in districts if d["district_id"] not in progress["processed_ids"]]
        log(f"Resuming: {len(districts)} districts remaining")

    found_count = progress["stats"]["found"]
    not_found_count = progress["stats"]["not_found"]

    for i, district in enumerate(districts):
        district_id = district["district_id"]
        district_name = district["district_name"]

        log(f"[{i+1}/{len(districts)}] {district_name} ({district_id})")

        result = process_district(district)

        if result:
            results[district_id] = result
            found_count += 1
        else:
            not_found_count += 1

        progress["processed_ids"].append(district_id)
        progress["stats"]["found"] = found_count
        progress["stats"]["not_found"] = not_found_count

        # Save every 10 districts
        if (i + 1) % 10 == 0:
            save_progress(progress)
            save_results(results)
            log(f"Checkpoint: {i+1}/{len(districts)} processed (Found: {found_count}, Not found: {not_found_count})")

        time.sleep(DELAY_BETWEEN_REQUESTS)

    # Final save
    save_progress(progress)
    save_results(results)

    total = found_count + not_found_count
    log(f"\n{'='*60}")
    log(f"Website Crawler Complete!")
    log(f"  Total processed: {total}")
    if total > 0:
        log(f"  Found video source: {found_count} ({found_count/total*100:.1f}%)")
    log(f"  Not found: {not_found_count}")
    log(f"  Results written to: {OUTPUT_FILE}")
    log(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Universal Website Crawler for Texas School Districts")
    parser.add_argument("--batch", help="Batch range (e.g., 1-50)", type=str)
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--district", help="Process a single district by ID", type=str)

    args = parser.parse_args()

    batch_start = None
    batch_end = None

    if args.batch:
        parts = args.batch.split("-")
        if len(parts) == 2:
            batch_start = int(parts[0])
            batch_end = int(parts[1])

    log("Starting Universal Website Crawler")
    log(f"Input: {INPUT_FILE}")
    log(f"Output: {OUTPUT_FILE}")

    process_districts(batch_start, batch_end, args.resume, args.district)


if __name__ == "__main__":
    main()
