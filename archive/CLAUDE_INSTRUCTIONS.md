# Claude Code Instructions - Texas Districts Video Discovery Project

## Project Overview

**Goal**: Discover and document video/audio archive URLs for all ~1,024 Texas school board meetings. This is a data collection project where the data doesn't exist in any centralized location, so Claude is being used to create this dataset.

**Critical Requirement**: ONLY record URLs that actually contain playable video or audio content. Do NOT record meeting portals that only have agendas/documents without videos.

## Current Status

- **Completed**: Districts 1-101 (Batch 1 & 2)
- **Next**: Districts 102-201 (Batch 3)
- **Ultimate Goal**: All ~1,024 Texas school districts

## Enhanced Search Protocol

### Phase 1: Vendor-First Search (WITH BOXCAST)

Search ALL major video platforms first:

```
site:swagit.com OR site:granicus.com OR site:boarddocs.com OR site:boxcast.tv OR site:youtube.com "{District Name}" board meeting
```

**Why vendor-first?** These platforms host 70%+ of Texas district videos. Checking them first saves time and has highest success rate.

**Boxcast Addition**: Increasingly popular for Texas school livestreams. Don't skip this.

### Phase 2: YouTube Channel Extraction (IF YOUTUBE MENTIONED)

If search results mention YouTube but don't provide channel URL:

1. **Fetch the district's board meeting page** using WebFetch
2. **Look for iframe src** containing `youtube.com/embed/{VIDEO_ID}`
3. **Extract channel from video**:
   - Use the video ID to construct: `https://www.youtube.com/watch?v={VIDEO_ID}`
   - Fetch that page and look for channel link in page source
4. **Record in @handle or /channel/UC... format**
5. **If no iframe found**: Note as "YouTube mentioned, channel URL not found" and mark confidence as MEDIUM

### Phase 3: District Website Direct Check

Only if vendor searches fail:

```
"{District Name}" Texas board meeting videos archive
```

Then fetch the district's official website and look for:
- "Board Meetings" or "Board of Trustees" page
- Livestream or video archive links
- Embedded video players

### Phase 4: Verification Gate (MANDATORY BEFORE HIGH CONFIDENCE)

Before marking any entry as HIGH confidence, you MUST verify:

✅ **Video player loads on the page** (not just a link that says "videos available")
✅ **At least 3 meetings visible** in the archive/playlist
✅ **Most recent meeting is < 6 months old** (shows active maintenance)
✅ **Archive start year recorded** (scroll to oldest video for Swagit/Granicus)

If you cannot verify all 4 criteria, mark as MEDIUM or LOW confidence.

## Platform-Specific Verification Rules

### Swagit
- **HIGH confidence IF**: Can see video grid with multiple meetings and dates
- **Must record**: archive_start_year by scrolling to oldest video
- **Verify**: Recent meetings are present (< 6 months)

### Granicus
- **HIGH confidence IF**: Meeting list shows "Video" or "Watch" buttons
- **Must record**: archive_start_year
- **Verify**: Videos actually play (not just agenda PDFs)

### BoardBook / BoardDocs
⚠️ **HIGH RISK OF FALSE POSITIVES**

**Verification required**:
1. Click into a recent meeting entry
2. Look for "Video", "Recording", or embedded video player
3. Check if there's an external video link (YouTube, Vimeo, etc.)

**If agendas/PDFs only**: Mark as `none_found` with note "BoardBook agendas only"

**Many BoardBook portals do NOT have videos** - they're just document repositories.

### YouTube
- **Preferred format**: @handle (e.g., `@austinisd`) or /channel/UC... (e.g., `/channel/UCcc_lr7Xzmq48dYB17CM48g`)
- **If channel URL not found**: Mark confidence as MEDIUM
- **Verify**: Channel has board meeting playlist with 3+ videos
- **Record**: Full YouTube URL in video_url column AND channel handle in youtube_channel_id column

### Website Stream / Website Archive

⚠️ **SPLIT THIS CATEGORY**:

**website_archive**:
- Has playable past meeting videos embedded on district site
- Can see video player with multiple meetings
- Archive is navigable

**website_livestream_only**:
- District mentions livestreaming meetings
- No archive of past meetings found
- Or archive requires login/authentication

**If unclear which**: Fetch the page and check if you can see past meeting videos.

### Boxcast
- Usually has format: `boxcast.tv/channel/{CHANNEL_ID}`
- Verify by checking if channel page loads with video list
- Record archive_start_year

## CSV Output Format

```csv
district_id,district_name,county,enrollment,website_url,video_platform,video_url,archive_start_year,youtube_channel_id,notes,confidence,last_checked
```

**Platform values**:
- swagit
- granicus
- boarddocs
- boardbook (only if videos confirmed)
- boxcast
- youtube
- website_archive (past videos available)
- website_livestream_only (live only, no archive)
- panopto
- diligent
- citizenportal
- audio_only (special case)
- none_found

