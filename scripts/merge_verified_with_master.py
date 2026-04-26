#!/usr/bin/env python3
"""
Merge Verified Video Data with TEA Master District List

This script merges our verified district video data with the authoritative
TEA master list to create a complete dataset of all Texas districts.

Usage:
    python scripts/merge_verified_with_master.py

Input:
    - data/districts_verified.csv (172 districts with video data)
    - data/tea_districts_master_clean.csv (all TX districts from TEA)

Output:
    - data/districts_complete.csv (complete merged dataset)
    - data/merge_report.md (validation report)

Author: Texas Districts Video Discovery Project
Date: 2026-01-15
"""

import csv
from pathlib import Path
from datetime import datetime

# File paths
VERIFIED_FILE = Path("data/districts_verified.csv")
TEA_MASTER_FILE = Path("data/tea_districts_master_clean.csv")
OUTPUT_FILE = Path("data/districts_complete.csv")
REPORT_FILE = Path("data/merge_report.md")


def load_verified_districts(file_path):
    """
    Load verified districts with video data.

    Returns:
        dict: {district_id: {all fields}}
    """
    districts = {}

    if not file_path.exists():
        print(f"ERROR: Verified districts file not found: {file_path}")
        return districts

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            district_id = row.get('district_id', '').strip()
            if district_id:
                districts[district_id] = dict(row)

    return districts


def load_tea_master(file_path):
    """
    Load TEA master district list.

    Returns:
        dict: {district_id: {district_name, county, enrollment}}
    """
    districts = {}

    if not file_path.exists():
        print(f"ERROR: TEA master file not found: {file_path}")
        print(f"\nPlease run: python scripts/process_tea_master.py")
        return districts

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            district_id = row.get('district_id', '').strip()
            if district_id:
                districts[district_id] = {
                    'district_name': row.get('district_name', ''),
                    'county': row.get('county', ''),
                    'enrollment': row.get('enrollment', '')
                }

    return districts


def merge_districts(verified, tea_master):
    """
    Merge verified and TEA master data.

    Returns:
        tuple: (merged_list, stats_dict, issues_dict)
    """
    merged = []
    stats = {
        'total_tea': len(tea_master),
        'total_verified': len(verified),
        'matched': 0,
        'verified_not_in_tea': 0,
        'tea_not_verified': 0,
        'mismatches': 0
    }
    issues = {
        'verified_not_in_tea': [],
        'name_mismatches': [],
        'county_mismatches': [],
        'enrollment_mismatches': []
    }

    # Process all districts from TEA master (authoritative source)
    for district_id, tea_data in tea_master.items():
        if district_id in verified:
            # District has video data - merge it
            verified_data = verified[district_id]
            stats['matched'] += 1

            # Check for data mismatches (TEA is authoritative)
            if tea_data['district_name'] != verified_data.get('district_name', ''):
                issues['name_mismatches'].append({
                    'district_id': district_id,
                    'tea_name': tea_data['district_name'],
                    'verified_name': verified_data.get('district_name', '')
                })

            if tea_data['county'] != verified_data.get('county', ''):
                issues['county_mismatches'].append({
                    'district_id': district_id,
                    'tea_county': tea_data['county'],
                    'verified_county': verified_data.get('county', '')
                })

            # Merge: Use TEA data for name/county/enrollment, keep video data from verified
            merged_row = {
                'district_id': district_id,
                'district_name': tea_data['district_name'],  # TEA is authoritative
                'county': tea_data['county'],  # TEA is authoritative
                'enrollment': tea_data['enrollment'],  # TEA is authoritative
                'website_url': verified_data.get('website_url', ''),
                'video_platform': verified_data.get('video_platform', ''),
                'video_url': verified_data.get('video_url', ''),
                'archive_start_year': verified_data.get('archive_start_year', ''),
                'youtube_channel_id': verified_data.get('youtube_channel_id', ''),
                'notes': verified_data.get('notes', ''),
                'confidence': verified_data.get('confidence', ''),
                'last_checked': verified_data.get('last_checked', ''),
                'video_status': 'verified'
            }
        else:
            # District not yet processed for video
            stats['tea_not_verified'] += 1
            merged_row = {
                'district_id': district_id,
                'district_name': tea_data['district_name'],
                'county': tea_data['county'],
                'enrollment': tea_data['enrollment'],
                'website_url': '',
                'video_platform': '',
                'video_url': '',
                'archive_start_year': '',
                'youtube_channel_id': '',
                'notes': '',
                'confidence': '',
                'last_checked': '',
                'video_status': 'pending'
            }

        merged.append(merged_row)

    # Check for districts in verified but NOT in TEA master (potential bad IDs)
    for district_id in verified:
        if district_id not in tea_master:
            stats['verified_not_in_tea'] += 1
            issues['verified_not_in_tea'].append({
                'district_id': district_id,
                'district_name': verified[district_id].get('district_name', ''),
                'county': verified[district_id].get('county', '')
            })

    stats['mismatches'] = (len(issues['name_mismatches']) +
                          len(issues['county_mismatches']) +
                          len(issues['enrollment_mismatches']))

    # Sort by district_id
    merged.sort(key=lambda x: x['district_id'])

    return merged, stats, issues


def write_merged_csv(merged_data, output_path):
    """Write merged data to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        'district_id', 'district_name', 'county', 'enrollment',
        'website_url', 'video_platform', 'video_url', 'archive_start_year',
        'youtube_channel_id', 'notes', 'confidence', 'last_checked', 'video_status'
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged_data)


def generate_report(stats, issues, output_path):
    """Generate merge validation report."""
    report = f"""# TEA Master List Merge Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total districts in TEA master | {stats['total_tea']} |
