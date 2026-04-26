#!/usr/bin/env python3
"""
District ID Validation Tool

Validates district IDs against TEA master list to prevent duplicates
and ensure data quality.

Usage:
    # As command-line tool
    python scripts/validate_district_id.py 101912
    python scripts/validate_district_id.py "Houston ISD" --name

    # As library
    from scripts.validate_district_id import validate_district_id
    result = validate_district_id('101912')

Author: Texas Districts Video Discovery Project
Date: 2026-01-15
"""

import csv
import sys
from pathlib import Path
from difflib import SequenceMatcher

# File paths
TEA_MASTER_FILE = Path("data/tea_districts_master_clean.csv")
VERIFIED_FILE = Path("data/districts_verified.csv")
COMPLETE_FILE = Path("data/districts_complete.csv")


class DistrictValidator:
    """Validates district IDs and names against TEA master list."""

    def __init__(self):
        """Initialize validator with TEA master data."""
        self.tea_districts = {}  # {district_id: {name, county, enrollment}}
        self.verified_ids = set()  # IDs already processed
        self.name_to_id = {}  # {district_name: district_id} for fuzzy matching

        self._load_tea_master()
        self._load_verified()

    def _load_tea_master(self):
        """Load TEA master district list."""
        if not TEA_MASTER_FILE.exists():
            print(f"WARNING: TEA master file not found: {TEA_MASTER_FILE}")
            print("Run: python scripts/process_tea_master.py")
            return

        with open(TEA_MASTER_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                district_id = row.get('district_id', '').strip()
                if district_id:
                    self.tea_districts[district_id] = {
                        'name': row.get('district_name', ''),
                        'county': row.get('county', ''),
                        'enrollment': row.get('enrollment', '')
                    }
                    # Store name-to-ID mapping for fuzzy search
                    name_key = row.get('district_name', '').upper()
                    self.name_to_id[name_key] = district_id

    def _load_verified(self):
        """Load already verified districts."""
        # Try complete file first, then verified file
        file_to_load = COMPLETE_FILE if COMPLETE_FILE.exists() else VERIFIED_FILE

        if not file_to_load.exists():
            return

        with open(file_to_load, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                district_id = row.get('district_id', '').strip()
                if district_id:
                    self.verified_ids.add(district_id)

    def validate_id(self, district_id):
        """
        Validate a district ID.

        Returns:
            dict: {
                'valid': bool,
                'exists_in_tea': bool,
                'already_verified': bool,
                'district_name': str,
                'county': str,
                'enrollment': str,
                'message': str
            }
        """
        district_id = district_id.strip()

        # Check format (should be 6 digits)
        if not (district_id.isdigit() and len(district_id) == 6):
            return {
                'valid': False,
                'exists_in_tea': False,
                'already_verified': False,
                'message': f'Invalid format: "{district_id}" (must be 6 digits)'
            }

        # Check if exists in TEA master
        if district_id not in self.tea_districts:
            return {
                'valid': False,
                'exists_in_tea': False,
                'already_verified': False,
                'message': f'District ID {district_id} not found in TEA master list'
            }

        tea_data = self.tea_districts[district_id]
        already_verified = district_id in self.verified_ids

        return {
            'valid': True,
            'exists_in_tea': True,
            'already_verified': already_verified,
            'district_name': tea_data['name'],
            'county': tea_data['county'],
            'enrollment': tea_data['enrollment'],
            'message': 'Valid district ID' if not already_verified else 'District already processed'
        }

    def find_by_name(self, district_name, threshold=0.8):
        """
        Find district by name using fuzzy matching.

        Args:
            district_name: Name to search for
            threshold: Similarity threshold (0.0-1.0)

        Returns:
            list: [{district_id, name, county, similarity}]
        """
        search_name = district_name.upper()
        matches = []

        for name_key, district_id in self.name_to_id.items():
            similarity = SequenceMatcher(None, search_name, name_key).ratio()
            if similarity >= threshold:
                tea_data = self.tea_districts[district_id]
                matches.append({
                    'district_id': district_id,
                    'name': tea_data['name'],
                    'county': tea_data['county'],
                    'enrollment': tea_data['enrollment'],
                    'similarity': similarity,
                    'already_verified': district_id in self.verified_ids
                })

        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        return matches

    def check_duplicate(self, district_name, county):
        """
        Check if a district with this name and county already exists.

        Returns:
            dict: {
                'is_duplicate': bool,
                'canonical_id': str or None,
                'matches': list
            }
        """
        # Find potential matches by name
        matches = self.find_by_name(district_name, threshold=0.9)

        # Filter matches by county if provided
        if county:
            county_upper = county.upper()
            matches = [m for m in matches if county_upper in m['county'].upper()]

        return {
            'is_duplicate': len(matches) > 0,
            'canonical_id': matches[0]['district_id'] if matches else None,
            'matches': matches
        }

    def get_stats(self):
        """Get validation statistics."""
        return {
            'total_tea_districts': len(self.tea_districts),
            'verified_districts': len(self.verified_ids),
            'pending_districts': len(self.tea_districts) - len(self.verified_ids),
            'completion_pct': len(self.verified_ids) / len(self.tea_districts) * 100 if self.tea_districts else 0
        }


def validate_district_id(district_id):
    """
    Convenience function for library usage.

    Args:
        district_id: District ID to validate

    Returns:
        dict: Validation result
    """
    validator = DistrictValidator()
    return validator.validate_id(district_id)


def main():
    """Command-line interface."""
    import argparse

    parser = argparse.ArgumentParser(description='Validate Texas school district IDs')
    parser.add_argument('query', help='District ID or name to validate')
    parser.add_argument('--name', '-n', action='store_true',
                       help='Search by district name instead of ID')
    parser.add_argument('--stats', '-s', action='store_true',
                       help='Show validation statistics')
    args = parser.parse_args()

    validator = DistrictValidator()

    if args.stats:
        stats = validator.get_stats()
        print("\n" + "="*60)
        print("District Validation Statistics")
        print("="*60)
        print(f"Total TEA districts: {stats['total_tea_districts']}")
        print(f"Verified districts: {stats['verified_districts']}")
        print(f"Pending processing: {stats['pending_districts']}")
        print(f"Completion: {stats['completion_pct']:.1f}%")
        print("="*60 + "\n")
        return

    if args.name:
        # Search by name
        print(f"\nSearching for: '{args.query}'\n")
        matches = validator.find_by_name(args.query)

        if not matches:
            print("❌ No matches found")
            print("\nTry:")
            print("  - Check spelling")
            print("  - Search for partial name (e.g., 'Houston' instead of 'Houston ISD')")
            print("  - Use district ID if known")
            return

        print(f"Found {len(matches)} match(es):\n")
        for i, match in enumerate(matches[:5], 1):  # Show top 5
            verified_status = "✓ VERIFIED" if match['already_verified'] else "⏳ PENDING"
            print(f"{i}. {match['name']}")
            print(f"   ID: {match['district_id']}")
            print(f"   County: {match['county']}")
            print(f"   Enrollment: {match['enrollment']}")
            print(f"   Match: {match['similarity']*100:.0f}%")
            print(f"   Status: {verified_status}\n")
    else:
        # Validate ID
        result = validator.validate_id(args.query)

        print("\n" + "="*60)
        if result['valid']:
            print(f"✓ Valid District ID: {args.query}")
            print("="*60)
            print(f"District: {result['district_name']}")
            print(f"County: {result['county']}")
            print(f"Enrollment: {result['enrollment']}")

            if result['already_verified']:
                print(f"\n⚠️  Status: ALREADY PROCESSED")
                print(f"This district is already in the verified dataset.")
                print(f"Check: districts_verified.csv or districts_complete.csv")
            else:
                print(f"\n✓ Status: READY TO PROCESS")
                print(f"This district ID is valid and not yet in the dataset.")
        else:
            print(f"❌ Invalid District ID: {args.query}")
            print("="*60)
            print(f"Error: {result['message']}")

            # Suggest similar districts if name provided
            if len(args.query) > 3:
                print("\nTry searching by name:")
                print(f"  python scripts/validate_district_id.py '{args.query}' --name")

        print("="*60 + "\n")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Usage: python scripts/validate_district_id.py [district_id or name]")
        print("       python scripts/validate_district_id.py 101912")
        print("       python scripts/validate_district_id.py 'Houston ISD' --name")
        print("       python scripts/validate_district_id.py --stats")
        sys.exit(1)

    main()
