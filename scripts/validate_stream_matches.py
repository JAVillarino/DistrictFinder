"""Validate district <-> video URL pairings in districts_complete.csv.

Heuristic: every populated (district_name, video_url) pair is checked for a
name/URL agreement. Clear mismatches (wrong subdomain, wrong youtube handle,
wrong domain) are flagged as CLEAR. URLs that are platform-generic or whose
identity cannot be derived from the URL alone are flagged as REVIEW. Strong
matches are KEEP.

Run: python scripts/validate_stream_matches.py
Writes: data/stream_validation_report.csv
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import os
DATA = Path(__file__).resolve().parent.parent / "data"
SRC = Path(os.environ.get("VALIDATE_SRC", DATA / "districts_complete.csv"))
REPORT = Path(os.environ.get("VALIDATE_REPORT", DATA / "stream_validation_report.csv"))

STOPWORDS = {
    "isd", "cisd", "msd", "county", "the", "of", "and",
    "school", "district", "independent",
}


def district_tokens(name: str) -> set[str]:
    """Lowercase alphanumeric tokens, stopwords removed."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s-]", " ", name)
    tokens = {t for t in re.split(r"[\s-]+", name) if t and t not in STOPWORDS}
    # common abbreviations/expansions
    if "ft" in tokens:
        tokens.add("fort")
    if "fort" in tokens:
        tokens.add("ft")
    if "mt" in tokens:
        tokens.add("mount")
    if "st" in tokens:
        tokens.add("saint")
    return tokens


# Known false-positive acronym matches: (district_id, URL signature) that
# will always be forced to CLEAR. These are cases where an acronym
# accidentally collides with another well-known district's domain.
FORCE_CLEAR: set[tuple[str, str]] = {
    ("227901", "website:aisd.net"),       # Austin ISD - aisd.net is Arlington's
    ("221912", "website:wylieisd.net"),   # Wylie Taylor - wylieisd.net is Collin Wylie's
}

# Manual URL -> district_id overrides used when the heuristic ranking would
# pick the wrong owner (usually because multiple districts share an acronym
# and enrollment ordering doesn't match reality).
FORCE_ASSIGN: dict[str, str] = {
    "website:aisd.net": "220901",       # Arlington ISD
    "website:wylieisd.net": "043914",   # Wylie ISD (Collin County)
}

# Districts whose single-word name is actually a compound; list the
# sub-parts so acronyms/matches work. Keep keys lowercase, space-separated.
COMPOUND_SPLITS = {
    "channelview": ["channel", "view"],
    "goosecreek": ["goose", "creek"],
    "brazosport": ["brazos", "port"],
    "lovejoy": ["love", "joy"],
    "newcaney": ["new", "caney"],
    "grapevine": ["grape", "vine"],
    "northwest": ["north", "west"],
    "northside": ["north", "side"],
    "southside": ["south", "side"],
    "southwest": ["south", "west"],
    "eastcentral": ["east", "central"],
    "birdville": ["bird", "ville"],
    "friendswood": ["friends", "wood"],
    "pflugerville": ["pf"],
    "sweeny": ["sweeny"],
    "brownwood": ["brown", "wood"],
    "jacksonville": ["jackson", "ville"],
    "collinsville": ["collins", "ville"],
    "stephenville": ["stephen", "ville"],
    "brownsville": ["browns", "ville"],
    "gainesville": ["gaines", "ville"],
    "centerville": ["center", "ville"],
    "hitchcock": ["hitchcock"],
    "angleton": ["angleton"],
    "brookeland": ["brook", "eland"],
    "woodville": ["wood", "ville"],
    "palestine": ["palestine"],
    "paducah": ["paducah"],
    "huntsville": ["hunts", "ville"],
    "huntington": ["hunting", "ton"],
    "jacksboro": ["jacks", "boro"],
    "whiteface": ["white", "face"],
    "whiteoak": ["white", "oak"],
    "redoak": ["red", "oak"],
    "bayview": ["bay", "view"],
    "crystalcity": ["crystal", "city"],
    "eaglepass": ["eagle", "pass"],
    "fortbend": ["fort", "bend"],
    "fortworth": ["fort", "worth"],
    "fortstockton": ["fort", "stockton"],
    "hearne": ["hearne"],
    "ingleside": ["ingle", "side"],
    "kingsville": ["kings", "ville"],
    "laporte": ["la", "porte"],
    "lubbockcooper": ["lubbock", "cooper"],
    "medinavalley": ["medina", "valley"],
    "portlavaca": ["port", "lavaca"],
    "redcreek": ["red", "creek"],
    "rosebud-lott": ["rose", "bud", "lott"],
    "southlake": ["south", "lake"],
    "sundown": ["sun", "down"],
    "sunnyvale": ["sunny", "vale"],
    "weatherford": ["weather", "ford"],
    "wimberley": ["wimberley"],
}


