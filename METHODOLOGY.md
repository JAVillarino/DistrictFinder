# Discovery Pipeline Methodology

This document describes how the DistrictFinder pipeline locates, classifies, and validates school board meeting video archives. It is written for someone who wants to understand the mechanics or adapt the pipeline for another state.

---

## Data Source

The pipeline starts with the Texas Education Agency's AskTED system, which publishes a downloadable roster of all recognized public school entities in Texas. The raw file (`data/tea_master_districts_raw.csv`) contains roughly 9,700 rows because it includes individual campuses, charter schools, and administrative units alongside independent school districts.

`process_tea_master.py` filters that list down to ISDs. It accepts any row whose entity-type field contains one of: `ISD`, `CISD`, `CONS ISD`, `INDEPENDENT SCHOOL DISTRICT`, `CONSOLIDATED ISD`, `MSD`, `CSD`, or `CHARTER`. From each surviving row it extracts four fields:

- **district_id** — the six-digit TEA canonical identifier (TEA prepends an apostrophe to IDs with leading zeros, which the script strips before left-padding to exactly six digits)
- **district_name** — the official TEA name
- **county** — county name
- **enrollment** — student count as of October of the collection year

The script deduplicates on `district_id` and rejects any row where the ID cannot be normalized to exactly six digits. The cleaned output lands in `data/tea_districts_master_clean.csv` at roughly 1,208 unique districts.

### Districts Without Websites

Roughly 10–15% of districts have no website listed in the TEA data. The pipeline handles this in two passes before crawling begins.

**Pass 1 — Pattern-based URL generation.** `discover_websites.py` derives URL candidates from the district name by normalizing it (lowercased, punctuation removed) and then generating slug variants:

```
{name}isd.org / .net / .us / .com / .edu
{name}isd (concatenated form)
{first_word}isd
{name}isd (hyphenated)
{name}schools
{acronym}isd  (only if the acronym is ≥ 2 characters, to prevent collisions)
```

Each candidate is tested with an HTTP HEAD request (falling back to GET if the server returns 405). A URL is accepted if it returns a status below 400, or if it returns 401, 403, or 451 (authentication/permission required—these indicate a live site even if content is gated). Redirects are accepted only when the final hostname shares a four-character substring with the original candidate, which prevents accepting a redirect to a parked domain or an unrelated district.

**Pass 2 — Search fallback.** For districts that still have no website after pattern matching, `google_search_finder.py` performs a targeted web search using `site:` operators against known vendor platforms (Swagit, Granicus, BoardDocs), extracting district-specific results from the response HTML.

---

## Stage 1: Page Discovery

Once a district has a website, `website_crawler.py` attempts to locate the page where board meeting videos live.

### Direct Path Probing

The crawler first tries a fixed list of common board-meeting URL paths by appending each to the district's root URL and issuing a HEAD request with a 12-second timeout:

```
/board                         /board-of-trustees
/school-board                  /board-meetings
/meetings                      /board/meetings
/board/board-meetings          /live-feed
/live                          /livestream
/board/live-stream             /board-meeting-videos
/board/video-archive           /board/meeting-recordings
/board-of-trustees/meetings    /board-of-trustees/board-meetings
/board-of-trustees/meeting-recordings
```

Any path that returns a live response is retained as a candidate board page. The crawler caps itself at eight pages per district.

### Homepage Link Fallback

If direct probing yields fewer than two candidate pages, the crawler fetches the district homepage and scans its anchor tags for links whose `href` or link text contains any of: `board`, `meeting`, `trustee`, `video`, `live`, or `stream`. Those links are fetched and added to the candidate pool.

### Page-Level Signals

On each candidate page the crawler parses HTML looking for two categories of signals.

**Video keywords** indicate that a page likely hosts recordings: `video`, `watch`, `recording`, `livestream`, `live stream`, `live feed`, `broadcast`, `replay`, `webcast`, `stream`.

**Archive keywords** indicate that multiple past meetings are available: `archive`, `past meetings`, `previous meetings`, `recordings`, `meeting archive`, `video archive`, `past recordings`.

