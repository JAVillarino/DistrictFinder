# Texas Districts Video Discovery - Agent Instructions

## Quick Start

1. Read `STATE.md` for current progress and known issues
2. **VALIDATE district ID first** (see Validation section below)
3. Load `data/districts_complete.csv` for complete district list
4. Resume from district noted in STATE.md
5. Append results to `data/districts_complete.csv`
6. Update `STATE.md` after each batch

---

## ⚠️ VALIDATION REQUIREMENT (Added 2026-01-15)

**CRITICAL:** Always validate district IDs before processing to prevent duplicates.

### Before Processing Any District

Run validation script:
```bash
python3 scripts/validate_district_id.py [district_id]
```

**Example:**
```bash
$ python3 scripts/validate_district_id.py 101912
✓ Valid District ID: 101912
District: Houston ISD
County: Harris
✓ Status: READY TO PROCESS
```

**If already processed:**
```bash
⚠️ Status: ALREADY PROCESSED
This district is already in the verified dataset.
```
→ **SKIP this district** - Don't add duplicate entry!

### Validation Rules

1. **District ID must be in TEA master list** (validates against official source)
2. **Check for duplicates** (prevents re-processing same district)
3. **Use canonical ID** (TEA's official district ID only)
4. **Never add alternate IDs** (some districts have multiple IDs - always use TEA's version)

### Why This Matters

We previously had **22 duplicate entries** because districts appeared with multiple IDs from different sources. This validation step ensures:
- No duplicate processing
- Official TEA district IDs used
- Data quality maintained
- Progress tracking accurate

**See full workflow:** `docs/MASTER_LIST_WORKFLOW.md`

---

## Search Protocol (v2.0)

### Phase 1: Vendor-First Search (60% hit rate)

Run these searches in parallel for each district:

```
1. site:swagit.com "{District Name}"
2. site:granicus.com "{District Name}"
3. site:boarddocs.com "{District Name}"
4. site:boxcast.tv "{District Name}"
```

**Why this works:**
- Swagit hosts ~40% of Texas districts
- Granicus hosts ~6%
- BoardDocs hosts ~2% (with actual video capability)
- Boxcast increasingly popular for livestreams

### Phase 2: YouTube Channel Search

If vendor search fails:

```
site:youtube.com "{District Name} board meeting"
```

**CRITICAL:** Must extract actual channel URL:
- `https://www.youtube.com/@handlename`
- `https://www.youtube.com/c/channelname`
- `https://www.youtube.com/channel/UC...`

### Phase 3: District Website Check

As last resort, visit district's board meeting page directly.

---

## Verification Gates

Before marking HIGH confidence, ALL three gates must pass:

### Gate 1: Video Player Loads
- Actual embedded video player visible (not just a link)
- Player loads without errors
- For vendor platforms: Can see video list/grid

### Gate 2: Archive Depth
- At least 3 meetings visible
- Most recent meeting < 6 months old
- Record `archive_start_year` in CSV

### Gate 3: Free Access
- No login required
- No paywall (CitizenPortal.ai = paywall)
- Publicly accessible

**If any gate fails:** Mark as MEDIUM or LOW with notes.

---

## Platform-Specific Rules

### Swagit
- HIGH: Video list loads, recent meetings visible
- URL format: `https://{districtname}isd.new.swagit.com/`

### Granicus
- HIGH: Meeting portal loads with video links
- Check formats: `granicus.com/player` and `.iqm2.com`

### BoardDocs
- CAUTION: Can mean videos OR agendas only
- NEVER mark HIGH unless video player confirmed
- URL: `https://go.boarddocs.com/tx/{district}/Board.nsf/Public`

### BoardBook
- HIGH RISK OF FALSE POSITIVES
- Default assumption: Agendas only (NO videos)
- Mark as "none_found" unless EXPLICIT video evidence
- URL: `https://meetings.boardbook.org/Public/Organization/{id}`

### YouTube
- HIGH only with actual channel URL
- MEDIUM if YouTube mentioned but channel not found
- Record channel handle in `youtube_channel_id` column

### Website Archives
- **website_archive**: Has list of past meetings, can watch recordings
- **website_livestream_only**: Live stream page, no recordings
- Only mark HIGH if archive confirmed

### CitizenPortal.ai
- PAYWALL WARNING - Not free public access
- Mark as LOW with note "paywalled service"

---

## Output Schema

CSV columns for `data/districts_complete.csv`:

```csv
district_id,district_name,county,enrollment,website_url,video_platform,video_url,archive_start_year,youtube_channel_id,notes,confidence,last_checked
```

### Platform Values
- `swagit`
- `granicus`
- `youtube`
- `boarddocs` (only if videos confirmed)
- `website_archive` (has past recordings)
- `website_livestream_only` (live only)
- `panopto`
- `diligent`
- `citizenportal` (note paywall)
- `boxcast`
- `audio_only`
- `none_found`

### Confidence Levels
- `high` - Verified, passes all gates
- `medium` - Mentioned but not fully verified
- `low` - No videos, paywall, or historical only

---

## Checkpointing

### Every 10-15 districts:
1. Save results to `data/districts_output.csv`
2. Update `STATE.md` with current progress
3. Note any issues or patterns discovered

### Every 25 districts:
1. Run spot-check on 5 random HIGH entries
2. Verify URLs still work
3. Update quality metrics in STATE.md

---

## Common Pitfalls

### DON'T:
- Mark BoardBook as HIGH without verifying videos exist
- Assume "livestream" means archive exists
- Record YouTube without actual channel URL
- Mark HIGH based on "mentioned" (must verify player loads)
- Ignore paywall warnings

### DO:
- Always check BoardBook entries directly
- Distinguish between live streaming and archiving
- Extract actual YouTube channel @handles
- Verify video player actually loads
- Note paywalled services clearly

---

## YouTube Channel Extraction

When district website embeds YouTube but doesn't link to channel:

### Method 1: Inspect Embedded Player
1. Visit district's board meeting page
2. Look for embedded YouTube iframe
3. Extract video ID from iframe src
4. Visit video URL, click channel name

### Method 2: View Page Source
1. Right-click → "View Page Source"
2. Search for "youtube.com/embed" or "youtube.com/watch"
3. Extract video ID and follow Method 1

### Method 3: Direct YouTube Search
```
site:youtube.com "{District Name} ISD board meeting"
```

---

## Automated Scripts

Use scripts in `scripts/` folder to speed up processing:

```bash
# Test Swagit URLs for a batch
python scripts/swagit_matcher.py --batch 131-150

# Test Granicus patterns
python scripts/granicus_matcher.py --batch 131-150

# Find YouTube channels via API
python scripts/youtube_bulk_finder.py --batch 131-150

# Validate all URLs
python scripts/validation_pipeline.py

# Check progress
python scripts/progress_tracker.py --status
```

Scripts handle ~70% of districts automatically. Use agent for:
- Website archives (custom implementations)
- BoardBook verification
- YouTube iframe extraction
- Ambiguous cases

---

## Quick Resume Prompts

### Option A: Continue Processing (Recommended)
```
Continue Texas school districts video discovery.
Check STATE.md for current progress.
Next: Process next batch of districts from data/districts_complete.csv where video_status is pending.
Apply enhanced protocol with verification gates.
Update data/districts_complete.csv with results.
Update STATE.md when done.
```

### Option B: YouTube Channel Hunt
```
Find missing YouTube channel URLs for 10 districts in STATE.md.
Use iframe extraction method.
Update data/districts_output.csv with channel handles.
Upgrade confidence from MEDIUM to HIGH when found.
```

### Option C: Quality Verification
```
Spot-check 10 random HIGH confidence entries.
Verify URLs work and videos play.
Check archive depth accuracy.
Downgrade any false positives.
Update STATE.md with findings.
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Districts processed | 1,060 |
| Video URL found | 70-75% |
| HIGH confidence | 80%+ of found URLs |
| False positive rate | <5% |
| YouTube URL capture | 90%+ |
| Archive depth recorded | 90%+ |

---

**Remember:** Quality > Speed | Verify Before Marking HIGH | BoardBook = Agendas Only
