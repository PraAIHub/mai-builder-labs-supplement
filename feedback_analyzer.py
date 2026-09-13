#!/usr/bin/env python3
"""Analyze human feedback from state/feedback.jsonl and integrate into evals.

Usage:
    python3 feedback_analyzer.py stage1              analyze feedback for stage1
    python3 feedback_analyzer.py stage2              analyze feedback for stage2
    python3 feedback_analyzer.py --both              analyze both stages
    python3 feedback_analyzer.py --report feedback   save report to feedback_report.json

Feedback schema (logged via /feedback endpoint):
    {
        "timestamp": "2026-09-13T12:00:00.000000",
        "golden_row_id": "123",
        "original_response": "Agent said this",
        "corrected_response": "Should have said this",
        "reason": "didn't understand the policy"
    }

This script:
1. Reads all feedback entries
2. Groups by pattern and category
3. Identifies gaps in golden set coverage
4. Suggests new test cases to add
5. Measures correlation with eval failures
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def load_feedback(stage_path):
    """Load all feedback entries from state/feedback.jsonl."""
    feedback_file = stage_path / "state" / "feedback.jsonl"
    entries = []
    if not feedback_file.exists():
        return entries

    try:
        with open(feedback_file, "r") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    except (OSError, json.JSONDecodeError) as e:
        print(f"Warning: Could not read {feedback_file}: {e}")

    return entries


def analyze_feedback(entries, stage_name):
    """Analyze feedback patterns."""
    if not entries:
        return {"stage": stage_name, "count": 0, "insights": "No feedback yet"}

    analysis = {
        "stage": stage_name,
        "count": len(entries),
        "date_range": {
            "first": entries[0].get("timestamp"),
            "last": entries[-1].get("timestamp"),
        },
        "by_category": defaultdict(list),
        "by_golden_id": defaultdict(list),
        "gaps_identified": [],
    }

    for entry in entries:
        category = entry.get("category", "unknown").lower()
        analysis["by_category"][category].append(entry)

        golden_id = entry.get("golden_id") or entry.get("golden_row_id")
        if golden_id:
            analysis["by_golden_id"][golden_id].append(entry)

    # Identify top categories for corrections
    top_categories = sorted(
        analysis["by_category"].items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    analysis["category_distribution"] = [
        {"category": cat, "count": len(entries), "percentage": round(len(entries)/len(entries)*100, 1)}
        for cat, entries in top_categories
    ]

    # Identify rows with most feedback
    top_rows = sorted(
        analysis["by_golden_id"].items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:5]

    analysis["most_corrected_rows"] = [
        {"golden_id": golden_id, "correction_count": len(entries), "issues": [e.get("issue") for e in entries]}
        for golden_id, entries in top_rows
    ]

    # Identify gaps based on categories
    category_names = [cat for cat, _ in top_categories]

    if "tone" in category_names:
        count = len(analysis["by_category"]["tone"])
        if count >= len(entries) * 0.3:
            analysis["gaps_identified"].append(
                f"Tone/style gaps: {count} corrections ({round(count/len(entries)*100)}%) — Agent tone is too formal or lacks empathy"
            )

    if "policy_violation" in category_names or "policy" in str(category_names).lower():
        count = len(analysis["by_category"].get("policy_violation", []))
        if count > 0:
            analysis["gaps_identified"].append(
                f"Policy understanding gaps: {count} corrections — Agent misapplies or omits policy details"
            )

    if "incomplete_info" in category_names:
        count = len(analysis["by_category"]["incomplete_info"])
        if count >= len(entries) * 0.2:
            analysis["gaps_identified"].append(
                f"Completeness gaps: {count} corrections ({round(count/len(entries)*100)}%) — Agent omits relevant details"
            )

    if "factual_error" in category_names:
        count = len(analysis["by_category"]["factual_error"])
        if count > 0:
            analysis["gaps_identified"].append(
                f"Factual errors: {count} corrections — Agent states incorrect information"
            )

    return analysis


def generate_report(analyses):
    """Generate summary report."""
    report = {
        "generated": datetime.utcnow().isoformat(),
        "summary": f"Analyzed feedback from {sum(a['count'] for a in analyses)} entries across {len(analyses)} stage(s)",
        "stages": analyses,
        "recommendations": [],
    }

    # Global recommendations
    total_feedback = sum(a["count"] for a in analyses)
    if total_feedback == 0:
        report["recommendations"].append("No feedback collected yet. Run the agent and use /feedback endpoint to capture corrections.")
    elif total_feedback < 10:
        report["recommendations"].append(f"Minimal feedback ({total_feedback} entries). Collect more before drawing conclusions.")
    else:
        report["recommendations"].append("Sufficient feedback to begin analysis. Review gaps and expand golden set accordingly.")

    return report


def main():
    root = Path(__file__).parent

    stages = []
    if "--both" in sys.argv or len(sys.argv) == 1:
        stages = ["stage1", "stage2"]
    else:
        stages = [s for s in sys.argv[1:] if s.startswith("stage")]

    if not stages:
        print("Usage: python3 feedback_analyzer.py stage1 [stage2] [--report]")
        sys.exit(1)

    analyses = []
    for stage in stages:
        stage_path = root / stage
        if not stage_path.exists():
            print(f"Skipping {stage}: not found")
            continue

        print(f"Analyzing {stage}...")
        entries = load_feedback(stage_path)
        analysis = analyze_feedback(entries, stage)
        analyses.append(analysis)

        print(f"  {len(entries)} feedback entries")
        if analysis.get("top_reasons"):
            print(f"  Top reason: {analysis['top_reasons'][0]}")
        if analysis.get("gaps_identified"):
            for gap in analysis["gaps_identified"]:
                print(f"  Gap: {gap}")

    report = generate_report(analyses)

    # Save report if requested
    if "--report" in sys.argv:
        report_file = root / "feedback_report.json"
        report_file.write_text(json.dumps(report, indent=2, default=str))
        print(f"\nReport saved to {report_file.name}")
    else:
        print("\nFull report (JSON):")
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
