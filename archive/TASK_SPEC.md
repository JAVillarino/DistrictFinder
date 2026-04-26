# Texas School Board Video URL Discovery Task

## Objective

Systematically discover and catalog video archive URLs for all ~1,024 Texas Independent School Districts (ISDs). This dataset will power the HERC/Kinder Institute School Board Analysis project.

## Input

You will work from a CSV file `texas_districts.csv` containing:
- `district_id`: TEA district number
- `district_name`: Full district name (e.g., "Houston Independent School District")
- `county`: County name
- `enrollment`: Approximate student enrollment (for prioritization)

## Output

Create and continuously update `district_video_sources.csv` with:

```csv
district_id,district_name,county,enrollment,website_url,video_platform,video_url,archive_start_year,youtube_channel_id,notes,confidence,last_checked
```

### Field Definitions

| Field | Description | Example |
|-------|-------------|---------|
| `district_id` | TEA ID | `101912` |
| `district_name` | Full name | `Houston ISD` |
| `website_url` | Official district homepage | `https://www.houstonisd.org` |
| `video_platform` | One of: `youtube`, `swagit`, `granicus`, `vimeo`, `facebook`, `mp4_direct`, `none_found`, `website_down` | `swagit` |
| `video_url` | Direct URL to video archive page | `https://houstonisd.swagit.com/` |
| `archive_start_year` | Earliest year with videos (if visible) | `2014` |
| `youtube_channel_id` | If YouTube, the channel ID | `UC...` |
| `notes` | Any relevant observations | `"Also has Granicus for older meetings"` |
| `confidence` | `high`, `medium`, `low` | `high` |
| `last_checked` | ISO date | `2025-01-14` |

## Process

### Step 1: Find District Website

For each district:
1. Search for `"{district_name}" official website`
2. Verify it's the actual district site (look for .org, .net, .us domains, official logos)
3. Record the homepage URL

**Common patterns:**
- `{name}isd.org`
- `{name}isd.net`
- `www.{name}isd.esc{region}.net`

### Step 2: Locate Board Meeting Videos

From the district homepage, look for:
1. "School Board" or "Board of Trustees" section
2. "Board Meetings" or "Meeting Videos" link
3. "Watch Live" or "Live Stream" links

**Navigation paths to try:**
- Homepage → School Board → Board Meetings → Videos
- Homepage → About Us → Board of Trustees → Meeting Archives
- Homepage → Departments → Board Services

### Step 3: Classify Video Platform

Identify the hosting platform:

| Platform | URL Pattern | Notes |
|----------|-------------|-------|
| YouTube | `youtube.com/channel/`, `youtube.com/@`, `youtube.com/playlist?list=` | Look for channel ID |
| Swagit | `*.swagit.com`, `swagit.com/play/` | Common for large TX districts |
| Granicus | `*.granicus.com` | Government streaming platform |
| Vimeo | `vimeo.com/` | Less common |
| Facebook | `facebook.com/*/videos` | Sometimes used for live streams |
| MP4 Direct | Direct links to `.mp4` files on district server | Rare, harder to scrape |
| None Found | No video presence discovered | Note what you did find |

### Step 4: Document Archive Depth

If visible, note:
- Earliest meeting year available
- Approximate meeting count (if shown)
- Whether archive is complete or spotty

### Step 5: Checkpoint Progress

**CRITICAL**: Save progress every 25 districts.

After each batch of 25:
1. Write current results to `district_video_sources.csv`
2. Log progress to `discovery_log.txt`: `"[2025-01-14 10:30] Completed districts 1-25. 22 YouTube, 2 Swagit, 1 not found."`
3. Continue to next batch

## Prioritization

Process districts in this order:
1. **Tier 1 (enrollment > 50,000)**: ~20 districts - Highest priority
2. **Tier 2 (enrollment 10,000-50,000)**: ~100 districts
3. **Tier 3 (enrollment 1,000-10,000)**: ~400 districts
4. **Tier 4 (enrollment < 1,000)**: ~500 districts - Many may not have video

## Edge Cases

### District website is down/broken
- Record `website_down` in platform field
- Note error in notes field
- Move on

### Multiple video sources
- Record the PRIMARY source in main fields
- Note secondary sources in `notes` (e.g., "YouTube for 2020+, Granicus for older")

### Facebook-only live streams
- Record as `facebook`
- Note if no archive exists ("live only, no archive")

### Videos embedded in BoardDocs/BoardBook
- These often link to external platforms
- Find the actual video host and record that

### Regional Education Service Centers (ESCs)
- Skip these, focus on ISDs only

## Validation Hints

To verify a URL is correct:
- Page should show multiple meeting videos
- Titles should reference "Board Meeting", "Board of Trustees", district name
- Dates should be roughly monthly

If you find a generic YouTube channel with no board content, mark as `none_found`.

## Sample Output Rows

```csv
district_id,district_name,county,enrollment,website_url,video_platform,video_url,archive_start_year,youtube_channel_id,notes,confidence,last_checked
101912,Houston ISD,Harris,187000,https://www.houstonisd.org,swagit,https://houstonisdtx.new.swagit.com/,2014,,Also uses Legistar for agendas,high,2025-01-14
057905,Dallas ISD,Dallas,145000,https://www.dallasisd.org,swagit,https://dallasisdtx.swagit.com/,2014,,Has separate archive and live pages,high,2025-01-14
220905,Austin ISD,Travis,72000,https://www.austinisd.org,youtube,https://www.youtube.com/@AustinISD,2018,UC1234567890,Also broadcasts on AISD.TV,high,2025-01-14
015907,San Antonio ISD,Bexar,46000,https://www.saisd.net,granicus,https://sanantonioisd.granicus.com/,2016,,BoardBook for agendas,high,2025-01-14
```

## Resume Instructions

If task is interrupted:
1. Check `district_video_sources.csv` for last completed district
2. Check `discovery_log.txt` for last checkpoint
3. Resume from next district in the input list

## Final Deliverables

1. `district_video_sources.csv` - Complete dataset
2. `discovery_log.txt` - Process log with timestamps
3. `summary_stats.md` - Platform breakdown, coverage stats
4. `manual_review_needed.csv` - Districts requiring human verification

## Success Metrics

| Metric | Target |
|--------|--------|
| Districts processed | 1,024 |
| Video URL found | 60-70% |
| High confidence classifications | 80%+ of found URLs |
| Checkpoints logged | Every 25 districts |