def district_acronyms(name: str) -> set[str]:
    """Return plausible URL acronyms for a district name.

    Generates multiple parse variants: original tokens, compound-expanded
    tokens, and (for districts whose name contains "COUNTY") variants
    that keep vs drop the word "county", because some districts include
    it in their acronym (e.g. 'CULBERSON COUNTY-ALLAMOORE' -> 'cca') and
    some don't (ector county -> 'ec').
    """
    low = re.sub(r"[^a-z0-9\s-]", " ", name.lower())
    base_parts = [p for p in re.split(r"[\s-]+", low) if p and p not in STOPWORDS]
    if not base_parts:
        return set()
    variants = [base_parts]
    # compound-expanded variant
    expanded: list[str] = []
    for p in base_parts:
        expanded.extend(COMPOUND_SPLITS.get(p, [p]))
    if expanded != base_parts:
        variants.append(expanded)
    # "county" kept variant: re-parse without stripping "county"
    parts_with_county = [p for p in re.split(r"[\s-]+", low)
                         if p and p not in (STOPWORDS - {"county"})]
    if parts_with_county != base_parts:
        variants.append(parts_with_county)

    out: set[str] = set()
    for parts in variants:
        acr = "".join(p[0] for p in parts)
        concat = "".join(parts)
        out.update({acr, acr + "isd", acr + "cisd", acr + "msd", concat, concat + "isd"})
        out.add("my" + acr + "isd")
        if len(parts) >= 2:
            out.add("".join(p[0] for p in parts[:-1]) + parts[-1])
            out.add(parts[0][0] + parts[1][0])
    return {a for a in out if len(a) >= 2}


def url_signature(url: str) -> tuple[str, str]:
    """Return (platform_key, identifying_string) for the URL.

    identifying_string is the piece expected to contain the district name.
    platform_key tells us how discriminating the string is.
    """
    u = url.strip()
    low = u.lower()
    try:
        parsed = urlparse(u)
    except Exception:
        return ("unknown", low)

    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()

    # swagit: the subdomain usually encodes the district
    if "swagit.com" in host:
        sub = host.split(".swagit.com")[0]
        sub = sub.replace(".new", "").replace("new.", "")
        return ("swagit", sub)

    # youtube channel handles / custom URLs
    if "youtube.com" in host or "youtu.be" in host:
        m = re.search(r"/@([^/?]+)", path + "?" + (parsed.query or ""))
        if m:
            return ("yt_handle", m.group(1))
        m = re.search(r"/user/([^/?]+)", path)
        if m:
            return ("yt_user", m.group(1))
        m = re.search(r"/c/([^/?]+)", path)
        if m:
            return ("yt_c", m.group(1))
        # /channel/UCxxxxxx -> opaque ID, cannot validate from URL
        if "/channel/" in path:
            return ("yt_channel_id", path.split("/channel/")[-1].strip("/"))
        if "/playlist" in path:
            # playlist URL - no district info
            return ("yt_playlist", parsed.query or "")
        # bare youtube.com
        if path in ("", "/"):
            return ("yt_generic", "")
        return ("yt_other", path.strip("/"))

    # boardbook: organization id — cannot validate from URL alone
    if "boardbook.org" in host:
        m = re.search(r"organization/(\d+)", path)
        return ("boardbook", m.group(1) if m else path)

    # platform-generic landing pages — cannot validate from URL alone
    if "citizenportal.ai" in host:
        return ("citizenportal", "")
    if host.endswith("panopto.com") or "hosted.panopto.com" in host:
        return ("panopto", host)
    if "granicus.com" in host:
        # subdomain usually encodes district
        sub = host.split(".granicus.com")[0]
        return ("granicus", sub)
    if "iqm2.com" in host:
        sub = host.split(".iqm2.com")[0]
        return ("iqm2", sub)
    if "diligent.community" in host:
        sub = host.split(".diligent.community")[0]
        return ("diligent", sub)

    # generic website - use the root hostname sans TLD
    h = host
    if h.startswith("www."):
        h = h[4:]
    return ("website", h)


SUFFIXES = (
    "isd|cisd|msd|tv|tx|live|news|media|channel|schools|athletics|"
    "bobcats|bulldogs|eagles|panthers|tigers|mustangs|cougars|wildcats|"
    "warriors|raiders|rams|rangers|hawks|lions|knights|pirates|broncos|"
    "chargers|cardinals|falcons|patriots|trojans"
)

def _boundary_contains_token(ident_low: str, needle: str) -> bool:
    """Real-word tokens. 3-char tokens need a right-side boundary (to
    reject 'arp' in 'sharpschool'); 4+ char tokens are rare enough that
    a plain substring match is safe and also catches things like
    'ector' in 'ectorcountyisd'.
    """
    if len(needle) >= 4:
        return needle in ident_low
    return bool(re.search(
        rf"{re.escape(needle)}({SUFFIXES}|[^a-z]|$)",
        ident_low,
    ))


