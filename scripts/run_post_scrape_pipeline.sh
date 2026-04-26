#!/bin/sh
# Run after website_crawler.py and platform_directory_scraper.py finish.
# Merges their outputs into districts_complete.csv then re-validates.
set -e
cd "$(dirname "$0")/.."
PY="$PWD/venv/bin/python"

# 1) Merge discovery outputs into complete CSV (only fills pending rows).
cd scripts && $PY merge_discovery_results.py && cd ..

# 2) Validate + apply for video URLs, then websites.
$PY scripts/validate_stream_matches.py
$PY scripts/apply_stream_validation.py
$PY scripts/validate_website_matches.py
$PY scripts/apply_website_validation.py

# 3) Reassign any URLs that landed on the wrong district.
$PY scripts/reassign_stream_urls.py || true
$PY scripts/reassign_website_urls.py || true

# 4) Final stats
$PY - <<'EOF'
import csv
rows = list(csv.DictReader(open('data/districts_complete.csv')))
v = sum(1 for r in rows if r['video_url'].strip())
w = sum(1 for r in rows if r['website_url'].strip())
print(f'Total districts: {len(rows)}')
print(f'website_url populated: {w}')
print(f'video_url populated: {v}')
EOF
