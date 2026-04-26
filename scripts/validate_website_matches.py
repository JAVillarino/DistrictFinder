"""Validate district <-> website_url pairings in districts_complete.csv.

Mirror of validate_stream_matches.py but scans the `website_url` column.
Uses the same name-matching heuristics. Writes a report to
`data/website_validation_report.csv`.

Run: python scripts/validate_website_matches.py
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from pathlib import Path

from validate_stream_matches import (
    url_signature,
    name_matches_ident,
    classify,
    district_tokens,  # noqa: F401
)

DATA = Path(__file__).resolve().parent.parent / "data"
SRC = Path(os.environ.get("WEBSITE_VALIDATE_SRC", DATA / "districts_complete.csv"))
REPORT = Path(os.environ.get("WEBSITE_VALIDATE_REPORT", DATA / "website_validation_report.csv"))

# known false-positive (district_id, sig) to force CLEAR
FORCE_CLEAR = {
    ("227901", "website:aisd.net"),       # Austin ISD - aisd.net is Arlington's
    ("221912", "website:wylieisd.net"),   # Wylie Taylor - wylieisd.net is Collin Wylie's
}


def main() -> int:
    rows = list(csv.DictReader(SRC.open()))
    sig_rows: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        if r["website_url"].strip():
            sig_rows[url_signature(r["website_url"])].append(r)

    import re as _re
    from validate_stream_matches import STOPWORDS as _STOPWORDS

    def enrollment(r: dict) -> int:
        try:
            return int(r.get("enrollment") or 0)
        except ValueError:
            return 0

    def canonical_concat(name: str) -> str:
        low = _re.sub(r"[^a-z0-9\s-]", " ", name.lower())
        parts = [p for p in _re.split(r"[\s-]+", low) if p and p not in _STOPWORDS]
        return "".join(parts)

    def owner_score(r: dict, ident_low: str) -> tuple:
        cc = canonical_concat(r["district_name"])
        prefix_bonus = 2 if cc and ident_low.startswith(cc) else 0
        substr_bonus = 1 if cc and cc in ident_low else 0
        cf = (r.get("county") or "").split()[0].lower()
        county_bonus = 1 if (len(cf) >= 5 and cf in ident_low) else 0
        return (prefix_bonus, substr_bonus, county_bonus, enrollment(r))

    sig_owner: dict[tuple[str, str], str | None] = {}
    for sig, shared in sig_rows.items():
        plat, ident = sig
        if plat in {"citizenportal", "panopto", "boardbook",
                    "yt_channel_id", "yt_playlist", "yt_generic"}:
            sig_owner[sig] = None
            continue
        matchers = [
            r for r in shared
            if name_matches_ident(r["district_name"], ident.lower())
            and (r["district_id"], f"{plat}:{ident}") not in FORCE_CLEAR
        ]
        if not matchers:
            sig_owner[sig] = None
        elif len(matchers) == 1:
            sig_owner[sig] = matchers[0]["district_id"]
        else:
            ident_low = ident.lower()
            best = max(matchers, key=lambda r: owner_score(r, ident_low))
            sig_owner[sig] = best["district_id"]

    out_rows = []
    summary = {"KEEP": 0, "CLEAR": 0, "REVIEW": 0}
    for r in rows:
        url = r["website_url"].strip()
        if not url:
            continue
        sig = url_signature(url)
        count = len(sig_rows[sig])
        owner = sig_owner[sig]
        dup_has_owner = bool(owner and owner != r["district_id"])
        sig_key = f"{sig[0]}:{sig[1]}"
        if (r["district_id"], sig_key) in FORCE_CLEAR:
            decision, reason = "CLEAR", "FORCE_CLEAR: known false acronym match"
        else:
            decision, reason = classify(r["district_name"], url, sig, count, dup_has_owner)
        summary[decision] += 1
        out_rows.append({
            "district_id": r["district_id"],
            "district_name": r["district_name"],
            "website_url": url,
            "signature": sig_key,
            "dup_count": count,
            "decision": decision,
            "reason": reason,
        })

    with REPORT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    total = sum(summary.values())
    print(f"Scanned {total} populated website_url rows")
    for k, v in summary.items():
        print(f"  {k:7s} {v}")
    print(f"Report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
