#!/usr/bin/env python3
"""
Apply Manual Corrections to District IDs

Fixes the 7 problematic districts that need manual correction:
- 5 low confidence matches that need verification
- 2 districts that don't exist and should be removed

Author: Texas Districts Video Discovery Project
Date: 2026-01-15
"""

import csv
from pathlib import Path

# Manual corrections needed
MANUAL_CORRECTIONS = {
    '221912': '043914',  # Wylie ISD - should be Collin County (221912 is Taylor County)
    '188903': '057911',  # Highland Park ISD - should be Dallas County (188903 is Potter County)
    '146902': '101911',  # Baytown → Goose Creek CISD (Baytown doesn't exist as separate ISD)
}

# Districts to remove (don't exist in TEA, have no video data)
DISTRICTS_TO_REMOVE = {'220913', '227911'}  # Haltom City ISD, Fort Worth Academy

# Name corrections
NAME_CORRECTIONS = {
    '101911': 'Goose Creek CISD'  # Was listed as "Baytown ISD"
}


def apply_corrections(input_file, output_file):
    """Apply manual corrections to the verified dataset."""

    rows_corrected = 0
    rows_removed = 0
    corrections_applied = []

    with open(input_file, 'r', encoding='utf-8') as f_in:
        with open(output_file, 'w', newline='', encoding='utf-8') as f_out:
            reader = csv.DictReader(f_in)
            writer = csv.DictWriter(f_out, fieldnames=reader.fieldnames)
            writer.writeheader()

            for row in reader:
                district_id = row['district_id']

                # Skip districts that should be removed
                if district_id in DISTRICTS_TO_REMOVE:
                    rows_removed += 1
                    print(f"✗ Removed {row['district_name']} ({district_id}) - does not exist as separate district")
                    continue

                # Apply ID corrections
                if district_id in MANUAL_CORRECTIONS:
                    old_id = district_id
                    new_id = MANUAL_CORRECTIONS[district_id]
                    row['district_id'] = new_id
                    rows_corrected += 1

                    # Also apply name correction if needed
                    old_name = row['district_name']
                    if new_id in NAME_CORRECTIONS:
                        row['district_name'] = NAME_CORRECTIONS[new_id]
                        corrections_applied.append(f"{old_name} ({old_id}) → {row['district_name']} ({new_id})")
                        print(f"✓ Corrected {old_name} → {row['district_name']}: {old_id} → {new_id}")
                    else:
                        corrections_applied.append(f"{old_name}: {old_id} → {new_id}")
                        print(f"✓ Corrected {old_name}: {old_id} → {new_id}")

                writer.writerow(row)

    return rows_corrected, rows_removed, corrections_applied


def main():
    """Main execution function."""
    print("="*80)
    print("Applying Manual District ID Corrections")
    print("="*80 + "\n")

    input_file = Path("data/districts_verified_corrected.csv")
    output_file = Path("data/districts_verified_final.csv")

    corrected, removed, details = apply_corrections(input_file, output_file)

    print(f"\n{'='*80}")
    print(f"Manual corrections applied:")
    print(f"  District IDs corrected: {corrected}")
    print(f"  Districts removed: {removed}")
    print(f"  Output saved to: {output_file}")
    print(f"{'='*80}\n")

    if details:
        print("Corrections applied:")
        for detail in details:
            print(f"  - {detail}")
        print()

    return corrected, removed


if __name__ == "__main__":
    corrected, removed = main()
    print(f"✓ Ready for merge: {corrected} IDs corrected, {removed} invalid districts removed")
