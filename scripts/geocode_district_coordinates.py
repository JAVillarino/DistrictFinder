"""Geocode TEA district office addresses and add latitude/longitude columns.

Uses the public U.S. Census batch geocoder, keyed by TEA district_id.
Writes a reusable cache to data/district_coordinates.csv and updates
data/districts_complete.csv in place. Existing coordinates are preserved
unless --refresh is passed.

Run:
    python scripts/geocode_district_coordinates.py
    python scripts/geocode_district_coordinates.py --refresh
"""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
COMPLETE = DATA / "districts_complete.csv"
RAW_TEA = DATA / "tea_master_districts_raw.csv"
CACHE = DATA / "district_coordinates.csv"

CENSUS_BATCH_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BATCH_SIZE = 1000
TIMEOUT = 60


def clean_id(value: str) -> str:
    return (value or "").replace("'", "").strip().zfill(6)


def is_po_box(value: str) -> bool:
    normalized = (value or "").upper().replace(".", " ")
    return "PO BOX" in normalized or "P O BOX" in normalized or normalized.startswith("BOX ")


def load_complete() -> tuple[list[dict], list[str]]:
    with COMPLETE.open(newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def load_raw_addresses(district_ids: set[str]) -> dict[str, dict]:
    addresses = {}
    fallback_school_addresses = {}
    with RAW_TEA.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            did = clean_id(row.get("District Number", ""))
            if did not in district_ids:
                continue
            street = (row.get("District Street Address") or "").strip()
            city = (row.get("District City") or "").strip()
            state = (row.get("District State") or "TX").strip() or "TX"
            zip_code = (row.get("District Zip") or "").strip()
            school_street = (row.get("School Street Address") or "").strip()
            if did not in fallback_school_addresses and school_street and not is_po_box(school_street):
                fallback_school_addresses[did] = {
                    "district_id": did,
                    "street": school_street,
                    "city": (row.get("School City") or "").strip() or city,
                    "state": (row.get("School State") or "TX").strip() or state,
                    "zip": (row.get("School Zip") or "").strip() or zip_code,
                }
            if did not in addresses and street and city and zip_code and not is_po_box(street):
                addresses[did] = {
                    "district_id": did,
                    "street": street,
                    "city": city,
                    "state": state,
                    "zip": zip_code,
                }
    for did, address in fallback_school_addresses.items():
        addresses.setdefault(did, address)
    return addresses


def load_cache() -> dict[str, dict]:
    if not CACHE.exists():
        return {}
    with CACHE.open(newline="") as f:
        return {row["district_id"]: row for row in csv.DictReader(f)}


def geocode_batch(addresses: list[dict]) -> dict[str, dict]:
    rows = []
    for item in addresses:
        rows.append([
            item["district_id"],
            item["street"],
            item["city"],
            item["state"],
            item["zip"],
        ])

    body = io.StringIO()
    writer = csv.writer(body)
    writer.writerows(rows)

    response = requests.post(
        CENSUS_BATCH_URL,
        files={"addressFile": ("district_addresses.csv", body.getvalue(), "text/csv")},
        data={"benchmark": "Public_AR_Current"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    results = {}
    for row in csv.reader(io.StringIO(response.text)):
        if len(row) < 8:
            continue
        did, input_address, match, match_type, matched_address, coordinates, tiger_line_id, side = row[:8]
        longitude = ""
        latitude = ""
        if match == "Match" and "," in coordinates:
            lon, lat = [part.strip() for part in coordinates.split(",", 1)]
            longitude = lon
            latitude = lat
        results[did] = {
            "district_id": did,
            "latitude": latitude,
            "longitude": longitude,
            "geocode_status": match,
            "geocode_match_type": match_type,
            "matched_address": matched_address,
            "tiger_line_id": tiger_line_id,
            "side": side,
            "input_address": input_address,
        }
    return results


def save_cache(rows: dict[str, dict]) -> None:
    fieldnames = [
        "district_id", "latitude", "longitude", "geocode_status",
        "geocode_match_type", "matched_address", "tiger_line_id", "side",
        "input_address",
    ]
    with CACHE.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for did in sorted(rows):
            writer.writerow({field: rows[did].get(field, "") for field in fieldnames})


def update_complete(rows: list[dict], fieldnames: list[str], coordinates: dict[str, dict]) -> int:
    for field in ["latitude", "longitude", "coordinate_source"]:
        if field not in fieldnames:
            fieldnames.append(field)

    updated = 0
    for row in rows:
        coord = coordinates.get(row["district_id"])
        if not coord or not coord.get("latitude") or not coord.get("longitude"):
            continue
        if row.get("latitude") == coord["latitude"] and row.get("longitude") == coord["longitude"]:
            if not row.get("coordinate_source"):
                row["coordinate_source"] = "census_geocoder"
            continue
        row["latitude"] = coord["latitude"]
        row["longitude"] = coord["longitude"]
        row["coordinate_source"] = "census_geocoder"
        updated += 1

    with COMPLETE.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="ignore cached coordinates")
    args = parser.parse_args()

    rows, fieldnames = load_complete()
    district_ids = {row["district_id"] for row in rows}
    raw_addresses = load_raw_addresses(district_ids)
    coordinates = {} if args.refresh else load_cache()

    missing = [
        raw_addresses[did] for did in sorted(raw_addresses)
        if did not in coordinates or not coordinates[did].get("latitude") or not coordinates[did].get("longitude")
    ]

    print(f"Complete rows: {len(rows)}")
    print(f"TEA office addresses: {len(raw_addresses)}")
    print(f"Cached coordinate rows: {len(coordinates)}")
    print(f"Need geocoding: {len(missing)}")

    for start in range(0, len(missing), BATCH_SIZE):
        batch = missing[start:start + BATCH_SIZE]
        print(f"Geocoding batch {start + 1}-{start + len(batch)}...")
        coordinates.update(geocode_batch(batch))
        save_cache(coordinates)

    updated = update_complete(rows, fieldnames, coordinates)
    matched = sum(1 for item in coordinates.values() if item.get("latitude") and item.get("longitude"))
    print(f"Matched coordinates: {matched}")
    print(f"Updated districts_complete.csv rows: {updated}")
    print(f"Coordinate cache: {CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
