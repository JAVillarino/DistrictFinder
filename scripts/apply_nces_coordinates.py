"""Apply NCES EDGE district office coordinates to missing district rows.

NCES EDGE publishes annual public LEA geocodes keyed by NCES district ID.
This script reads the downloaded EDGE_GEOCODE_PUBLICLEA_2324.zip file,
matches it to TEA districts by NCES District ID, and fills only rows that
do not already have latitude/longitude.

County agreement is required before accepting an NCES point. A few NCES
rows are known to carry bad county/location data for Texas districts, and
this guard prevents those points from moving dots to the wrong part of the
state.
"""

from __future__ import annotations

import csv
import zipfile
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
COMPLETE = DATA / "districts_complete.csv"
RAW_TEA = DATA / "tea_master_districts_raw.csv"
NCES_ZIP = DATA / "EDGE_GEOCODE_PUBLICLEA_2324.zip"
NCES_CACHE = DATA / "nces_district_coordinates.csv"


def clean_id(value: str) -> str:
    return (value or "").replace("'", "").strip().zfill(6)


def clean_nces_id(value: str) -> str:
    return (value or "").replace("'", "").strip().zfill(7)


def clean_county(value: str) -> str:
    return (value or "").upper().replace(" COUNTY", "").strip()


def load_tea_crosswalk() -> dict[str, dict]:
    crosswalk = {}
    with RAW_TEA.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            district_id = clean_id(row.get("District Number", ""))
            if district_id in crosswalk:
                continue
            nces_id = clean_nces_id(row.get("NCES District ID", ""))
            if not nces_id:
                continue
            crosswalk[district_id] = {
                "district_id": district_id,
                "district_name": row.get("District Name", "").strip(),
                "nces_id": nces_id,
                "county": clean_county(row.get("County Name", "")),
            }
    return crosswalk


def load_nces_coordinates() -> dict[str, dict]:
    target = "EDGE_GEOCODE_PUBLICLEA_2324/EDGE_GEOCODE_PUBLICLEA_2324.TXT"
    coordinates = {}
    with zipfile.ZipFile(NCES_ZIP) as zf:
        text = zf.read(target).decode("utf-8")
    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) < 12 or parts[2] != "48":
            continue
        latitude = parts[10].strip()
        longitude = parts[11].strip()
        if not latitude or not longitude:
            continue
        coordinates[parts[0]] = {
            "nces_id": parts[0],
            "nces_name": parts[1],
            "street": parts[3],
            "city": parts[4],
            "state": parts[5],
            "zip": parts[6],
            "county": clean_county(parts[9]),
            "latitude": latitude,
            "longitude": longitude,
            "school_year": parts[20] if len(parts) > 20 else "",
        }
    return coordinates


def write_nces_cache(rows: list[dict]) -> None:
    fieldnames = [
        "district_id", "district_name", "nces_id", "nces_name", "street",
        "city", "state", "zip", "county", "latitude", "longitude",
        "school_year", "status",
    ]
    with NCES_CACHE.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    crosswalk = load_tea_crosswalk()
    nces = load_nces_coordinates()
    with COMPLETE.open(newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    for field in ["latitude", "longitude", "coordinate_source"]:
        if field not in fieldnames:
            fieldnames.append(field)

    cache_rows = []
    updated = 0
    skipped_county = 0
    missing_nces = 0
    already_had_coordinates = 0

    for row in rows:
        district_id = row["district_id"]
        tea = crosswalk.get(district_id)
        coord = nces.get(tea["nces_id"]) if tea else None
        status = "missing_nces"
        if not tea or not coord:
            missing_nces += 1
        elif coord["county"] != tea["county"]:
            skipped_county += 1
            status = "county_mismatch"
        elif row.get("latitude") and row.get("longitude"):
            if not row.get("coordinate_source"):
                row["coordinate_source"] = "census_geocoder"
            already_had_coordinates += 1
            status = "already_populated"
        else:
            row["latitude"] = coord["latitude"]
            row["longitude"] = coord["longitude"]
            row["coordinate_source"] = "nces_edge_2023_24"
            updated += 1
            status = "applied"

        if tea and coord:
            cache_rows.append({
                "district_id": district_id,
                "district_name": row["district_name"],
                "nces_id": tea["nces_id"],
                "nces_name": coord["nces_name"],
                "street": coord["street"],
                "city": coord["city"],
                "state": coord["state"],
                "zip": coord["zip"],
                "county": coord["county"],
                "latitude": coord["latitude"],
                "longitude": coord["longitude"],
                "school_year": coord["school_year"],
                "status": status,
            })

    with COMPLETE.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    write_nces_cache(cache_rows)

    print(f"NCES Texas coordinates: {len(nces)}")
    print(f"Matched TEA districts: {len(cache_rows)}")
    print(f"Already had coordinates: {already_had_coordinates}")
    print(f"Applied missing coordinates: {updated}")
    print(f"Skipped county mismatches: {skipped_county}")
    print(f"Missing NCES matches: {missing_nces}")
    print(f"NCES cache: {NCES_CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