| Districts with verified video data | {stats['total_verified']} |
| Successfully matched | {stats['matched']} |
| TEA districts pending video processing | {stats['tea_not_verified']} |
| Verified districts NOT in TEA master | {stats['verified_not_in_tea']} |
| Data mismatches found | {stats['mismatches']} |

**Completion:** {stats['matched']}/{stats['total_tea']} ({stats['matched']/stats['total_tea']*100:.1f}%)

---

## Critical Issues Requiring Review

### ⚠️ Districts in Verified Dataset NOT Found in TEA Master

"""

    if not issues['verified_not_in_tea']:
        report += "✅ **None found** - All verified districts match TEA master list!\n\n"
    else:
        report += f"**Found {len(issues['verified_not_in_tea'])} districts** - These may have incorrect IDs:\n\n"
        for item in issues['verified_not_in_tea']:
            report += f"- **{item['district_id']}** - {item['district_name']} ({item['county']} County)\n"
        report += "\n**Action required:** Verify these district IDs against TEA records.\n\n"

    report += "---\n\n## Data Mismatches (TEA is Authoritative)\n\n"

    if issues['name_mismatches']:
        report += f"### District Name Mismatches ({len(issues['name_mismatches'])})\n\n"
        report += "| District ID | TEA Name | Our Name |\n"
        report += "|-------------|----------|----------|\n"
        for item in issues['name_mismatches']:
            report += f"| {item['district_id']} | {item['tea_name']} | {item['verified_name']} |\n"
        report += "\n**Resolution:** TEA names have been used in merged dataset.\n\n"

    if issues['county_mismatches']:
        report += f"### County Mismatches ({len(issues['county_mismatches'])})\n\n"
        report += "| District ID | TEA County | Our County |\n"
        report += "|-------------|------------|------------|\n"
        for item in issues['county_mismatches']:
            report += f"| {item['district_id']} | {item['tea_county']} | {item['verified_county']} |\n"
        report += "\n**Resolution:** TEA counties have been used in merged dataset.\n\n"

    if not issues['name_mismatches'] and not issues['county_mismatches']:
        report += "✅ **No mismatches found** - All verified data matches TEA master!\n\n"

    report += "---\n\n## Next Steps\n\n"

    if issues['verified_not_in_tea']:
        report += f"1. **URGENT:** Review {len(issues['verified_not_in_tea'])} districts not in TEA master\n"
        report += "   - Check if IDs are incorrect\n   - Verify districts haven't been consolidated/closed\n   - Update district IDs if needed\n\n"

    report += f"2. **Continue processing:** {stats['tea_not_verified']} districts still need video discovery\n"
    report += f"3. **Progress tracking:** Currently at {stats['matched']/stats['total_tea']*100:.1f}% completion\n"
    report += f"4. **Use validation tool:** Run `python scripts/validate_district_id.py` before adding new districts\n\n"

    report += "---\n\n## Files Generated\n\n"
    report += f"- **Complete dataset:** `data/districts_complete.csv` ({stats['total_tea']} districts)\n"
    report += f"- **Video verified:** {stats['matched']} districts with video data\n"
    report += f"- **Pending processing:** {stats['tea_not_verified']} districts without video data\n\n"

    report += "---\n\n*Merge process completed successfully.*\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)


def main():
    """Main execution function."""
    print("="*60)
    print("TEA Master List Merger")
    print("="*60 + "\n")

    # Load data
    print("Loading verified districts...")
    verified = load_verified_districts(VERIFIED_FILE)
    print(f"  Loaded {len(verified)} verified districts\n")

    print("Loading TEA master list...")
    tea_master = load_tea_master(TEA_MASTER_FILE)
    print(f"  Loaded {len(tea_master)} districts from TEA\n")

    if not tea_master:
        print("\n❌ Cannot proceed without TEA master list.")
        print("Please download and process TEA data first:")
        print("  1. See: DOWNLOAD_TEA_MASTER.md")
        print("  2. Run: python scripts/process_tea_master.py")
        return

    # Merge datasets
    print("Merging datasets...")
    merged, stats, issues = merge_districts(verified, tea_master)
    print(f"  Merged {len(merged)} total districts\n")

    # Write outputs
    print(f"Writing merged dataset to {OUTPUT_FILE}...")
    write_merged_csv(merged, OUTPUT_FILE)

    print(f"Generating report at {REPORT_FILE}...")
    generate_report(stats, issues, REPORT_FILE)

    # Summary
    print("\n" + "="*60)
    print("Merge Complete!")
    print("="*60)
    print(f"  Total districts: {stats['total_tea']}")
    print(f"  Verified (with video): {stats['matched']}")
    print(f"  Pending processing: {stats['tea_not_verified']}")
    print(f"  Completion: {stats['matched']/stats['total_tea']*100:.1f}%")

    if issues['verified_not_in_tea']:
        print(f"\n⚠️  WARNING: {len(issues['verified_not_in_tea'])} verified districts NOT in TEA master!")
        print("  Check merge_report.md for details")

    if stats['mismatches'] > 0:
        print(f"\nℹ️  {stats['mismatches']} data mismatches found (resolved using TEA data)")

    print(f"\n✓ Output: {OUTPUT_FILE}")
    print(f"✓ Report: {REPORT_FILE}\n")


if __name__ == "__main__":
    main()
