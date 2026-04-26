"""Find district YouTube channels via the YouTube Data API v3.

For each district with an empty video_url, search YouTube for
  "<district name> ISD board meetings"
and pick the best channel match. Writes a YouTube channel URL into
video_url (platform=youtube) if a plausible match is found.

Why this over crawling: many districts only announce meetings on
Facebook or don't link their YT channel from their homepage. Direct YT
search finds channels regardless.

Quota usage: search.list = 100 units per call, daily quota 10k = 100
districts/day. Run in batches; resume via --skip-populated.

Usage:
    venv/bin/python scripts/discover_youtube_channels.py --limit 50
    venv/bin/python scripts/discover_youtube_channels.py --min-enroll 2000
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests

from validate_stream_matches import name_matches_ident

DATA = Path(__file__).resolve().parent.parent / "data"
SRC = DATA / "districts_complete.csv"
LOG = DATA / "youtube_discovery_log.csv"
CONFIG = Path(__file__).resolve().parent / "config.json"

API_URL = "https://www.googleapis.com/youtube/v3/search"
TIMEOUT = 10


def load_key() -> str:
    return json.load(CONFIG.open())["youtube_api_key"]


class QuotaExceeded(Exception):
    pass


def search_channel(name: str, key: str) -> tuple[str, str, str] | None:
    """Return (channel_id, channel_title, channel_url) of best match, or None."""
    q = f"{name} ISD board meetings Texas"
    params = {
        "part": "snippet",
        "q": q,
        "type": "channel",
        "maxResults": 5,
        "key": key,
        "regionCode": "US",
    }
    try:
        r = requests.get(API_URL, params=params, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"  API error: {e}", file=sys.stderr)
        return None
    if r.status_code == 403:
        body = r.text[:200].replace("\n", " ")
        print(f"  quota/403: {body}", file=sys.stderr)
        if "quota" in body.lower() or "exceeded" in body.lower():
            raise QuotaExceeded(body)
        return None
    if r.status_code != 200:
        print(f"  http {r.status_code}: {r.text[:200]}", file=sys.stderr)
        return None
    data = r.json()
    items = data.get("items", [])
    for item in items:
        title = item["snippet"]["channelTitle"]
        cid = item["snippet"]["channelId"]
        # must plausibly match the district name
        title_low = re.sub(r"[^a-z0-9]", "", title.lower())
        if name_matches_ident(name, title_low):
            url = f"https://www.youtube.com/channel/{cid}"
            return cid, title, url
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--min-enroll", type=int, default=0)
    ap.add_argument("--district", type=str, default=None)
    args = ap.parse_args()

    key = load_key()
    with SRC.open() as f:
        fieldnames = csv.DictReader(f).fieldnames
    rows = list(csv.DictReader(SRC.open()))

    todo = []
    for r in rows:
        if args.district and r["district_id"] != args.district:
            continue
        if r["video_url"].strip():
            continue
        try:
            enroll = int(r["enrollment"] or 0)
        except ValueError:
            enroll = 0
        if enroll < args.min_enroll:
            continue
        todo.append(r)
    # largest districts first (higher cost-of-failure)
    todo.sort(key=lambda r: -int(r["enrollment"] or 0))
    if args.limit:
        todo = todo[: args.limit]

    print(f"Searching YouTube for {len(todo)} districts (quota ~100/day)...",
          file=sys.stderr)

    found = 0
    log_rows = []
    for i, r in enumerate(todo, 1):
        try:
            res = search_channel(r["district_name"], key)
        except QuotaExceeded:
            print("YouTube quota exceeded; stopping early.", file=sys.stderr)
            break
        if res:
            cid, title, url = res
            r["video_url"] = url
            r["video_platform"] = "youtube"
            r["video_status"] = "verified"
            r["confidence"] = "medium"
            r["last_checked"] = date.today().isoformat()
            r["youtube_channel_id"] = cid
            r["notes"] = f"Found via YT API: channel '{title}'"
            found += 1
            print(f"[{i}/{len(todo)}] {r['district_name']} -> {title} ({url})",
                  file=sys.stderr)
            log_rows.append({
                "district_id": r["district_id"],
                "district_name": r["district_name"],
                "channel_title": title,
                "url": url,
                "status": "found",
            })
        else:
            print(f"[{i}/{len(todo)}] {r['district_name']}: no match",
                  file=sys.stderr)
            log_rows.append({
                "district_id": r["district_id"],
                "district_name": r["district_name"],
                "channel_title": "",
                "url": "",
                "status": "not_found",
            })
        # checkpoint every 10
        if i % 10 == 0:
            with SRC.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                w.writerows(rows)

    with SRC.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    write_header = not LOG.exists()
    with LOG.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["district_id", "district_name",
                                          "channel_title", "url", "status"])
        if write_header:
            w.writeheader()
        w.writerows(log_rows)

    print(f"\nDone. Found {found} / {len(todo)} YouTube channels",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