**Confidence values**:
- **high**: All 4 verification criteria met
- **medium**: Videos mentioned but not fully verified, or YouTube channel URL not found
- **low**: No videos found, audio only, or agendas-only portal

## Batch Processing Guidelines

1. **Process in batches of 10-15 districts** to maintain quality
2. **Update CSV after each batch** (don't wait until all complete)
3. **Use TodoWrite to track progress** for each batch
4. **Mark todos complete immediately** after finishing each district (don't batch completions)
5. **Take verification seriously** - it's better to mark MEDIUM than to record false positives

## Common Pitfalls to Avoid

❌ **Don't assume BoardBook = videos** (most are agendas only)
❌ **Don't mark HIGH without verifying** all 4 gate criteria
❌ **Don't record "meeting portal" URLs** that don't actually have videos
❌ **Don't skip archive_start_year** for Swagit/Granicus
❌ **Don't leave YouTube channels as generic district URLs** (need actual channel handle)
❌ **Don't conflate "livestream mentioned" with "archive exists"**

## Quality Control Metrics

Track these throughout the session:

- **Discovery rate**: % of districts with videos/audio found
- **High confidence rate**: % marked as HIGH confidence
- **Platform distribution**: Breakdown by vendor
- **YouTube channel URL success rate**: % of YouTube districts with actual @handle found
- **False positive catches**: BoardBook/website_stream entries corrected during verification

## Files to Update

1. **district_video_sources.csv** - Main database (append after each batch)
2. **discovery_log.txt** - Progress log (timestamp each batch completion)
3. **SESSION_STATUS.md** - Overall project status (update at end of session)
4. **RESUME_HERE.md** - Resume instructions for next session (update at end)

## Session Continuation Template

When resuming from a previous session, always read:

1. `/Users/joelvillarino/Downloads/TexasDistricts/RESUME_HERE.md` - Where to start
2. `/Users/joelvillarino/Downloads/TexasDistricts/SESSION_STATUS.md` - Current status
3. `/Users/joelvillarino/Downloads/TexasDistricts/texas_districts_starter.csv` - Source list

Then:
1. Create todo list for the batch you're processing
2. Apply enhanced search protocol with verification gate
3. Update CSV after each batch
4. Update all status files at end of session

## Summarization Instructions for Context Continuation

When this conversation needs to be summarized for the next Claude session, include:

### 1. Primary Request and Intent
- Original project goal and current session objectives
- Critical user feedback throughout session (with quotes)
- What the user wants accomplished

### 2. Key Technical Concepts
- Search protocol and verification methodology
- Platform types and confidence levels
- CSV structure and batch processing approach
- Verification gate criteria

### 3. Files and Code Sections
- List each file with purpose, current state, structure
- Include relevant code/data snippets showing edits made
- Note line numbers where significant changes occurred

### 4. Errors and Fixes
- Document each error type encountered
- User feedback about quality issues
- Fixes applied and fixes still needed
- Root cause analysis

### 5. Problem Solving
- Solved problems with their solutions
- Ongoing troubleshooting issues
- Systematic approaches being developed

### 6. All User Messages
- Chronological list of every user message
- Preserve exact wording, especially for feedback/corrections

### 7. Pending Tasks
- Numbered list of tasks not yet completed
- Include specific details (which districts, what needs verification, etc.)

### 8. Current Work
- What was being worked on immediately before summary
- Which files were being edited
- What specific task was in progress

### 9. Optional Next Step
- Concrete next action to take when conversation resumes
- Direct quote from conversation showing what user wants
- Specific command or tool to use first

## Data Quality Standards

**Before marking HIGH confidence, ask yourself**:

1. Did I actually see a video player on the page?
2. Can I see at least 3 meetings in the archive?
3. Is the most recent meeting less than 6 months old?
4. Did I record the archive start year (for Swagit/Granicus)?

**If you can't answer YES to all 4**: Mark as MEDIUM or LOW.

## YouTube Channel Discovery - Systematic Approach

If a district claims to have YouTube but you can't find the channel URL:

1. **Search**: `site:youtube.com "{District Name}" board meeting`
2. **If that fails**: `"{District Name}" site:youtube.com @`
3. **If still no URL**: Fetch district's board meeting page
4. **Look for**: `<iframe src="https://www.youtube.com/embed/{VIDEO_ID}"`
5. **Extract**: Video ID from iframe
6. **Visit**: `https://www.youtube.com/watch?v={VIDEO_ID}`
7. **Extract**: Channel URL from video page source
8. **Record**: Both the video_url (district page) and youtube_channel_id (@handle)

**If all fails**: Mark confidence as MEDIUM with note "YouTube mentioned, channel URL not found"

---

**Last Updated**: 2026-01-15
**Version**: 2.0 (Enhanced with verification gate and Boxcast)
