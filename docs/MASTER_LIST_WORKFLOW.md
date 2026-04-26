# TEA Master List Integration Workflow

This guide explains how to integrate the authoritative TEA master district list to prevent duplicates and expand your dataset systematically.

## Overview

**Problem:** We had 22 duplicates because districts appeared with multiple IDs from different sources.

**Solution:** Use TEA's authoritative master list as the single source of truth for all district IDs, names, and enrollment data.

---

## Complete Workflow

### Step 1: Download TEA Master List (MANUAL)

**Time:** 2-3 minutes

1. Visit: https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/DownloadFile.aspx
2. Select "Download School and District Data File"
3. Choose sort: "District Number"
4. Click "Download File"
5. Save as: `data/tea_master_districts_raw.csv`

See detailed instructions: [DOWNLOAD_TEA_MASTER.md](../DOWNLOAD_TEA_MASTER.md)

### Step 2: Process TEA Data

**Script:** `scripts/process_tea_master.py`

**What it does:**
- Extracts districts only (filters out individual schools)
- Cleans district IDs (removes apostrophes, standardizes format)
- Removes duplicates
- Creates clean master list

**Run:**
```bash
python3 scripts/process_tea_master.py
```

**Output:** `data/tea_districts_master_clean.csv` (~1,208 districts)

**Expected output:**
```
Processing complete!
  Total rows processed: ~9,000+
  Districts found: ~1,250
  Duplicates removed: ~40
  Unique districts: ~1,208
```

### Step 3: Merge with Verified Data

**Script:** `scripts/merge_verified_with_master.py`

**What it does:**
- Merges your 172 verified districts with TEA master list
- Uses TEA data as authoritative for names/counties/enrollment
- Preserves all video platform data from verified dataset
- Creates complete dataset with all 1,208 districts
- Generates validation report

**Run:**
```bash
python3 scripts/merge_verified_with_master.py
```

**Outputs:**
- `data/districts_complete.csv` (~1,208 rows)
  - 172 rows with `video_status: verified`
  - ~1,036 rows with `video_status: pending`
- `data/merge_report.md` (validation report)

**Review the report:**
```bash
cat data/merge_report.md
```

Look for:
- Districts in verified but NOT in TEA (potential bad IDs)
- Name/county mismatches (TEA is authoritative)
- Overall completion percentage

### Step 4: Validate Before Adding New Districts

**Script:** `scripts/validate_district_id.py`

**Usage examples:**

**Validate a district ID:**
```bash
python3 scripts/validate_district_id.py 101912
```

Output:
```
✓ Valid District ID: 101912
District: Houston ISD
County: Harris
Enrollment: 187000
✓ Status: READY TO PROCESS
```

**Search by district name:**
```bash
python3 scripts/validate_district_id.py "Katy ISD" --name
```

**Check progress:**
```bash
python3 scripts/validate_district_id.py --stats
```

### Step 5: Update Video Discovery Workflow

**Before adding any new district:**

1. **Validate ID first:**
   ```bash
   python3 scripts/validate_district_id.py [district_id]
   ```

2. **Check if already processed:**
   - Script will flag if district already in dataset
   - Prevents duplicate entries

3. **Use canonical ID:**
   - Always use the district ID from TEA master
   - If you find alternate IDs, note them but don't add separately

4. **Add to complete dataset:**
   - Work from `districts_complete.csv` going forward
   - Update `video_status` from "pending" to "verified"
   - Add video platform data

---

## File Structure After Integration

```
data/
├── tea_master_districts_raw.csv      # Downloaded from TEA (keep for reference)
├── tea_districts_master_clean.csv    # Processed TEA master (~1,208 districts)
├── districts_verified.csv             # Original 172 verified (archived)
├── districts_complete.csv             # NEW: Complete dataset (~1,208 districts)
├── merge_report.md                    # Validation report
└── youtube_channels.csv               # YouTube metadata

scripts/
├── process_tea_master.py              # Step 2: Clean TEA data
├── merge_verified_with_master.py      # Step 3: Merge datasets
└── validate_district_id.py            # Step 4: Validation tool
```

---

## Integration with Existing Scripts

Your existing automation scripts still work:

```bash
# Swagit automation (now validates against TEA master)
python3 scripts/swagit_matcher.py --batch 173-200

# YouTube API search (validates IDs first)
python3 scripts/youtube_bulk_finder.py --missing

# URL validation
python3 scripts/validate_urls.py
```

**Key change:** Before adding results to CSV, validate district IDs:
```python
from scripts.validate_district_id import validate_district_id

result = validate_district_id('101912')
if result['valid'] and not result['already_verified']:
    # Safe to add this district
    pass
```

---

## Preventing Future Duplicates

### For Manual Entry

**Always:**
1. Run validation script first
2. Check merge report for existing entries
3. Use TEA's canonical district ID
4. Cross-reference county matches

**Never:**
- Add districts without validating ID
- Use alternate IDs without checking TEA master
- Assume spelling variations are different districts

### For Automated Scripts

**Add validation step:**
```python
# Before processing a district
validator = DistrictValidator()
result = validator.validate_id(district_id)

if not result['valid']:
    log(f"Skipping invalid ID: {district_id}")
    continue

if result['already_verified']:
    log(f"Skipping duplicate: {district_id}")
    continue

# Proceed with video discovery
```

---

## Quarterly Maintenance

**Every 3 months:**

1. **Download fresh TEA master list**
   - New districts may be created
   - Districts may consolidate or close
   - Enrollment data updates

2. **Re-run processing script**
   ```bash
   python3 scripts/process_tea_master.py
   ```

3. **Check for new districts**
   ```bash
   diff data/tea_districts_master_clean.csv data/tea_districts_master_clean_old.csv
   ```

4. **Update complete dataset**
   ```bash
   python3 scripts/merge_verified_with_master.py
   ```

---

## Progress Tracking

With the complete dataset, you can now accurately track progress:

```python
import csv

with open('data/districts_complete.csv') as f:
    reader = csv.DictReader(f)
    total = 0
    verified = 0
    for row in reader:
        total += 1
        if row['video_status'] == 'verified':
            verified += 1

print(f"Progress: {verified}/{total} ({verified/total*100:.1f}%)")
```

Current status: **172/1,208 (14.2%)**

---

## Troubleshooting

### "TEA master file not found"
**Solution:** Run Step 1 (download) and Step 2 (process) first

### "District ID not found in TEA master"
**Solution:** Double-check the ID format (6 digits). The district may not exist or may have been consolidated.

### "District already processed"
**Solution:** Check `districts_complete.csv` - this district already has video data

### Merge report shows mismatches
**Solution:** This is expected. TEA data is authoritative - mismatches are automatically resolved in merged dataset.

---

## Benefits of This Approach

✅ **No more duplicates** - Single source of truth for district IDs
✅ **100% coverage** - Know exactly which districts remain to process
✅ **Data quality** - TEA enrollment/county data is authoritative
✅ **Progress tracking** - Measure completion against known total
✅ **Scalable** - Foundation for processing remaining ~1,036 districts
✅ **Validation** - Prevent bad IDs before they enter dataset

---

*Last updated: 2026-01-15*
