#!/usr/bin/env python3
"""
Process TEA Master District List

This script processes the raw TEA AskTED CSV download and extracts a clean
list of school districts with standardized fields.

Usage:
    python scripts/process_tea_master.py

Input:  data/tea_master_districts_raw.csv (manual download from TEA)
Output: data/tea_districts_master_clean.csv

Author: Texas Districts Video Discovery Project
Date: 2026-01-15
"""

import csv
import sys
from pathlib import Path

# File paths
INPUT_FILE = Path("data/tea_master_districts_raw.csv")
OUTPUT_FILE = Path("data/tea_districts_master_clean.csv")

# District type keywords that identify district-level entities
DISTRICT_TYPES = [
    "ISD",  # Independent School District
    "CISD",  # Consolidated Independent School District
    "CONS ISD",
    "INDEPENDENT SCHOOL DISTRICT",
    "CONSOLIDATED ISD",
    "MSD",  # Municipal School District
    "CSD",  # Common School District
    "CHARTER",  # Charter districts
]


def is_district(entity_name, entity_type=None):
    """
    Determine if an entity is a district (not an individual school).

    Args:
        entity_name: Name of the entity
        entity_type: Optional type field if available in TEA data

    Returns:
        bool: True if entity is a district-level organization
    """
    name_upper = entity_name.upper()

    # Check if name contains district type keywords
    for district_type in DISTRICT_TYPES:
        if district_type in name_upper:
            return True

    # Additional check: districts typically don't have "EL", "MS", "HS", "SCHOOL" in name
    # unless followed by district type
    school_keywords = ["ELEMENTARY", "MIDDLE SCHOOL", "HIGH SCHOOL", "JUNIOR HIGH"]
    has_school_keyword = any(keyword in name_upper for keyword in school_keywords)

    if has_school_keyword and not any(dt in name_upper for dt in DISTRICT_TYPES):
        return False

    return False  # Default to not a district if unclear


def clean_district_id(district_id):
    """
    Clean district ID by removing apostrophes and ensuring 6-digit format.

    TEA sometimes prepends apostrophes to preserve leading zeros.

    Args:
        district_id: Raw district ID string

    Returns:
        str: Cleaned 6-digit district ID
    """
    if not district_id:
        return ""

    # Remove apostrophes
    cleaned = district_id.replace("'", "").strip()

    # Pad with leading zeros to ensure 6 digits
    if cleaned.isdigit():
        cleaned = cleaned.zfill(6)

    return cleaned


def process_tea_csv(input_path, output_path):
    """
    Process TEA master CSV and extract clean district list.

    Args:
        input_path: Path to raw TEA CSV download
        output_path: Path to save cleaned district CSV

    Returns:
        tuple: (districts_processed, districts_found)
    """
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print(f"\nPlease download the TEA master district list first:")
        print(f"1. Visit: https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/DownloadFile.aspx")
        print(f"2. Download 'All Schools and Districts' CSV")
        print(f"3. Save as: {input_path}")
        return 0, 0

    districts = []
    total_rows = 0

    print(f"Processing TEA master file: {input_path}")

    with open(input_path, 'r', encoding='utf-8') as f:
        # Try to detect the CSV format
        sample = f.read(2000)
        f.seek(0)

        # TEA CSVs may have different header formats
        reader = csv.DictReader(f)

        for row in reader:
            total_rows += 1

            # Common TEA field names (vary by export type)
            # Try multiple possible field name variations
            possible_id_fields = ['District Number', 'DistrictNumber', 'DISTRICT', 'CDN', 'CO-DIST']
            possible_name_fields = ['District Name', 'DistrictName', 'DISTNAME', 'Name']
            possible_county_fields = ['County', 'CountyName', 'County Name', 'CNTYNAME']
            possible_type_fields = ['Type', 'EntityType', 'Entity Type']

            # Extract fields
            district_id = None
            for field in possible_id_fields:
                if field in row and row[field]:
                    district_id = clean_district_id(row[field])
                    break

            district_name = None
            for field in possible_name_fields:
                if field in row and row[field]:
                    district_name = row[field].strip()
                    break

            county = None
            for field in possible_county_fields:
                if field in row and row[field]:
                    county = row[field].strip()
                    break

            entity_type = None
            for field in possible_type_fields:
                if field in row and row[field]:
                    entity_type = row[field].strip()
                    break

            # Skip if essential fields missing
            if not district_id or not district_name:
                continue

            # Check if this is a district (not individual school)
            if not is_district(district_name, entity_type):
                continue

            # Extract enrollment if available
            enrollment = ""
            enrollment_fields = [
                'District Enrollment as of Oct 2024',  # TEA AskTED export format
                'Enrollment',
                'Students',
                'ENROLL',
                'Total Enrollment'
            ]
            for field in enrollment_fields:
                if field in row and row[field]:
                    enrollment = row[field].strip()
                    break

            # Validate district ID format (should be 6 digits)
            if not (district_id.isdigit() and len(district_id) == 6):
                print(f"WARNING: Invalid district ID format: {district_id} for {district_name}")
                continue

            districts.append({
                'district_id': district_id,
                'district_name': district_name,
                'county': county or "",
                'enrollment': enrollment
            })

    # Remove duplicates (keep first occurrence)
    seen_ids = set()
    unique_districts = []
    duplicates_removed = 0

    for district in districts:
        if district['district_id'] not in seen_ids:
            seen_ids.add(district['district_id'])
            unique_districts.append(district)
        else:
            duplicates_removed += 1
            print(f"DUPLICATE: {district['district_id']} - {district['district_name']}")

    # Sort by district ID
    unique_districts.sort(key=lambda x: x['district_id'])

    # Write output CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['district_id', 'district_name', 'county', 'enrollment']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(unique_districts)

    print(f"\n{'='*60}")
    print(f"Processing complete!")
    print(f"  Total rows processed: {total_rows}")
    print(f"  Districts found: {len(districts)}")
    print(f"  Duplicates removed: {duplicates_removed}")
    print(f"  Unique districts: {len(unique_districts)}")
    print(f"  Output: {output_path}")
    print(f"{'='*60}\n")

    return total_rows, len(unique_districts)


def main():
    """Main execution function."""
    print("="*60)
    print("TEA Master District List Processor")
    print("="*60 + "\n")

    processed, found = process_tea_csv(INPUT_FILE, OUTPUT_FILE)

    if found == 0:
        print("\nNo districts found. Please check:")
        print("1. Is the input file downloaded correctly?")
        print("2. Does it contain district data (not just schools)?")
        print("3. Are the column names correct?")
        sys.exit(1)

    print(f"✓ Successfully processed {found} districts")
    print(f"✓ Clean district list saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
