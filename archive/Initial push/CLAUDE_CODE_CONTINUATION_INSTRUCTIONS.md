# Instructions for Claude Code: Texas School Board Video URL Discovery

## Current Progress
- **Completed**: 2/50 districts (Houston ISD, Dallas ISD)
- **Files created**:
  - `district_video_sources.csv` - Main output file
  - `discovery_log.txt` - Progress log
  - This instruction file

## Task Overview
Systematically find video archive URLs for the remaining 48 districts in `/mnt/user-data/uploads/texas_districts_starter.csv`.

## Process for Each District

### Step 1: Search for the district website
```
web_search: "{district_name} official website texas"
```

### Step 2: Find board meeting videos
```
web_search: "{district_name} school board meeting videos"
```

### Step 3: Classify the platform
Look for these URL patterns:
- **YouTube**: `youtube.com/channel/`, `youtube.com/@`, `youtube.com/playlist`
- **Swagit**: `*.swagit.com`, `swagit.com/play/`
- **Granicus**: `*.granicus.com`, `granicus.com/player/`
- **BoardDocs**: `go.boarddocs.com/tx/{district}/`
- **Vimeo**: `vimeo.com/`
- **Facebook**: `facebook.com/*/videos`

### Step 4: Record the result
Add a row to `district_video_sources.csv` with these fields:
- district_id, district_name, county, enrollment (from input CSV)
- website_url (official district homepage)
- video_platform (youtube|swagit|granicus|vimeo|facebook|none_found|website_down)
- video_url (direct link to video archive)
- archive_start_year (if visible)
- youtube_channel_id (if applicable)
- notes (any relevant observations)
- confidence (high|medium|low)
- last_checked (2025-01-14)

## Python Helper Script

Use this script to add each district's results:

```python
import csv

def add_district_result(district_data):
    # Read existing
    with open('/home/claude/district_video_sources.csv', 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Add new
    rows.append(district_data)
    
    # Write back
    with open('/home/claude/district_video_sources.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'district_id', 'district_name', 'county', 'enrollment',
            'website_url', 'video_platform', 'video_url', 'archive_start_year',
            'youtube_channel_id', 'notes', 'confidence', 'last_checked'
        ])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Added: {district_data['district_name']}")

# Example usage:
add_district_result({
    'district_id': '015915',
    'district_name': 'Northside ISD',
    'county': 'Bexar',
    'enrollment': '98000',
    'website_url': 'https://www.nisd.net',
    'video_platform': 'youtube',
    'video_url': 'https://www.youtube.com/@NorthsideISD',
    'archive_start_year': '2020',
    'youtube_channel_id': 'UC...',
    'notes': 'Channel has full board meeting playlist',
    'confidence': 'high',
    'last_checked': '2025-01-14'
})
```

## Checkpoint Strategy

**CRITICAL**: Save progress every 25 districts by:
1. Updating `district_video_sources.csv`
2. Logging to `discovery_log.txt`:
   ```python
   with open('/home/claude/discovery_log.txt', 'a') as f:
       f.write(f"[2025-01-14 HH:MM] Checkpoint: Completed districts 1-25. X YouTube, Y Swagit, Z Granicus, N not found\n")
   ```

## Next Districts to Process (in order)

3. Northside ISD (Bexar, 98000)
4. Cypress-Fairbanks ISD (Harris, 94000)
5. Fort Bend ISD (Fort Bend, 94000)
6. Fort Worth ISD (Tarrant, 71000)
7. Garland ISD (Dallas, 70000)
8. Katy ISD (Harris, 67000)
9. North East ISD (Bexar, 67000)
10. Aldine ISD (Harris, 66000)
... and so on

## Expected Platform Distribution (Texas patterns)

Based on preliminary research:
- **YouTube**: 30-40% (most common for large districts)
- **Swagit**: 15-20% (popular in TX)
- **Granicus**: 10-15% (common for large urban districts)
- **None found**: 20-30% (many small districts don't record)

## Common Texas District Website Patterns

- `{name}isd.org`
- `{name}isd.net`
- `www.{cityname}isd.org`
- For multiple cities: `{city1}-{city2}isd.org`

## Tips for Efficient Discovery

1. **Start broad**: Search just district name + "texas"
2. **Check homepage first**: Many link to "Board of Trustees" → "Meeting Videos"
3. **Look for these nav paths**:
   - Board → Meetings → Videos
   - About → Board → Archives
   - Departments → Board Services
4. **If BoardDocs found**: Check if it links to external video platform
5. **Rural districts**: Many under 5,000 enrollment don't have video archives

## Quality Checks

Mark confidence as:
- **high**: Video archive page found, platform clear, recent videos visible
- **medium**: Platform found but archive depth unclear
- **low**: Unclear if page is actually video archive, or old/broken links

## When Stuck

If a district is difficult:
1. Try `web_fetch` on their board meeting page
2. Search for "{district name} board meeting youtube" or "swagit"
3. Check if they mention "live stream" - often points to platform
4. If truly no videos found: Mark as `none_found`, confidence `high`

## Resume Point

You are starting from district #3 (Northside ISD).

The first 2 districts are complete:
- Houston ISD → Granicus
- Dallas ISD → Swagit

## Final Deliverables

When all 50 districts are complete:
1. `district_video_sources.csv` - Complete dataset
2. `discovery_log.txt` - Process log
3. `summary_stats.md` - Platform breakdown (create this)

Example summary_stats.md structure:
```markdown
# Summary Statistics

Total districts: 50
- YouTube: X (XX%)
- Swagit: X (XX%)
- Granicus: X (XX%)
- Other: X (XX%)
- None found: X (XX%)

Top platforms by enrollment coverage:
- Platform X serves Y students across Z districts
```

## Let's Begin!

Start with district #3: Northside ISD
```
web_search: "Northside ISD San Antonio school board meeting videos"
```

Good luck! Remember to checkpoint every 25 districts.