The crawler also checks for embedded `<iframe>` and `<embed>` elements, which are the clearest structural signal that a video player is present on the page rather than merely linked.

### Non-Standard Site Structures

Districts that host video on a vendor platform (Swagit, Granicus, YouTube, etc.) often embed that platform inside an iframe on their own site rather than linking to it directly. The crawler handles this by extracting `src` attributes from all iframe elements and checking those URLs against the platform detection patterns described in the next section.

Some districts redirect their board page to a subdomain (e.g., `meetings.fortbendisd.com`) or to an entirely separate vendor URL with no apparent connection to the district's domain. The crawler follows these redirects transparently because `requests` follows HTTP 301/302 chains by default.

---

## Stage 2: Platform Classification

For each candidate page, the crawler runs a two-layer detection process: first match the URL structure of the page or any link it contains, then match patterns in the page HTML.

### Detection Architecture

Each platform is defined by two lists of regex patterns:

```python
PLATFORMS = {
    "swagit": {
        "url_patterns":  [r"swagit\.com"],
        "html_patterns": [r"swagit\.com", r"swagit"],
    },
    "granicus": {
        "url_patterns":  [r"granicus\.com", r"iqm2\.com"],
        "html_patterns": [r"granicus\.com", r"iqm2\.com"],
    },
    "youtube": {
        "url_patterns":  [r"youtube\.com/(channel|c|@|user)", r"youtu\.be"],
        "html_patterns": [r"youtube\.com/embed", r"youtube\.com/live",
                          r"youtube\.com/(channel|c|@|user)"],
    },
    "boarddocs": {
        "url_patterns":  [r"go\.boarddocs\.com"],
        "html_patterns": [r"boarddocs\.com", r"BoardDocs"],
    },
    "boardbook": {
        "url_patterns":  [r"meetings\.boardbook\.org"],
        "html_patterns": [r"boardbook\.org", r"BoardBook"],
    },
    "boxcast": {
        "url_patterns":  [r"boxcast\.(tv|com)"],
        "html_patterns": [r"boxcast\.(tv|com)"],
    },
    "vimeo": {
        "url_patterns":  [r"vimeo\.com"],
        "html_patterns": [r"player\.vimeo\.com", r"vimeo\.com"],
    },
    "panopto": {
        "url_patterns":  [r"panopto\.com"],
        "html_patterns": [r"panopto\.com"],
    },
    "citizenportal": {
        "url_patterns":  [r"citizenportal\.ai"],
        "html_patterns": [r"citizenportal"],
    },
}
```

URL patterns are tested against every link found on the page. HTML patterns are tested against the full page source. The first platform whose patterns match is selected; if none match but video or archive keywords are present, the page is recorded as `website_archive` (a generic non-vendor video host).

### Per-Platform URL Extraction and Validation

Once a platform is identified, the crawler applies a platform-specific regex to extract a canonical URL for that district's video archive.

**Swagit.** `swagit_matcher.py` generates URL candidates by normalizing the district name (lowercase, remove `ISD`/`CISD`/`MSD`, strip punctuation) and testing five subdomain patterns in order:

```
{name}isd.new.swagit.com       (most common)
{name}isdtx.new.swagit.com     (Texas-specific)
{name}isd.swagit.com           (legacy)
{name}isdtx.swagit.com         (legacy Texas)
{name}isdtx.v3.swagit.com      (version 3)
```

Each candidate is fetched; a hit is scored as described in the confidence section below. If the crawler encounters Swagit during a general crawl rather than the dedicated matcher, it extracts the URL with:

```python
re.search(r'(https?://[a-zA-Z0-9.-]+\.swagit\.com[^\s"\'<>]*)', html)
```

**Granicus.** `granicus_matcher.py` tests four URL patterns:

```
{name}.granicus.com/
{name}isd.granicus.com/player/
{name}tx.iqm2.com/Citizens/
{name}schoolstx.iqm2.com/Citizens/
```

IQM2 is Granicus's legacy product; both domains receive identical treatment. Extraction regex during crawl:

```python
re.search(r'(https?://[a-zA-Z0-9.-]+\.(?:granicus\.com|iqm2\.com)[^\s"\'<>]*)', html)
```

