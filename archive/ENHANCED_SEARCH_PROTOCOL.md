# Enhanced Search Protocol for Texas School District Video Discovery
**Version 2.0** | Last Updated: 2026-01-15

## Overview
This protocol incorporates learnings from processing districts 1-101, addressing false positives and improving accuracy.

## Core Search Strategy

### Phase 1: Vendor-First Search (60% Hit Rate)
Search major video hosting vendors BEFORE checking district websites or YouTube.

**Search queries (run in parallel):**
```
1. site:swagit.com "{District Name}"
2. site:granicus.com "{District Name}"
3. site:boarddocs.com "{District Name}"
4. site:boxcast.tv "{District Name}"  ← NEW: Added 2026-01-15
```

**Why this works:**
- Swagit hosts ~40% of Texas districts
- Granicus hosts ~6% of districts
- BoardDocs hosts ~2% of districts (with actual video capability)
- Boxcast increasingly popular for Texas school livestreams

### Phase 2: YouTube Channel Search
If vendor search fails, search for YouTube presence.

**Search query:**
```
site:youtube.com "{District Name} board meeting"
```

**CRITICAL:** Must extract actual channel URL, not just confirm videos exist.

**Channel URL formats:**
- `https://www.youtube.com/@handlename`
- `https://www.youtube.com/c/channelname`
- `https://www.youtube.com/channel/UC...`

### Phase 3: District Website Check
As last resort, check district's official website.

**Search query:**
```
"{District Name}" Texas board meeting videos
```

Then manually inspect the district's board meeting page.

---

## Verification Gates (NEW)

### Before Marking HIGH Confidence
A district can ONLY be marked HIGH confidence if it passes ALL three gates:

#### Gate 1: Video Player Loads ✅
- Actual embedded video player visible (not just a link or mention)
- Player loads without errors
- For vendor platforms (Swagit/Granicus): Can see video list/grid

#### Gate 2: Archive Depth ✅
- At least **3 meetings** visible in archive
- Most recent meeting < **6 months old** (preferably < 3 months)
- **Record archive_start_year** in CSV

#### Gate 3: Playback Confirmed ✅
For spot-checking (minimum 10% of entries):
- Click a video to verify it actually plays
- Confirm it's a board meeting (not a district promo video)

**If any gate fails:** Mark as MEDIUM or LOW confidence with notes explaining why.

---

## Platform-Specific Verification Rules

### Swagit
- ✅ HIGH: Video list loads, recent meetings visible
- ⚠️ MEDIUM: 404 error or empty archive
- URL format: `https://{districtname}isd.new.swagit.com/`

### Granicus
- ✅ HIGH: Meeting portal loads with video links
- Check both formats: `granicus.com/player` and `.iqm2.com`
- Some use Legistar (same company)

### BoardDocs
- ⚠️ **CAUTION:** BoardDocs can mean two things:
  1. **BoardDocs with videos** (rare): Embedded video player in meeting pages
  2. **BoardDocs agendas only** (common): Just PDF documents
- **NEVER mark HIGH unless you confirm video player exists**
- URL: `https://go.boarddocs.com/tx/{district}/Board.nsf/Public`

### BoardBook
- ⚠️ **HIGH RISK OF FALSE POSITIVES**
- **Default assumption:** Agendas only (NO videos)
- Mark as "none_found" unless EXPLICIT video evidence found
- Known pattern: Districts use BoardBook for agendas + separate platform for videos
- URL format: `https://meetings.boardbook.org/Public/Organization/{id}`

### YouTube
- ✅ HIGH only if you have actual channel URL
- ⚠️ MEDIUM if district mentions YouTube but channel not found
- **MUST extract channel handle:** @username format preferred
- Record in `youtube_channel_id` column

### Website Stream
Split into two categories:

#### website_archive (TRUE archive)
- Has list/grid of past meetings
- Can click and watch previous meetings
- Archive goes back at least 6 months
- **Mark as HIGH**

#### website_livestream_only (NO archive)
- Page says "meetings are livestreamed"
- No recordings of past meetings
- Only upcoming meeting info
- **Mark as MEDIUM or LOW** with note "livestream only, no archive"

### CitizenPortal.ai
- ⚠️ **PAYWALL WARNING**
- Platform DOES have videos but requires paid subscription
- **Mark as LOW confidence** with note "paywalled service"
- Not considered free public access
- URL: `https://citizenportal.ai/`

### Panopto
- Usually hosted by Texas Education Telecommunications Network (TETN)
- URL format: `https://tetnvideo.hosted.panopto.com/`
- ✅ HIGH if video list visible

### Diligent
- Previously called "BoardEffect"
- URL format: `https://{district}.diligent.community/Portal/`
- Check for "Board Meeting Live Stream" and "Previous Board Meeting Videos" sections

---

## iframe Extraction Method (YouTube Channels)

When district website embeds YouTube videos but doesn't link to channel:

### Method 1: Inspect Embedded Player
1. Visit district's board meeting page
2. Look for embedded YouTube iframe
3. Extract channel ID from iframe src attribute:
   ```html
   <iframe src="https://www.youtube.com/embed/VIDEO_ID"></iframe>
   ```
4. Visit the video URL: `https://www.youtube.com/watch?v=VIDEO_ID`
5. Click channel name to get channel URL

### Method 2: View Page Source
1. Right-click → "View Page Source"
2. Search for "youtube.com/embed" or "youtube.com/watch"
3. Extract video ID and follow method 1

### Method 3: Direct YouTube Search
```
site:youtube.com "{District Name} ISD board meeting"
```
Filter results to channels (not individual videos)

---

## Archive Depth Verification

### Required for HIGH Confidence
Record `archive_start_year` for all Swagit, Granicus, and BoardDocs entries.

