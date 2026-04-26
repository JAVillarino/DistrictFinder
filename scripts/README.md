# Texas School Districts - Automation Scripts

**Created:** 2026-01-15
**Purpose:** Automate 70-75% of district video discovery

---

## 📁 Files in This Directory

### Core Scripts
1. **swagit_matcher.py** - Tests Swagit URL patterns (handles 35% of districts)
2. **youtube_bulk_finder.py** - Uses YouTube Data API to find channels (10-15%)
3. **granicus_matcher.py** - Tests Granicus URL patterns (5-7%)
4. **validation_pipeline.py** - Validates all entries, calculates confidence scores

### Support Scripts
5. **progress_tracker.py** - Central state management, progress dashboard

### Configuration
- **config.json** - API keys and thresholds (create from config.example.json)
- **config.example.json** - Template configuration (safe to commit)

---

## 🚀 Quick Start

```bash
# Install dependencies (from repo root)
pip install -r ../requirements.txt

# Configure YouTube API key
cp config.example.json config.json
# Edit config.json and add your key from console.cloud.google.com

# Test on first batch
python swagit_matcher.py --batch 125-155
python youtube_bulk_finder.py --missing
python validation_pipeline.py --batch 125-155

# Check progress
python progress_tracker.py --status
```

---

## 📖 Full Documentation

See **AGENT_INSTRUCTIONS.md** in parent directory for complete usage instructions.

---

## 🎯 Expected Performance

- **Time Savings:** 43% faster (70 hours → 40 hours)
- **Accuracy:** 94%+ maintained
- **Automation Rate:** 70-75% of districts handled by scripts
- **Agent Review:** 25-30% requiring manual verification

---

## 🔧 Common Commands

```bash
# Run all matchers on a batch
python swagit_matcher.py --batch 125-175
python granicus_matcher.py --batch 125-175
python youtube_bulk_finder.py --batch 125-175 --limit 30

# Validate results
python validation_pipeline.py --batch 125-175

# Check what needs agent review
cat agent_queue.csv

# View progress
python progress_tracker.py --status
```

---

## ⚠️ Important Notes

- **YouTube API:** Limited to 10,000 quota/day (100 searches)
- **Rate Limiting:** Scripts respect 0.5s delay between requests
- **Resumability:** All scripts save progress every 10 districts
- **Backups:** Always backup CSV before bulk operations

---

## 📊 Script Output Files

- `swagit_progress.json` - Swagit matcher state
- `youtube_progress.json` - YouTube finder state (includes quota tracking)
- `granicus_progress.json` - Granicus matcher state
- `project_state.json` - Overall project progress
- `agent_queue.csv` - Districts needing manual review
- `*.log` - Detailed execution logs

---

**For detailed workflow instructions, see AGENT_INSTRUCTIONS.md in parent directory**
**Historical documentation available in archive/HYBRID_WORKFLOW_GUIDE.md**