**YouTube.** YouTube channel URLs exist in four forms, and the crawler tries each in priority order:

```python
# 1. @handle — preferred; uniquely identifies the channel
re.search(r'youtube\.com/(@[a-zA-Z0-9_-]+)', html)

# 2. /channel/UCxxxxxx — opaque ID, always stable
re.search(r'youtube\.com/channel/(UC[a-zA-Z0-9_-]+)', html)

# 3. /c/ChannelName — custom vanity URL
re.search(r'youtube\.com/c/([a-zA-Z0-9_-]+)', html)

# 4. /user/Username — older format
re.search(r'youtube\.com/user/([a-zA-Z0-9_-]+)', html)
```

`discover_youtube_channels.py` supplements the crawler using the YouTube Data API v3. It queries `"{district name} ISD board meetings Texas"` with `type=channel` and `maxResults=5`, then validates each result by checking whether the channel title contains a token derived from the district name (see the name-matching logic below). Only validated results are written to the dataset.

**BoardDocs.** BoardDocs hosts agendas and, for some districts, video archives at `https://go.boarddocs.com/tx/{slug}/Board.nsf/Public`. The slug is derived by trying `{name}isd`, `{name}`, `{name}cisd`, `{name}msd`, and `{name}tx`. Extraction regex:

```python
re.search(r'(https?://go\.boarddocs\.com/tx/[a-zA-Z0-9]+/Board\.nsf[^\s"\'<>]*)', html)
```

**Important:** BoardDocs often hosts agendas only, with no video whatsoever. A BoardDocs URL is never marked HIGH confidence unless a video player element is confirmed visible on the page. See confidence logic below.

**BoardBook.** Similar to BoardDocs — primarily an agenda tool. Default assumption is no video unless explicit evidence exists. Extraction regex:

```python
re.search(r'(https?://meetings\.boardbook\.org/[^\s"\'<>]*)', html)
```

**BoxCast, Vimeo, Panopto, CitizenPortal.** These are treated as supplementary platforms. BoxCast and Vimeo are straightforward video hosts:

```python
# BoxCast
re.search(r'(https?://[a-zA-Z0-9.-]+\.boxcast\.(?:tv|com)[^\s"\'<>]*)', html)

# Vimeo — prefer src from <iframe> elements; fall back to link scan
for iframe in soup.find_all('iframe', src=True):
    if 'vimeo.com' in iframe['src']:
        return iframe['src']
re.search(r'(https?://(?:player\.)?vimeo\.com/[^\s"\'<>]+)', html)
```

CitizenPortal is flagged as a paywall: it requires a subscription to access recordings, so any district using it cannot receive a HIGH confidence rating for free public access.

**Zoom and Facebook Live.** These are detected as supplementary signals. Zoom recordings and Facebook Live links are extracted and recorded but treated as LOW confidence by default because they are typically ad-hoc streams without a persistent archive:

```python
# Zoom recording
re.search(r'(https?://[a-zA-Z0-9.-]*zoom\.us/rec/[^\s"\'<>]+)', html)

# Facebook Live
re.search(r'(https?://(?:www\.)?facebook\.com/[^\s"\'<>]+/videos[^\s"\'<>]*)', html)
```

---

## Confidence Rating Logic

Every result is scored on a 0–100 scale across three layers. The thresholds are:

- **HIGH** — score ≥ 85
- **MEDIUM** — score 60–84
- **LOW** — score < 60

### Layer 1: HTTP Status (30 points)

If the video URL returns a status code below 400, the result receives 30 points. A dead URL (4xx or 5xx, or a connection timeout) receives 0 and cannot proceed to the other layers — the record is immediately marked LOW.

### Layer 2: Content Keywords (up to 40 points)

The page content is scanned for three groups of terms:

- **Video player evidence** (`iframe`, `video`, `embed`, `player`, `swagit`, `granicus`, `youtube`): +20 points if any match
- **Board meeting context** (`board`, `meeting`, `trustees`, `regular meeting`): +10 points if any match
- **Archive evidence** (`archive`, `past`, `recordings`, `previous`, `watch`): +10 points if any match

