#!/usr/bin/env python3
"""
Fix Mismatched Districts

This script finds correct TEA district IDs for the 49 districts that weren't
found in the TEA master list and creates corrected datasets.

Author: Texas Districts Video Discovery Project
Date: 2026-01-15
"""

import csv
from pathlib import Path
from validate_district_id import DistrictValidator

# 49 mismatched districts from merge_report.md
MISMATCHED_DISTRICTS = [
    ("015903", "East Central ISD", "Bexar County"),
    ("031902", "Willis ISD", "Montgomery County"),
    ("031907", "Montgomery ISD", "Montgomery County"),
    ("057908", "DeSoto ISD", "Dallas County"),
    ("057915", "Cedar Hill ISD", "Dallas County"),
    ("057917", "Wylie ISD", "Collin County"),
    ("057918", "Highland Park ISD", "Dallas County"),
    ("057920", "Coppell ISD", "Dallas County"),
    ("057921", "Sunnyvale ISD", "Dallas County"),
    ("071910", "Ysleta ISD", "El Paso County"),
    ("079902", "Stafford MSD", "Fort Bend County"),
    ("079903", "Alvin ISD", "Brazoria County"),
    ("079904", "Angleton ISD", "Brazoria County"),
    ("079905", "Brazosport ISD", "Brazoria County"),
    ("079908", "Pearland ISD", "Brazoria County"),
    ("079909", "Needville ISD", "Fort Bend County"),
    ("079911", "Danbury ISD", "Brazoria County"),
    ("101901", "Baytown ISD", "Harris County"),
    ("101904", "La Porte ISD", "Harris County"),
    ("101909", "Friendswood ISD", "Galveston County"),
    ("101918", "Sheldon ISD", "Harris County"),
    ("101922", "Hitchcock ISD", "Galveston County"),
    ("101923", "Crosby ISD", "Harris County"),
    ("101926", "Tomball ISD", "Montgomery County"),
    ("101927", "Spring ISD", "Harris County"),
    ("157905", "Longview ISD", "Gregg County"),
    ("161902", "Allen ISD", "Collin County"),
    ("161904", "Princeton ISD", "Collin County"),
    ("161911", "Community ISD", "Collin County"),
    ("161913", "Royse City ISD", "Rockwall County"),
    ("161915", "Rockwall ISD", "Rockwall County"),
    ("161917", "Lovejoy ISD", "Collin County"),
    ("164925", "Barbers Hill ISD", "Chambers County"),
    ("165906", "McKinney ISD", "Collin County"),
    ("174905", "San Benito CISD", "Cameron County"),
    ("174907", "Point Isabel ISD", "Cameron County"),
    ("178911", "Salado ISD", "Bell County"),
    ("220903", "Aledo ISD", "Parker County"),
    ("220909", "Grapevine-Colleyville ISD", "Tarrant County"),
    ("220911", "Granbury ISD", "Hood County"),
    ("220913", "Haltom City ISD", "Tarrant County"),
    ("227902", "Burleson ISD", "Tarrant County"),
    ("227903", "Joshua ISD", "Johnson County"),
    ("227905", "Cleburne ISD", "Johnson County"),
    ("227908", "Everman ISD", "Tarrant County"),
    ("227911", "Fort Worth Academy of Fine Arts", "Tarrant County"),
    ("246901", "Round Rock ISD", "Williamson County"),
    ("246903", "Hays CISD", "Hays County"),
    ("246910", "Taylor ISD", "Williamson County"),
]

