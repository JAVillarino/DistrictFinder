# Texas School Districts - Official Data Sources

## Primary Authoritative Source: Texas Education Agency (TEA)

### TEA AskTED System (Recommended)
**URL:** https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/DownloadFile.aspx

**What it contains:**
- Complete list of all Texas school districts (~1,208 districts)
- Official district IDs in CCCNNN format (CCC = county code, NNN = district number)
- District names, counties, enrollment data
- Updated daily

**How to download:**
1. Visit the AskTED Download File page
2. Select "Download School and District Data File" or "Download All Schools and Districts"
3. Choose sort option (District Number recommended)
4. Click "Download File" button
5. Save the downloaded CSV file as `data/tea_master_districts_raw.csv`

**Important notes:**
- File is in CSV (comma-separated values) format
- Some columns may contain leading apostrophes for fields with leading zeros (District Number, Region Number)
- Contains both schools and districts - you'll need to filter for districts only
- No authentication required for basic download

### Alternative Source: TEA Public Open Data Portal
**URL:** https://schoolsdata2-tea-texas.opendata.arcgis.com/

**Datasets available:**
- [School Districts 2025](https://schoolsdata2-tea-texas.opendata.arcgis.com/datasets/TEA-Texas::school-districts-2025-/about)
- County-District Lists (CSV)
- District-County Lists (CSV)

**Data format:** KML, Shapefile, CSV
**License:** CC-BY-SA
**Contact:** GISAdmin@tea.texas.gov

### Secondary Source: TAPR Data Downloads
**URL:** https://rptsvr1.tea.texas.gov/perfreport/tapr/tapr_dd_download.html

Contains accountability and performance data including district information.

---

## Texas District ID Format

Texas uses a 6-digit district ID format: **CCCNNN**
- **CCC** = County code (first 3 digits, e.g., 101 = Harris County)
- **NNN** = District number within county (last 3 digits)

**Examples:**
- `101912` = Houston ISD (Harris County 101, District 912)
- `057905` = Dallas ISD (Dallas County 057, District 905)
- `015915` = Northside ISD (Bexar County 015, District 915)

**Important notes:**
- Some districts span multiple counties but have one primary county code
- District IDs may appear with different county prefixes in some TEA databases
- Always validate against TEA's official master list to get the canonical ID

---

## Data Update Frequency

**Recommended schedule:**
- **Quarterly:** Check for new districts, consolidations, or closures
- **Annually:** Full refresh of master district list before fall semester
- **As needed:** After significant district reorganizations or charter school approvals

**Texas school year:** August - June

---

## Data Validation Process

Before adding new districts to the verified dataset:

1. **Download latest TEA master list** (see instructions above)
2. **Run validation script:** `python scripts/validate_district_id.py [district_id]`
3. **Check for duplicates:** Script will flag if district already exists
4. **Verify canonical ID:** Script returns TEA's official district ID
5. **Cross-reference enrollment/county:** Ensure data matches TEA records

---

## Known Data Quality Issues

### Duplicate District IDs
**Problem:** Districts may appear with multiple IDs in different TEA databases
- Root cause: Districts spanning multiple counties
- Root cause: Historical ID changes or reorganizations
- Root cause: Different county prefix conventions

**Solution:** Always use the district ID from TEA AskTED as canonical
- Store alternate IDs in `notes` field if needed
- Run deduplication before merging new data

### District Name Variations
**Problem:** Spelling inconsistencies (e.g., "DeSoto ISD" vs "Desoto ISD")

**Solution:** Use TEA's official spelling from master list

### Enrollment Data Lag
**Problem:** Enrollment figures may be from previous school year

**Solution:** Note the school year of enrollment data in comments

---

## Contact Information

**TEA GIS Admin:** GISAdmin@tea.texas.gov
**TEA General:** (512) 463-9734
**AskTED Support:** Via TEA website

---

## Historical Note

This project previously experienced duplicate issues due to:
- Processing districts from multiple sources without validation
- No canonical ID verification against TEA master
- 22 duplicate entries identified and removed (2026-01-15)

**Current safeguard:** All new districts must validate against TEA master before addition.

---

*Document created: 2026-01-15*
*Last updated: 2026-01-15*