### Layer 3: Archive Depth (up to 30 points)

The pipeline counts embedded video elements and scans the page text for year and month references to estimate how current the archive is.

- Three or more video elements visible: +15 points
- One or two video elements: +8 points
- References to the current year and to recent months: +15 points

### Mandatory Verification Gates

Automated scoring alone does not produce a HIGH rating in the following cases. A human review step (or an explicit code path treating these as special cases) must confirm all three gates pass:

1. **Video player loads.** An actual embedded player is visible, not merely a link to a video page.
2. **Archive depth.** At least three distinct meetings are accessible, and the most recent is within six months of the check date.
3. **Free public access.** No login or subscription is required. Any CitizenPortal URL, or any page that prompts for credentials before showing content, fails this gate regardless of score.

If any gate fails, the result is capped at MEDIUM.

---

## Name-to-URL Validation

After scoring, `validate_stream_matches.py` runs a separate check to catch false positives where the crawl assigned a URL that belongs to a different district. This is a real problem: some patterns like `aisd.net` could plausibly match several ISDs.

The validator extracts a *signature* from each URL — the combination of platform and the domain-level identifier (e.g., `swagit:fortbendisd`, `youtube:@fortbendisd`). It then checks whether that identifier contains a meaningful token from the district's name.

**Token extraction** strips stopwords (`independent`, `school`, `district`, `consolidated`, `county`, `of`, `the`) and any word shorter than three characters, then lowercases and removes punctuation. `Fort Bend ISD` becomes the tokens `["fort", "bend"]`.

**Acronym generation** takes the first letter of each meaningful token. `Fort Bend ISD` produces `fbisd`.

**Boundary-aware matching** applies different rules based on token length to prevent substring collisions:

```python
def _boundary_contains_token(ident, needle):
    # Tokens 4+ chars: simple substring match
    if len(needle) >= 4:
        return needle in ident
    # 3-char tokens: must be followed by a known suffix or end of string
    # (prevents "arp" matching "sharpschool")
    return bool(re.search(
        rf"{re.escape(needle)}(isd|cisd|msd|tx|live|news|media|channel|schools|$)",
        ident,
    ))

def _boundary_contains_acronym(ident, needle):
    # Acronyms need both left and right boundaries
    # (prevents "tisd" matching "bmtisd")
    normalized = ident.replace("-", "").replace("_", "")
    return bool(re.search(
        rf"(^|[^a-z]){re.escape(needle)}(isd|cisd|msd|$)",
        normalized,
    ))
```

The validator also detects URLs that appear for multiple districts — a signal that the URL belongs to a vendor platform directory rather than a specific district — and flags those for review. Known mismatches that survived earlier passes are handled by a hardcoded `FORCE_CLEAR` table:

```python
FORCE_CLEAR = {
    ("227901", "website:aisd.net"),     # Austin ISD — aisd.net belongs to Arlington
    ("221912", "website:wylieisd.net"), # Wylie (Taylor Co) — wylieisd.net belongs to Wylie (Collin Co)
}
```

Each row receives a `KEEP`, `CLEAR`, or `REVIEW` decision. `CLEAR` nullifies the URL; `REVIEW` flags it for manual inspection without removing it.

---

## Failure Modes and Null Handling

**No video platform detected.** If the crawler processes all candidate pages for a district and finds no platform signatures but does find video or archive keywords, it records `video_platform = "website_archive"` and sets `video_url` to the first candidate board page. This indicates a plausible but unconfirmed archive that a human reviewer should check.

If neither platform signatures nor video keywords appear, the result is `None` — the district is recorded with `video_status = "none_found"` and `confidence = "low"`.

**Broken or unreachable URLs.** HTTP connection errors and timeouts during the validation pass return `(None, False, "")`. These trigger a score of 0 and the record is marked LOW. The error is written to `validation.log`. Broken URLs are not automatically removed from the dataset; they remain as LOW-confidence entries so that a future re-run can detect if the URL comes back online.