def find_correct_id(validator, old_id, district_name, county):
    """
    Find the correct TEA district ID for a district.

    Args:
        validator: DistrictValidator instance
        old_id: Incorrect district ID
        district_name: District name
        county: County name

    Returns:
        tuple: (correct_id, confidence, notes)
    """
    # Search by name
    matches = validator.find_by_name(district_name, threshold=0.85)

    if not matches:
        return (None, "not_found", f"No matches found for {district_name}")

    # Filter by county if possible
    county_upper = county.upper().replace(" COUNTY", "")
    county_matches = [m for m in matches if county_upper in m['county'].upper()]

    if len(county_matches) == 1:
        match = county_matches[0]
        if match['similarity'] >= 0.95:
            return (match['district_id'], "high", f"Exact match in correct county")
        else:
            return (match['district_id'], "medium", f"Good match ({match['similarity']*100:.0f}%) in correct county")
    elif len(county_matches) > 1:
        # Multiple matches in same county - take highest similarity
        best = max(county_matches, key=lambda x: x['similarity'])
        return (best['district_id'], "medium", f"Multiple matches, picked best ({best['similarity']*100:.0f}%)")
    else:
        # No county match, use best overall match
        best = matches[0]
        return (best['district_id'], "low", f"No county match, using best overall ({best['similarity']*100:.0f}%)")


def main():
    """Main execution function."""
    print("="*80)
    print("Mismatched District ID Correction")
    print("="*80 + "\n")

    # Initialize validator
    validator = DistrictValidator()

    # Create mapping
    id_mapping = {}  # old_id -> new_id
    corrections = []

    print("Searching TEA master list for correct IDs...\n")

    for old_id, district_name, county in MISMATCHED_DISTRICTS:
        correct_id, confidence, notes = find_correct_id(validator, old_id, district_name, county)

        if correct_id:
            id_mapping[old_id] = correct_id
            corrections.append({
                'old_id': old_id,
                'correct_id': correct_id,
                'district_name': district_name,
                'county': county,
                'confidence': confidence,
                'notes': notes
            })

            status = "✓" if confidence == "high" else "⚠" if confidence == "medium" else "?"
            print(f"{status} {district_name}")
            print(f"   Old ID: {old_id} → Correct ID: {correct_id} ({confidence})")
            print(f"   {notes}\n")
        else:
            print(f"✗ {district_name}")
            print(f"   Old ID: {old_id} → NOT FOUND")
            print(f"   {notes}\n")

    # Save corrections report
    report_path = Path("data/id_corrections_report.csv")
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['old_id', 'correct_id', 'district_name', 'county', 'confidence', 'notes']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(corrections)

    print("="*80)
    print(f"Found correct IDs: {len(id_mapping)}/{len(MISMATCHED_DISTRICTS)}")
    print(f"High confidence: {sum(1 for c in corrections if c['confidence'] == 'high')}")
    print(f"Medium confidence: {sum(1 for c in corrections if c['confidence'] == 'medium')}")
    print(f"Low confidence: {sum(1 for c in corrections if c['confidence'] == 'low')}")
    print(f"\nReport saved to: {report_path}")
    print("="*80 + "\n")

    # Now fix the verified dataset
    print("Updating verified dataset with correct IDs...\n")

    verified_file = Path("data/districts_verified.csv")
    verified_corrected = Path("data/districts_verified_corrected.csv")

    rows_updated = 0
    with open(verified_file, 'r', encoding='utf-8') as f_in:
        with open(verified_corrected, 'w', newline='', encoding='utf-8') as f_out:
            reader = csv.DictReader(f_in)
            writer = csv.DictWriter(f_out, fieldnames=reader.fieldnames)
            writer.writeheader()

            for row in reader:
                old_id = row['district_id']
                if old_id in id_mapping:
                    row['district_id'] = id_mapping[old_id]
                    rows_updated += 1
                    print(f"✓ Updated {row['district_name']}: {old_id} → {id_mapping[old_id]}")
                writer.writerow(row)

    print(f"\n✓ Updated {rows_updated} district IDs")
    print(f"✓ Corrected dataset saved to: {verified_corrected}")

    return len(id_mapping), rows_updated


if __name__ == "__main__":
    found, updated = main()
    if found < len(MISMATCHED_DISTRICTS):
        print(f"\n⚠ WARNING: Could not find correct IDs for {len(MISMATCHED_DISTRICTS) - found} districts")
        print("Manual review may be required.")
