"""Reassign CLEAR'd video URLs back to the districts their URLs actually identify.

For each row flagged CLEAR in stream_validation_report.csv:
  - Parse the URL signature.
  - Find the best-matching district by name token / acronym.
  - If that district's current video_url is empty, move the URL over
    (including platform, archive_start_year, youtube_channel_id).

Platform-generic URLs (citizenportal.ai, panopto, boardbook/N, opaque YT
channel IDs, youtube.com homepage, youtube playlist) can't be uniquely
attributed to a district from URL alone, so they are not reassigned.

Run: python scripts/reassign_stream_urls.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from validate_stream_matches import (
    url_signature,  # noqa: F401 (re-export useful in REPL/debug)
    name_matches_ident,
    district_tokens,
    district_acronyms,  # noqa: F401
    _boundary_contains_token,
    FORCE_CLEAR,
    FORCE_ASSIGN,
)

DATA = Path(__file__).resolve().parent.parent / "data"
SRC = DATA / "districts_complete.csv"
REPORT = DATA / "stream_validation_report.csv"

UNVERIFIABLE = {
    "citizenportal", "panopto", "boardbook",
    "yt_channel_id", "yt_playlist", "yt_generic",
}


def enrollment(row: dict) -> int:
    try:
        return int(row.get("enrollment") or 0)
    except ValueError:
        return 0


def token_hit_count(name: str, ident_low: str) -> int:
    """How many distinct district-name tokens (>=3 chars) appear in ident at a boundary."""
    return sum(
        1 for t in district_tokens(name)
        if len(t) >= 3 and _boundary_contains_token(ident_low, t)
    )


def looks_like_strong_match(name: str, ident_low: str) -> bool:
    """True if the full concat of the name's tokens is a prefix of ident.

    e.g. FORT WORTH ISD on "fortworthisd.granicus.com" -> True.
         FORT BEND ISD on same ident -> False (concat "fortbend" not a prefix).
    """
    tokens = [t for t in district_tokens(name) if len(t) >= 3]
    if len(tokens) < 2:
        return False
    concat = "".join(sorted(tokens, key=lambda t: -len(t)))  # order-independent
    # also try the canonical order — prefix check from name
    import re as _re
    parts = [p for p in _re.split(r"[\s-]+", name.lower()) if p and p not in {"isd","cisd","msd"}]
    canonical = "".join(parts)
    return canonical in ident_low


def best_target(rows: list[dict], signature: tuple[str, str]) -> dict | None:
    """Return the district row whose name best matches the URL signature."""
    plat, ident = signature
    if plat in UNVERIFIABLE:
        return None
    ident_low = ident.lower()
    sig_key = f"{plat}:{ident}"
    # Manual override takes precedence.
    if sig_key in FORCE_ASSIGN:
        forced_id = FORCE_ASSIGN[sig_key]
        for r in rows:
            if r["district_id"] == forced_id:
                return r
    cands = []
    for r in rows:
        # Skip districts explicitly forbidden from owning this URL.
        if (r["district_id"], sig_key) in FORCE_CLEAR:
            continue
        hit = name_matches_ident(r["district_name"], ident_low)
        if hit:
            cands.append((r, hit))
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0][0]
    # score priorities:
    # 1. canonical-name prefix (e.g. "fortworth" appears contiguously) -
    #    strongest possible signal.
    # 2. number of distinct tokens matched (>= 2 beats 1)
    # 3. length of the longest matched string
    # 4. county name appears in ident (>= 5 char county tokens only)
    # 5. enrollment
    def score(c):
        r, hit = c
        name = r["district_name"]
        prefix_bonus = 2 if looks_like_strong_match(name, ident_low) else 0
        hits = token_hit_count(name, ident_low)
        county_first = (r.get("county") or "").split()[0].lower()
        county_bonus = 1 if (len(county_first) >= 5 and county_first in ident_low) else 0
        return (prefix_bonus, hits, len(hit), county_bonus, enrollment(r))
    cands.sort(key=score, reverse=True)
    return cands[0][0]


def main() -> int:
    with SRC.open() as f:
        fieldnames = csv.DictReader(f).fieldnames
    rows = list(csv.DictReader(SRC.open()))

    report_by_id: dict[str, dict] = {
        r["district_id"]: r for r in csv.DictReader(REPORT.open())
    }

    # Lookup by district_id to mutate rows in place
    row_by_id: dict[str, dict] = {r["district_id"]: r for r in rows}

    reassigned = 0
    conflicts = 0
    skipped_unverifiable = 0
    log = []
    for src_id, rep in report_by_id.items():
        if rep["decision"] != "CLEAR":
            continue
        plat, ident = rep["signature"].split(":", 1)
        if plat in UNVERIFIABLE:
            skipped_unverifiable += 1
            continue
        target = best_target(rows, (plat, ident))
        if target is None:
            continue
        if target["district_id"] == src_id:
            continue
        if target["video_url"].strip():
            # target already has a URL we trust (KEEP) or another reassignment
            # already landed there; record and skip.
            conflicts += 1
            log.append(f"CONFLICT: {ident} -> {target['district_name']} but it already has {target['video_url']}")
            continue

        # reassign
        target["video_platform"] = rep["video_platform"]
        target["video_url"] = rep["video_url"]
        target["video_status"] = "verified"
        target["confidence"] = "medium"
        target["last_checked"] = "2026-04-17"
        target["notes"] = f"Reassigned from {rep['district_name']} based on URL matching '{target['district_name']}'"
        # archive_start_year and youtube_channel_id aren't in the report;
        # they were cleared with the source row, which is acceptable since
        # they were probably stale too.
        reassigned += 1
        log.append(f"REASSIGN: {rep['video_url']} : {rep['district_name']} -> {target['district_name']}")

    with SRC.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    for line in log:
        print(line)
    print()
    print(f"Reassigned: {reassigned}")
    print(f"Conflicts (target already had a URL): {conflicts}")
    print(f"Skipped (platform-generic / unverifiable URLs): {skipped_unverifiable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