**Ambiguous platform results.** Platforms where the URL alone cannot confirm a district match (CitizenPortal, Panopto, BoardBook, YouTube playlist IDs without a channel handle) are always marked REVIEW rather than KEEP, regardless of name matching, because the identifier in the URL is opaque or shared across many districts.

**Shared URLs.** When the same `video_url` value appears for more than one district — meaning two or more districts were assigned identical URLs — the validator flags all of them REVIEW and records the count in the notes field. This pattern typically means the matcher hit a vendor platform's generic homepage rather than a district-specific page.

**Duplicate district IDs.** `validate_district_id.py` is the gate that prevents duplicate IDs from entering the dataset. It rejects any write operation for a district_id that already exists with a non-null video_url, unless the update is explicitly replacing a LOW-confidence result with a better one.

---

## Reproducing the Pipeline for Another State

### Prerequisites

- Python 3.9+
- `pip install requests beautifulsoup4 pandas`
- A YouTube Data API v3 key (for the YouTube channel discovery step only)

### Step 1: Obtain and Process the District Roster

Download the equivalent of the TEA AskTED CSV from the target state's education agency. Adapt `process_tea_master.py` to match the column names in that state's export. The required output columns are `district_id`, `district_name`, `county`, and `enrollment`. Save to `data/tea_districts_master_clean.csv`.

```bash
python3 scripts/process_tea_master.py
```

### Step 2: Initialize the Working Dataset

```bash
python3 scripts/merge_verified_with_master.py
```

This creates `data/districts_complete.csv` with all districts at `video_status = "pending"`.

### Step 3: Discover Missing Websites

```bash
python3 scripts/discover_websites.py
```

This populates the `website_url` column for districts that lack one in the source data, using the pattern-generation and HTTP-validation logic described above.

### Step 4: Run the Platform-Specific Matchers

These matchers are faster and more precise than the general crawler for platforms with predictable URL structures. Run them before the general crawler to reduce the crawler's workload.

```bash
python3 scripts/swagit_matcher.py --batch 1-100
python3 scripts/granicus_matcher.py --batch 1-100
python3 scripts/platform_directory_scraper.py --all
```

The `--batch` flag accepts a range of row indices; use it to parallelize across machines or to resume after interruption. All scripts support `--resume` to skip rows that already have a non-null result.

### Step 5: Run the General Crawler

```bash
python3 scripts/website_crawler.py --batch 1-50 --resume
```

This handles any district not resolved by the platform matchers. The `--resume` flag skips districts already marked with a result.

### Step 6: Discover YouTube Channels

```bash
python3 scripts/discover_youtube_channels.py --skip-populated
```

This calls the YouTube Data API for each district that still lacks a video URL. Set the `YOUTUBE_API_KEY` environment variable before running.

### Step 7: Validate All Results

```bash
python3 scripts/validation_pipeline.py --latest-batch
```

This applies the three-layer scoring model to every URL discovered in the previous steps, populating the `confidence` and `validation_score` columns.

### Step 8: Run Name-to-URL Validation

```bash
python3 scripts/validate_stream_matches.py
python3 scripts/validate_website_matches.py
```

These apply the boundary-aware name matching and duplicate detection logic, adding `KEEP`, `CLEAR`, or `REVIEW` annotations to each row.

### Step 9: Check Progress

```bash
python3 scripts/progress_tracker.py --status
```

This prints a summary of how many districts are at each `video_status` value and which confidence levels are represented.

### Adapting Platform Patterns for Another State

The Swagit and Granicus matchers use `tx` as a suffix in several URL patterns (`{name}isdtx`, `{name}schoolstx`). For another state, replace `tx` with the appropriate two-letter abbreviation and update the pattern lists in `swagit_matcher.py` (lines 32–38) and `granicus_matcher.py` (lines 32–37). The BoardDocs matcher uses `/tx/` in the URL path (`go.boarddocs.com/tx/{slug}`); update that path segment as well.

The `COMPOUND_SPLITS` table in `validate_stream_matches.py` (lines 67–122) contains Texas-specific compound district names like `channelview`, `goosecreek`, and `brazosport`. Extend this table with compound names from the target state to prevent incorrect tokenization during name matching.
