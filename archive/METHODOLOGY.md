# Methodology: Automated School Board Video URL Discovery

## Overview

This document describes the methodology used to systematically discover and catalog video archive URLs for Texas school districts using Claude Code as an autonomous research agent.

## The Problem

Texas has approximately 1,024 independent school districts (ISDs). Each district maintains its own website and may host school board meeting videos on various platforms. Manually finding video URLs for all districts would require 50-80 hours of tedious clicking.

No centralized database of school board video sources exists.

## The Solution

We used Claude Code (Claude's agentic coding interface) to autonomously:
1. Visit each district's website
2. Navigate to board meeting sections
3. Identify video hosting platforms
4. Record URLs and metadata
5. Checkpoint progress for reliability

## Why This Works

This task is well-suited for AI automation because it requires:
- **Pattern recognition**: Identifying common URL structures (swagit, granicus, youtube)
- **Judgment calls**: Determining if a page is actually the board meeting archive
- **Tedium tolerance**: 1,000+ repetitive lookups with minor variations
- **Error resilience**: Handling broken websites, missing pages gracefully

It does NOT require:
- Complex reasoning
- Code execution
- Precise numerical calculations

## Technical Implementation

### Input Data

We sourced the list of Texas ISDs from:
- Texas Education Agency (TEA) district directory
- Includes district ID, name, county, enrollment

### Agent Configuration

```
Tool: Claude Code (claude.ai with computer use)
Task Type: Background task / Long-running autonomous task
Estimated Duration: 20-40 hours of agent time
Human Oversight: ~2-4 hours (spot checks, handling stalls)
```

### Checkpointing Strategy

To prevent data loss from interruptions:
- Results saved every 25 districts
- Progress logged with timestamps
- Resume capability from last checkpoint

### Validation

Post-discovery validation:
1. HTTP HEAD requests to verify URLs are live
2. Spot-check 5% of results manually
3. Flag low-confidence entries for human review

## Results Summary

[To be filled after completion]

| Metric | Result |
|--------|--------|
| Total districts processed | |
| YouTube sources found | |
| Swagit sources found | |
| Granicus sources found | |
| Other platforms | |
| No video found | |
| Processing time | |
| Estimated manual equivalent | ~60 hours |

## Platform Distribution

[To be filled after completion]

```
YouTube:    ████████████████████ XX%
Swagit:     ████████ XX%
Granicus:   ████ XX%
None found: ████████ XX%
Other:      ██ XX%
```

## Limitations

1. **Point-in-time snapshot**: URLs may change; needs periodic re-verification
2. **Surface-level discovery**: Does not count meetings or verify archive completeness
3. **AI judgment**: Some edge cases may be misclassified
4. **Website accessibility**: Some district sites may block automated access

## Reproducibility

To reproduce this process:

1. Obtain current TEA district list
2. Use Claude Code with the `TASK_SPEC.md` prompt
3. Allow 20-40 hours for completion
4. Run validation scripts on output
5. Manual review of flagged entries

## Cost Analysis

| Approach | Time | Cost |
|----------|------|------|
| Manual research | 50-80 hours | ~$1,500-2,400 (at $30/hr RA rate) |
| Claude Code automation | 2-4 hours oversight | ~$20 (Claude Pro subscription) |
| **Savings** | **~95%** | **~$1,500+** |

## Ethical Considerations

- All data collected is from public websites
- No login credentials used
- Respectful crawling (no rapid-fire requests)
- Data used for academic research (HERC/Kinder Institute)

## Future Improvements

1. **Scheduled re-verification**: Monthly URL health checks
2. **Archive depth analysis**: Count meetings per district
3. **Transcript availability detection**: Check if YouTube captions exist
4. **Automatic ingestion triggers**: When new meeting detected

## Citation

If using this methodology or dataset:

```
Texas School Board Video Source Dataset (2025)
Compiled using AI-assisted web research for the 
Houston Education Research Consortium (HERC)
Rice University Kinder Institute for Urban Research
```

## Contact

[Your information here]

---

*Document version: 1.0*
*Last updated: January 2025*
