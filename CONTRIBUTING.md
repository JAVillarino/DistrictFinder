# Contributing - Agent Workflow Guide

This project is designed to be extended by AI coding agents (like Claude Code). This document explains how to contribute effectively.

## For AI Agents

### Starting a Session

1. **Read STATE.md first** - Contains current progress, known issues, and next actions
2. **Load AGENT_INSTRUCTIONS.md** - Contains the full protocol and rules
3. **Check data/districts_complete.csv** - See what's already processed (filter `video_status: pending`)

### Standard Workflow

```
1. Read STATE.md for current status
2. Identify next batch of districts from data/districts_complete.csv (video_status: pending)
3. Process 10-15 districts per session
4. Update data/districts_complete.csv with results
5. Update STATE.md with new progress
6. Commit changes with descriptive message
```

### Quality Standards

Before marking a district as HIGH confidence:
- Video player actually loads (not just a link)
- At least 3 meetings visible
- Most recent meeting < 6 months old
- Free public access (no paywall)

### Common Mistakes to Avoid

1. **BoardBook false positives** - BoardBook usually means agendas only, not videos
2. **Missing YouTube URLs** - Don't mark YouTube as HIGH without actual channel URL
3. **Assuming livestream = archive** - Many districts only stream live, don't record
4. **CitizenPortal.ai** - This is paywalled, mark as LOW

### Commit Messages

Use this format:
```
Add districts 131-145 (15 districts)

- Swagit: 6 districts
- YouTube: 3 districts (2 channels found)
- None found: 4 districts
- Website archive: 2 districts

Updated STATE.md with progress (139/1024, 14%)
```

## For Human Contributors

### Setup

```bash
# Clone the repo
git clone <repo-url>
cd texas-districts-video-discovery

# Install dependencies
pip install -r requirements.txt

# Copy config template and add your API key
cp scripts/config.example.json scripts/config.json
# Edit scripts/config.json with your YouTube API key
```

### Running Scripts

```bash
cd scripts

# Test Swagit URLs for a batch
python swagit_matcher.py --batch 131-150

# Find YouTube channels
python youtube_bulk_finder.py --batch 131-150

# Validate all URLs
python validation_pipeline.py
```

### Manual Verification

For districts that scripts can't handle:
1. Visit the district's board meeting page
2. Look for embedded video player
3. Verify 3+ meetings available
4. Check most recent meeting date
5. Update CSV manually

### Pull Request Process

1. Create feature branch: `git checkout -b batch-131-150`
2. Process districts and update files
3. Run validation: `python scripts/validation_pipeline.py`
4. Commit with descriptive message
5. Push and create PR with summary of findings

## Data Quality

### Spot Checks

Every 50 districts, verify 5 random HIGH confidence entries:
- Click the video URL
- Confirm video loads
- Check archive depth is accurate

### Known Issues

Track in STATE.md:
- Missing YouTube channel URLs
- Entries needing re-verification
- Platform changes or migrations

## Questions?

Open an issue or check the archive/ folder for historical documentation.