def _boundary_contains_acronym(ident_low: str, needle: str) -> bool:
    """Acronyms (made-up letter combos) need both-side boundaries so
    'tisd' doesn't match inside 'bmtisd'. Hyphens in the ident are
    normalized away so 'piisd' matches 'pi-isd.net'. Right side also
    accepts channel/media suffixes so '@HCISDTV' matches Harlingen CISD.
    """
    normalized = ident_low.replace("-", "").replace("_", "")
    return bool(re.search(
        rf"(^|[^a-z]){re.escape(needle)}({SUFFIXES}|[^a-z]|$)",
        normalized,
    ))


def _boundary_contains(ident_low: str, needle: str) -> bool:
    return _boundary_contains_acronym(ident_low, needle)


def name_matches_ident(name: str, ident_low: str) -> str | None:
    """Return the longest matching token/acronym, or None.

    Both tokens and acronyms must appear at URL-like boundaries to avoid
    coincidental substring matches (e.g. "arp" inside "sharpschool").
    Longer matches outrank shorter ones.
    """
    tokens = district_tokens(name)
    best: str | None = None
    for t in tokens:
        if len(t) < 3:
            continue
        if _boundary_contains_token(ident_low, t):
            if best is None or len(t) > len(best):
                best = t
    for a in district_acronyms(name):
        if len(a) < 3:
            continue
        if _boundary_contains_acronym(ident_low, a):
            if best is None or len(a) > len(best):
                best = a
    return best


def classify(name: str, url: str, signature: tuple[str, str], dup_count: int,
             dup_has_owner: bool) -> tuple[str, str]:
    """Return (decision, reason). decision in {KEEP, CLEAR, REVIEW}.

    dup_has_owner: another district in the CSV legitimately matches this URL.
    """
    plat, ident = signature
    ident_low = ident.lower()

    # platform-generic, unverifiable from URL alone
    if plat in {"citizenportal", "panopto", "boardbook", "yt_channel_id", "yt_playlist", "yt_generic"}:
        if dup_count > 1:
            return ("CLEAR", f"{plat} URL shared by {dup_count} districts; not uniquely a {name} URL")
        return ("REVIEW", f"{plat} URL is platform-generic, cannot be verified from URL alone")

    if not ident_low:
        return ("REVIEW", f"{plat} with no identifier to compare")

    # If this row doesn't own the URL but another district does, clear it
    # even if the token matches (same-named districts can both "match" but
    # only one actually operates the channel/domain).
    if dup_has_owner:
        return ("CLEAR", f"{plat}:{ident} is another district's URL (shared by {dup_count}, one owns it)")

    hit = name_matches_ident(name, ident_low)
    if hit:
        return ("KEEP", f"{plat}:{ident} matches '{hit}'")
    if dup_count > 1:
        return ("CLEAR", f"{plat}:{ident} does not match and is shared by {dup_count} districts")
    return ("CLEAR", f"{plat}:{ident} does not contain any token or acronym of '{name}'")


def main() -> int:
    rows = list(csv.DictReader(SRC.open()))
    # index rows with video_urls by URL signature, to detect reuse and
    # determine whether any of the sharing districts legitimately owns it.
    sig_rows: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        if r["video_url"].strip():
            sig_rows[url_signature(r["video_url"])].append(r)

    def enrollment(r: dict) -> int:
        try:
            return int(r.get("enrollment") or 0)
        except ValueError:
            return 0

    def canonical_concat(name: str) -> str:
        """Lowercase alphanumeric concat of non-stopword tokens, e.g.
        'MEDINA VALLEY ISD' -> 'medinavalley', 'MEDINA ISD' -> 'medina'."""
        low = re.sub(r"[^a-z0-9\s-]", " ", name.lower())
        parts = [p for p in re.split(r"[\s-]+", low)
                 if p and p not in STOPWORDS]
        return "".join(parts)

    def owner_score(r: dict, ident_low: str) -> tuple:
        """Higher = more likely the real owner of this URL."""
        name = r["district_name"]
        cc = canonical_concat(name)
        # 1. exact canonical name appears as a prefix of ident (strongest signal)
        prefix_bonus = 2 if cc and ident_low.startswith(cc) else 0
        # 2. canonical name appears anywhere in ident
        substr_bonus = 1 if cc and cc in ident_low else 0
        # 3. county first word in ident (>= 5 chars)
        cf = (r.get("county") or "").split()[0].lower()
        county_bonus = 1 if (len(cf) >= 5 and cf in ident_low) else 0
        return (prefix_bonus, substr_bonus, county_bonus, enrollment(r))

    sig_owner: dict[tuple[str, str], str | None] = {}
    for sig, shared in sig_rows.items():
        plat, ident = sig
        if plat in {"citizenportal", "panopto", "boardbook", "yt_channel_id", "yt_playlist", "yt_generic"}:
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
        url = r["video_url"].strip()
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
            "video_platform": r["video_platform"],
            "video_url": url,
            "signature": f"{sig[0]}:{sig[1]}",
            "dup_count": count,
            "decision": decision,
            "reason": reason,
        })

    with REPORT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    total = sum(summary.values())
    print(f"Scanned {total} populated rows")
    for k, v in summary.items():
        print(f"  {k:7s} {v}")
    print(f"Report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
