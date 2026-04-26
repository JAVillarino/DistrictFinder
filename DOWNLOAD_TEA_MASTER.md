# How to Download TEA Master District List

**⚠️ MANUAL STEP REQUIRED**: The TEA AskTED system requires interactive download through a web browser.

Follow these steps to get the authoritative Texas district list:

## Step 1: Access TEA AskTED Download Page

Visit: **https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/DownloadFile.aspx**

## Step 2: Select Download Option

On the AskTED Download page, you'll see several download options:
- ✅ **Choose: "Download School and District Data File"** or **"Download All Schools and Districts"**

## Step 3: Choose Sort Option

From the dropdown menu, select your preferred sort order:
- **Recommended: "District Number"** (for easier processing)
- Alternatives: District Name, County, Region

## Step 4: Download the File

1. Click the **"Download File"** button
2. The system will generate the CSV file (may take a few seconds)
3. Your browser will download a CSV file (typically named something like `AskTED_Download.csv`)

## Step 5: Save the File

**IMPORTANT**: Rename and save the downloaded file to:
```
/Users/joelvillarino/Downloads/TexasDistricts/data/tea_master_districts_raw.csv
```

## Expected File Contents

The CSV file should contain:
- **All ~9,000+ rows** (includes both schools and districts)
- **District rows**: Will have district type in name (ISD, CISD, etc.)
- **Columns** (names may vary):
  - District Number (or CO-DIST, CDN)
  - District Name
  - County Name
  - Region
  - Type
  - Enrollment (may be in separate columns)

**Note:** Some columns may have leading apostrophes (') to preserve leading zeros - this is normal.

## Next Steps

After saving the file, run the processing script:

```bash
cd /Users/joelvillarino/Downloads/TexasDistricts
python3 scripts/process_tea_master.py
```

This will:
- Extract only districts (filtering out individual schools)
- Clean district IDs (remove apostrophes, standardize format)
- Remove duplicates
- Create `data/tea_districts_master_clean.csv` with ~1,200 districts

## Troubleshooting

### Problem: Download page requires authentication
**Solution:** Basic downloads should not require login. If prompted, contact TEA support.

### Problem: Downloaded file is empty or very small
**Solution:** The page may have timed out. Refresh and try again. Consider downloading during off-peak hours.

### Problem: File has unexpected format
**Solution:** Check that you selected "School and District Data File" and not personnel or other data types.

### Problem: Cannot find the file after download
**Solution:** Check your browser's default download folder, typically `~/Downloads/`

## Alternative Source (If AskTED Unavailable)

If the AskTED system is down, you can use the TEA Open Data Portal:

1. Visit: **https://schoolsdata2-tea-texas.opendata.arcgis.com/**
2. Search for "School Districts 2025"
3. Click on the dataset
4. Click "Download" and select "CSV" format
5. Save to `data/tea_master_districts_raw.csv`

**Note:** The Open Data Portal format may differ slightly - the processing script attempts to handle multiple formats.

## Questions?

- **TEA GIS Admin:** GISAdmin@tea.texas.gov
- **TEA Main:** (512) 463-9734
- **Documentation:** See `docs/DATA_SOURCES.md`

---

*Last updated: 2026-01-15*