**How to find:**
1. Swagit: Scroll to bottom of video list, check oldest date
2. Granicus: Look for date range selector or oldest meeting
3. Website archives: Check for "archive" or "past meetings" section with years

**Recording format:**
- Year only: `2021`
- If unclear: Leave blank and note in comments

---

## Common Pitfalls to Avoid

### ❌ DON'T DO THIS:
1. **Marking BoardBook as HIGH** without verifying videos exist
2. **Assuming "livestream" means archive exists** (many only stream live, no recordings)
3. **Recording YouTube as platform** without actual channel URL
4. **Marking HIGH based on "mentioned"** (must verify actual player loads)
5. **Ignoring paywall warnings** (CitizenPortal.ai, some BoardDocs)
6. **Not checking recent content** (archive may be abandoned)

### ✅ DO THIS INSTEAD:
1. Always check BoardBook entries directly (assume no videos)
2. Distinguish between live streaming and archiving
3. Extract actual YouTube channel @handles
4. Verify video player actually loads
5. Note paywalled services clearly
6. Check most recent meeting date

---

## Updated Confidence Level Definitions

### HIGH ✅
- Video player loads and displays content
- At least 3 meetings visible
- Most recent meeting < 6 months old
- Archive depth recorded (if applicable)
- FREE public access (no paywall)

### MEDIUM ⚠️
- Platform mentioned but not verified
- YouTube referenced but channel URL not found
- Livestream page exists but archive unclear
- Website has video section but content not confirmed

### LOW ❌
- Only document portals (BoardBook/BoardDocs agendas)
- Paywalled services (CitizenPortal.ai)
- Historical mentions only (COVID-era links)
- No video archive found after thorough search

---

## CSV Column Standards

### video_platform
Allowed values:
- `swagit`
- `granicus`
- `youtube`
- `boarddocs` (only if videos confirmed)
- `website_archive` (has past recordings)
- `website_livestream_only` (live only)
- `panopto`
- `diligent`
- `citizenportal` (note paywall in comments)
- `boxcast` (NEW)
- `audio_only` (rare, audio recordings only)
- `none_found`

### video_url
- For vendors: Direct link to district's video portal
- For YouTube: Channel URL (not individual video)
- For websites: Page with video player/archive
- For none_found: BoardBook URL (if exists) or district homepage

### youtube_channel_id
- Preferred format: `@handlename`
- Alternative: Full URL `https://www.youtube.com/@handlename`
- Channel ID format: `UCxxx...` (if @handle not available)

### notes
Include:
- Archive depth findings
- Paywall warnings
- Verification status
- Platform quirks (e.g., "Uses BoardBook for agendas")

### confidence
- `high` - Verified and passes all gates
- `medium` - Mentioned but not fully verified
- `low` - No videos or paywall/historical only

### last_checked
- Format: `YYYY-MM-DD`
- Update on every verification

---

## Batch Processing Guidelines

### Recommended Batch Size: 10-15 districts

**For each batch:**
1. Run all vendor searches in parallel (4 simultaneous WebSearch calls)
2. Process results and identify platforms
3. Verify each finding through verification gates
4. Record findings in CSV with detailed notes
5. Mark todo items as completed
6. Update progress log

**Quality over speed:**
- Take time to verify each entry properly
- Don't batch-complete without verification
- Spot-check previous entries periodically

---

## Error Recovery

### If search fails or unclear:
1. Try alternative search terms:
   - "{District Name} board meetings"
   - "{District Name} trustees video"
   - "{District Name} livestream"
2. Check district's "Board of Trustees" page directly
3. Look for "Watch meetings" or "Video archive" links in nav
4. If truly not found: Mark as "none_found" with LOW confidence

### If platform loads but seems abandoned:
- Check date of most recent meeting
- If > 1 year old: Downgrade to MEDIUM with note
- If > 2 years old: Consider LOW with note "archive appears abandoned"

---

## Testing Protocol (Quality Assurance)

### Every 25 districts, run spot-check:
1. Pick 5 random HIGH confidence entries
2. Click links to verify they still work
3. Confirm video player loads
4. Check most recent meeting date
5. Update any entries that fail verification

### Red flags requiring re-verification:
- Entry marked HIGH but no archive_start_year
- BoardBook marked as anything other than "none_found"
- YouTube without channel URL in youtube_channel_id
- website_stream without clarification (archive vs livestream_only)

---

## Known Issues & Solutions

### Issue: YouTube channel exists but URL not found
**Solution:** Use iframe extraction method or manual search

### Issue: District mentions videos but none visible
**Solution:** Mark as LOW, don't assume videos exist

### Issue: BoardBook appears to have videos
**Solution:** Verify carefully - likely embedded links to separate platform

### Issue: CitizenPortal.ai has coverage
**Solution:** Mark as LOW with paywall note

### Issue: Swagit link 404s
**Solution:** Try alternative URL formats (.new vs .v3 vs no subdomain)

### Issue: Archive depth unclear
**Solution:** Leave archive_start_year blank, note in comments

---

## Success Metrics

### Target Success Rate: ~80-85%
- Current rate after verification: 81%
- Expect similar rates in future batches
- Not all districts record meetings (budget/policy constraints)

### Quality Metrics:
- False positive rate: < 5%
- YouTube channel URL capture rate: > 80%
- Archive depth recorded: > 90% of HIGH confidence entries
- Verification gate pass rate: 100% of HIGH confidence

---

## Revision History

- **v2.0 (2026-01-15):** Added verification gates, Boxcast vendor, BoardBook warnings, CitizenPortal.ai paywall note, iframe extraction method, website_stream split
- **v1.0 (2026-01-14):** Initial protocol based on first 66 districts

---

**Remember:** Accuracy > Speed. Better to have 80% with HIGH confidence than 95% with false positives.
