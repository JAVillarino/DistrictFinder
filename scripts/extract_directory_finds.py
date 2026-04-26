"""Parse scripts/directory_scraper.log and write data/directory_results.csv
with only the real platform finds (Swagit/BoardDocs/Granicus/iqm2).
Drops Legistar wildcard-DNS false positives and de-dupes.

Intended for when the platform scraper is still running in its junk
Legistar phase — we extract the valuable data so far, kill the scraper,
and move on.
"""
from __future__ import annotations
import csv
import re
from pathlib import Path

LOG = Path("scripts/directory_scraper.log")
OUT = Path("data/directory_results.csv")

# ordered: first one wins if the same district appears across phases
KEEP_PLATFORMS = [
    ("swagit",   "swagit.com"),
    ("granicus", "granicus.com"),
    ("iqm2",     "iqm2.com"),
    ("boarddocs","go.boarddocs.com"),
]


def classify(url: str) -> str | None:
    u = url.lower()
    if "legistar.com" in u:
        return None
    for plat, host in KEEP_PLATFORMS:
        if host in u:
            return plat
    return None


def main() -> int:
    pattern = re.compile(r"FOUND(?: \(HEAD\))?: (.+?) -> (\S+)")
    seen_ids: dict[str, dict] = {}

    # need the district_id map; load from districts_complete.csv
    districts = {
        r["district_name"]: r for r in csv.DictReader(open("data/districts_complete.csv"))
    }

    for line in LOG.read_text().splitlines():
        m = pattern.search(line)
        if not m:
            continue
        name = m.group(1).strip()
        url = m.group(2).strip().rstrip(" ()")
        plat = classify(url)
        if not plat:
            continue
        dist = districts.get(name)
        if not dist:
            continue
        # first hit wins (earlier phases first; Swagit is most authoritative)
        if dist["district_id"] in seen_ids:
            continue
        seen_ids[dist["district_id"]] = {
            "district_id": dist["district_id"],
            "district_name": name,
            "county": dist.get("county", ""),
            "enrollment": dist.get("enrollment", ""),
            "website_url": dist.get("website_url", ""),
            "video_platform": plat,
            "video_url": url,
            "archive_start_year": "",
            "youtube_channel_id": "",
            "notes": f"Directory scraper: {plat}",
            "confidence": "high",
            "last_checked": "2026-04-21",
            "video_status": "directory_found",
        }

    fields = [
        "district_id","district_name","county","enrollment","website_url",
        "video_platform","video_url","archive_start_year","youtube_channel_id",
        "notes","confidence","last_checked","video_status",
    ]
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(seen_ids.values())
    print(f"Wrote {len(seen_ids)} directory finds to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
