#!/usr/bin/env python3
"""
Progress Tracker - Texas School Board Video Sources

Central state management for all scripts.
Tracks progress, calculates estimates, manages resumability.

Usage:
    python progress_tracker.py --status
    python progress_tracker.py --resume swagit
    python progress_tracker.py --reset youtube
"""

import json
import argparse
import csv
from datetime import datetime
from pathlib import Path

# Configuration
STATE_FILE = "project_state.json"
TOTAL_DISTRICTS = 1024
COMPLETE_FILE = Path(__file__).resolve().parent.parent / "data" / "districts_complete.csv"

# Script progress files
PROGRESS_FILES = {
    "swagit": "swagit_progress.json",
    "youtube": "youtube_progress.json",
    "granicus": "granicus_progress.json",
    "regional": "regional_progress.json"
}


def load_state():
    """Load project state"""
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)

    return {
        "total_districts": TOTAL_DISTRICTS,
        "processed": {
            "swagit_matcher": 0,
            "youtube_finder": 0,
            "granicus_matcher": 0,
            "regional_processor": 0,
            "agent_manual": 124,  # Starting point
            "total": 124
        },
        "remaining": TOTAL_DISTRICTS - 124,
        "estimated_hours": 0,
        "last_updated": datetime.now().isoformat()
    }


def load_complete_csv_counts():
    """Return progress counts from the authoritative districts_complete.csv."""
    if not COMPLETE_FILE.exists():
        return None

    with COMPLETE_FILE.open(newline="") as f:
        rows = list(csv.DictReader(f))

    pending = sum(1 for row in rows if row.get("video_status") == "pending")
    return {
        "total": len(rows),
        "pending": pending,
        "processed": len(rows) - pending,
        "verified": sum(1 for row in rows if row.get("video_status") == "verified"),
        "auto_discovered": sum(1 for row in rows if row.get("video_status") == "auto_discovered"),
    }


def save_state(state):
    """Save project state"""
    state["last_updated"] = datetime.now().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def update_from_progress_files(state):
    """Update state from individual script progress files"""
    for script_name, progress_file in PROGRESS_FILES.items():
        if Path(progress_file).exists():
            with open(progress_file, "r") as f:
                progress = json.load(f)
                processed_count = len(progress.get("processed_ids", []))
                state["processed"][script_name] = processed_count

    csv_counts = load_complete_csv_counts()
    if csv_counts:
        state["total_districts"] = csv_counts["total"]
        state["processed"]["verified"] = csv_counts["verified"]
        state["processed"]["auto_discovered"] = csv_counts["auto_discovered"]
        state["processed"]["total"] = csv_counts["processed"]
        state["remaining"] = csv_counts["pending"]
    else:
        script_total = sum(
            count for key, count in state["processed"].items()
            if key not in {"total", "verified", "auto_discovered"}
        )
        state["processed"]["total"] = script_total
        state["remaining"] = state["total_districts"] - state["processed"]["total"]

    # Estimate remaining time
    # Assume: Scripts handle 70% at 0.5 min/district, Agent handles 30% at 3 min/district
    script_remaining = state["remaining"] * 0.7
    agent_remaining = state["remaining"] * 0.3

    estimated_minutes = (script_remaining * 0.5) + (agent_remaining * 3)
    state["estimated_hours"] = round(estimated_minutes / 60, 1)

    return state


def display_status(state):
    """Display project status dashboard"""
    print("\n" + "="*60)
    print("Texas School Districts Video Discovery - Progress Dashboard")
    print("="*60)
    print(f"\n📊 Overall Progress: {state['processed']['total']}/{state['total_districts']} ({state['processed']['total']/state['total_districts']*100:.1f}%)")
    print(f"⏳ Estimated remaining: {state['estimated_hours']} hours")
    print(f"🕐 Last updated: {state['last_updated']}")

    print(f"\n📈 Breakdown by Method:")
    print(f"  Swagit Matcher:      {state['processed']['swagit_matcher']:>4} districts")
    print(f"  YouTube Finder:      {state['processed']['youtube_finder']:>4} districts")
    print(f"  Granicus Matcher:    {state['processed']['granicus_matcher']:>4} districts")
    print(f"  Regional Processor:  {state['processed']['regional_processor']:>4} districts")
    print(f"  Agent Manual:        {state['processed']['agent_manual']:>4} districts")
    if "verified" in state["processed"]:
        print(f"  Verified in CSV:     {state['processed']['verified']:>4} districts")
    if "auto_discovered" in state["processed"]:
        print(f"  Auto-discovered CSV: {state['processed']['auto_discovered']:>4} districts")
    print(f"  {'-'*40}")
    print(f"  TOTAL:               {state['processed']['total']:>4} districts")

    print(f"\n📋 Next Steps:")
    if state['remaining'] > 0:
        print(f"  - Process next batch of {min(50, state['remaining'])} districts")
        print(f"  - Run: python swagit_matcher.py --batch {state['processed']['total']+1}-{state['processed']['total']+50}")
    else:
        print(f"  ✓ All districts processed!")
        print(f"  - Run validation pipeline to verify quality")

    print("\n" + "="*60 + "\n")


def reset_script(script_name):
    """Reset progress for a specific script"""
    progress_file = PROGRESS_FILES.get(script_name)
    if not progress_file:
        print(f"Error: Unknown script '{script_name}'")
        print(f"Available scripts: {', '.join(PROGRESS_FILES.keys())}")
        return

    if Path(progress_file).exists():
        Path(progress_file).unlink()
        print(f"✓ Reset {script_name} progress")
    else:
        print(f"No progress file found for {script_name}")


def resume_script(script_name):
    """Display resume command for a script"""
    progress_file = PROGRESS_FILES.get(script_name)
    if not progress_file:
        print(f"Error: Unknown script '{script_name}'")
        return

    if Path(progress_file).exists():
        with open(progress_file, "r") as f:
            progress = json.load(f)
            processed_count = len(progress.get("processed_ids", []))
            print(f"\n{script_name} has processed {processed_count} districts")
            print(f"To resume, run:")
            print(f"  python {script_name}_matcher.py --resume")
    else:
        print(f"No progress file found for {script_name}")
        print(f"Start fresh with:")
        print(f"  python {script_name}_matcher.py --batch 125-175")


def main():
    parser = argparse.ArgumentParser(description="Progress Tracker for Texas School Districts")
    parser.add_argument("--status", action="store_true", help="Show status dashboard")
    parser.add_argument("--resume", help="Show resume command for script", type=str)
    parser.add_argument("--reset", help="Reset progress for script", type=str)
    parser.add_argument("--update", action="store_true", help="Update state from progress files")

    args = parser.parse_args()

    # Load state
    state = load_state()

    if args.update or args.status:
        state = update_from_progress_files(state)
        save_state(state)

    if args.status or not any(vars(args).values()):
        display_status(state)

    if args.resume:
        resume_script(args.resume)

    if args.reset:
        reset_script(args.reset)


if __name__ == "__main__":
    main()
