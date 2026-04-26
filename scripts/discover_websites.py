"""Populate missing website_url values via URL pattern guessing + HEAD check.

For each district with empty website_url, generate plausible URL candidates
from its name (`<slug>isd.org`, `<slug>isd.net`, `<acronym>isd.org`, ...)
then HTTP HEAD each candidate. First one that returns a 2xx/3xx response
wins. Falls back to GET if HEAD is refused.

Run in batches; writes back to data/districts_complete.csv as it goes.

Usage:
    python scripts/discover_websites.py               # all missing
    python scripts/discover_websites.py --limit 50    # first 50
    python scripts/discover_websites.py --min-enroll 500  # only >= 500 students
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import concurrent.futures as cf
from pathlib import Path

import requests

from validate_stream_matches import (
    district_tokens,
    district_acronyms,
    COMPOUND_SPLITS,
)

DATA = Path(__file__).resolve().parent.parent / "data"
SRC = DATA / "districts_complete.csv"
LOG = DATA / "website_discovery_log.csv"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/123.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 8
WORKERS = 12


def _slug_variants(name: str) -> list[str]:
    """Return ordered candidate URL "slugs" (no TLD) from a district name.

    Short multi-token acronyms (e.g. 'p' from PALESTINE, 's' from SEYMOUR)
    are suppressed — they collide with famous districts like Plano and
    Spring, and the pattern guesser was wrongly picking up pisd.org for
    every P-named district. Acronyms are only tried when they have >= 2
    characters, i.e. for multi-word district names.
    """
    low = re.sub(r"[^a-z0-9\s-]", " ", name.lower())
    parts = [p for p in re.split(r"[\s-]+", low)
             if p and p not in {"isd", "cisd", "msd", "the"}]
    if not parts:
        return []
    expanded: list[str] = []
    for p in parts:
        expanded.extend(COMPOUND_SPLITS.get(p, [p]))
    parts_no_county = [p for p in parts if p != "county"]

    concat = "".join(parts)
    concat_no_county = "".join(parts_no_county)
    concat_hyph = "-".join(parts)
    acr = "".join(p[0] for p in parts)
    acr_exp = "".join(p[0] for p in expanded)
    first_word = parts[0]

    variants = [
        concat + "isd",
        concat_no_county + "isd",
        first_word + "isd",
        concat_hyph + "-isd",
        concat + "schools",
        first_word + "-isd",
        concat,
        concat + "cisd",
    ]
    # Only include acronym slugs when the acronym is >= 2 chars (i.e. the
    # district name has at least two words). Single-letter + "isd" is far
    # too collision-prone.
    if len(acr) >= 2:
        variants.insert(3, acr + "isd")
    if len(acr_exp) >= 2 and acr_exp != acr:
        variants.insert(4, acr_exp + "isd")
    variants.append("my" + first_word + "isd")

    seen = set()
    out = []
    for v in variants:
        if v and v not in seen and len(v) >= 4:
            seen.add(v)
            out.append(v)
    return out


TLDS = [".org", ".net", ".us", ".com", ".edu"]


def url_candidates(name: str) -> list[str]:
    slugs = _slug_variants(name)
    urls = []
    for s in slugs:
        for tld in TLDS:
            urls.append(f"https://www.{s}{tld}")
            urls.append(f"https://{s}{tld}")
    return urls


def _same_host_family(original: str, final: str) -> bool:
    """Redirect-integrity check — accept only when the final host shares
    at least a 4-char substring with the original. Rejects parked/hijacked
    domains that redirect to unrelated hosts."""
    from urllib.parse import urlparse
    a = urlparse(original).hostname or ""
    b = urlparse(final).hostname or ""
    a = a.replace("www.", "")
    b = b.replace("www.", "")
    if a == b or b.endswith("." + a) or a.endswith("." + b):
        return True
    # any 4-char substring in common
    for i in range(len(a) - 3):
        if a[i:i+4] in b:
            return True
    return False


def check(url: str) -> bool:
    """True if the hostname resolves, responds with a not-clearly-dead
    status, and any redirects stay within the same host family.

    Accepts 2xx, 3xx, 401, 403, 451 as "live" including when the server
    is bot-blocking. Rejects 5xx. Rejects redirects to unrelated domains.
    """
    try:
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    except requests.RequestException:
        return False
    sc = r.status_code
    final = r.url
    if not _same_host_family(url, final):
        return False
    if sc < 400 or sc in (401, 403, 451):
        return True
    if sc in (405, 501):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                             allow_redirects=True, stream=True)
            r.close()
        except requests.RequestException:
            return False
        if not _same_host_family(url, r.url):
            return False
        return r.status_code < 400 or r.status_code in (401, 403, 451)
    return False


def find_website(name: str) -> str | None:
    for url in url_candidates(name):
        if check(url):
            return url
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--min-enroll", type=int, default=0)
    ap.add_argument("--district", type=str, default=None,
                    help="process a single district by id")
    args = ap.parse_args()

    with SRC.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    todo = []
    for r in rows:
        if args.district and r["district_id"] != args.district:
            continue
        if r["website_url"].strip():
            continue
        try:
            enroll = int(r["enrollment"] or 0)
        except ValueError:
            enroll = 0
        if enroll < args.min_enroll:
            continue
        todo.append(r)
    if args.limit:
        todo = todo[: args.limit]

    print(f"Processing {len(todo)} districts (workers={WORKERS})...", file=sys.stderr)

    found = 0
    log_rows = []
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(find_website, r["district_name"]): r for r in todo}
        for i, fut in enumerate(cf.as_completed(futures), 1):
            r = futures[fut]
            try:
                url = fut.result()
            except Exception as e:
                url = None
                print(f"[{i}/{len(todo)}] {r['district_name']}: ERROR {e}", file=sys.stderr)
            if url:
                r["website_url"] = url
                found += 1
                print(f"[{i}/{len(todo)}] {r['district_name']} -> {url}", file=sys.stderr)
            else:
                print(f"[{i}/{len(todo)}] {r['district_name']}: not found", file=sys.stderr)
            log_rows.append({
                "district_id": r["district_id"],
                "district_name": r["district_name"],
                "url": url or "",
                "status": "found" if url else "not_found",
            })
            # Periodic checkpoint write so a Ctrl-C doesn't lose progress.
            if i % 50 == 0:
                with SRC.open("w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=fieldnames)
                    w.writeheader()
                    w.writerows(rows)

    # final write
    with SRC.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    # append discovery log
    write_header = not LOG.exists()
    with LOG.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["district_id", "district_name", "url", "status"])
        if write_header:
            w.writeheader()
        w.writerows(log_rows)

    print(f"\nDone. Found {found} / {len(todo)} ({found/len(todo)*100:.1f}%)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
