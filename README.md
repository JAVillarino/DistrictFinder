# DistrictFinder — Texas School Board Streams

**Live at [districtfinder.org](https://districtfinder.org)**

A comprehensive dataset and toolkit for locating board meeting video archives across Texas's ~1,060 independent school districts.

## Why This Exists

School board meetings are public record, but finding the video archives is surprisingly difficult:

- **Fragmented sources**: Districts use dozens of different platforms (YouTube, Swagit, Granicus, Vimeo, BoardDocs, custom solutions)
- **No central index**: No existing database catalogs where Texas school boards post their meeting videos
- **Manual discovery barrier**: Previously required visiting 1,000+ individual district websites

This project automates that discovery process and publishes the results for
public-interest, research, journalistic, and civic use.

## Use Cases

- **Researchers**: Content analysis of board meeting discussions, policy tracking, voting pattern studies
- **Journalists**: Investigating school board activities and decisions across districts
- **Civic technologists**: Building transparency tools for local governance
- **Citizens**: Finding your district's board meeting archives
- **Developers**: Adapting the methodology for other states or local government bodies

## Status

Current dataset coverage:

- Video links: 779/1,060 districts
- Website links: 944/1,060 districts
- Map coordinates: 1,054/1,060 districts

Run `python scripts/audit_dataset.py` for the authoritative local audit.

## Data

The dataset is available in `data/` and updated as districts are verified:

| File | Description |
|------|-------------|
| `data/districts_complete.csv` | Master list of all 1,060 Texas ISDs with TEA district IDs |
| `data/districts_verified.csv` | Districts with confirmed video archive URLs |
| `data/youtube_channels.csv` | Discovered YouTube channels/playlists |
| `data/tea_districts_master_clean.csv` | Clean TEA reference data |

The compiled dataset is public for noncommercial use with attribution. See
[`DATA_LICENSE.md`](DATA_LICENSE.md).

## Automation Scripts

```bash
cd scripts

# Test Swagit URLs (~35% hit rate)
python swagit_matcher.py --batch 131-150

# Test Granicus patterns (~6% hit rate)
python granicus_matcher.py --batch 131-150

# Find YouTube channels via API (requires API key)
python youtube_bulk_finder.py --batch 131-150

# Validate all URLs
python validation_pipeline.py

# Check progress
python progress_tracker.py --status
```

Scripts handle ~70% of districts automatically. The remaining ~30% require manual verification due to non-standard website structures.

## Getting Started

1. Clone the repo
2. Install dependencies: `pip install -r requirements.txt`
3. For YouTube API searches, copy `scripts/config.example.json` to `scripts/config.json` and add your API key
4. Run `python scripts/progress_tracker.py --status` to see current state

## Vercel Deployment

The frontend is static (`index.html` + CSV files) and the issue-report button uses the serverless function in `api/flag.js`.

Set these Vercel environment variables before deploying:

```bash
RESEND_API_KEY=...
FLAG_TO_EMAIL=...
FLAG_FROM_EMAIL=...
```

`FLAG_TO_EMAIL` is only read inside the serverless function, so the recipient address is not included in the browser bundle. `FLAG_FROM_EMAIL` must be a sender address accepted by the Resend account.

Dataset downloads are served through `api/data.js` at `/data/...` with a
lightweight per-IP rate limit. This is a practical abuse deterrent, not DRM;
the data remains publicly accessible for allowed noncommercial use.

## Project Structure

```
├── data/                     # Dataset files
│   ├── districts_complete.csv    # Master list (all 1,060 districts)
│   ├── districts_verified.csv    # Verified video URLs
│   └── youtube_channels.csv      # YouTube discoveries
├── scripts/                  # Automation tools
├── docs/                     # Detailed documentation
└── archive/                  # Development history
```

## Contributing

Contributions welcome! See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines.

Ways to help:
- Verify video URLs for unprocessed districts
- Report broken links via issues
- Adapt scripts for other states
- Improve automation hit rates

## License

Code is licensed under the MIT License. Dataset files in `data/` are licensed
under Creative Commons Attribution-NonCommercial 4.0 International. Commercial
use of the compiled dataset requires prior written permission. See
[`LICENSE`](LICENSE) and [`DATA_LICENSE.md`](DATA_LICENSE.md).

## Contact

Joel Villarino
Rice University
