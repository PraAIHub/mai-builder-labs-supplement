#!/usr/bin/env python3
"""Analyze feedback and map to golden set rows for reweighting.

This is the core integration pipeline:
1. Read feedback.jsonl
2. Identify patterns (tone, policy, info, factual)
3. Map feedback to related golden rows (semantic similarity)
4. Generate state/feedback_analysis.json with boost/create recommendations
5. Output actionable report for next eval run

Usage:
    python3 feedback_analysis.py stage1              analyze stage1 feedback
    python3 feedback_analysis.py --both              analyze both stages
    python3 feedback_analysis.py --report            save to state/feedback_analysis.json
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

def load_feedback(stage_path):
    """Load feedback entries from state/feedback.jsonl."""
    feedback_file = stage_path / "state" / "feedback.jsonl"
    entries = []
    if not feedback_file.exists():
        return entries

    try:
        with open(feedback_file, "r") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        pass

    return entries


def load_golden(stage_path):
    """Load golden set cases from evals.py."""
    evals_file = stage_path / "evals.py"
    if not evals_file.exists():
        return []

    # Simple extraction: read CASES = [ ... ] from evals.py
    # This is a rough heuristic since we can't reliably parse Python AST here
    content = evals_file.read_text()

    # Find the CASES list and extract indices
    cases = []
    if "CASES = [" in content:
        # Mark all cases we found in the file
        # For proper implementation, would parse Python AST
        case_markers = content.count('{"name"')
        for i in range(case_markers):
            cases.append({"index": i, "marker": f"case_{i}"})

    return cases


def identify_pattern(feedback_entry):
    """Classify feedback entry into a pattern category."""
    category = feedback_entry.get("category", "unknown").lower()
    issue = feedback_entry.get("issue", "").lower()

    # Map categories to patterns
    pattern_map = {
        "tone": "wrong_tone",
        "policy_violation": "policy_gap",
        "incomplete_info": "incomplete_info",
        "factual_error": "factual_error",
    }

    if category in pattern_map:
        return pattern_map[category]

    # Fallback: infer from issue text
    if "tone" in issue or "formal" in issue or "empathy" in issue:
        return "wrong_tone"
    elif "policy" in issue or "escalat" in issue:
        return "policy_gap"
    elif "missing" in issue or "omit" in issue or "lack" in issue:
        return "incomplete_info"
    elif "incorrect" in issue or "wrong" in issue or "passive" in issue:
        return "factual_error"

    return "other"


def map_to_golden_rows(feedback_entry, golden_cases, stage_name):
    """Map feedback to related golden set rows using semantic hints."""
    golden_id = feedback_entry.get("golden_id") or feedback_entry.get("golden_row_id")
    issue = feedback_entry.get("issue", "").lower()
    correction = feedback_entry.get("correction", "").lower()

    related_rows = []

    # Direct mapping: if feedback specifies golden_id, that's a direct hit
    if golden_id:
        # Find the row index by name/id
        for i, case in enumerate(golden_cases):
            if case.get("name", "") == golden_id or str(i) == str(golden_id):
                related_rows.append(i)
                break

    # Semantic similarity heuristics
    keywords = [
        ("tone", ["empath", "formal", "conversational", "tone"]),
        ("escalation", ["escalat", "exception", "specialist", "human"]),
        ("tracking", ["track", "package", "location", "origin", "ship"]),
        ("policy", ["policy", "30-day", "return", "window", "refund"]),
    ]

    for keyword, terms in keywords:
        if any(term in issue or term in correction for term in terms):
            # Find related golden rows by keyword
            for i, case in enumerate(golden_cases):
                case_name = case.get("name", "").lower()
                if keyword in case_name and i not in related_rows:
                    related_rows.append(i)

    return related_rows


def analyze_feedback_batch(feedback_entries, stage_name, golden_cases):
    """Analyze all feedback and produce recommendations."""
    analysis = {
        "stage": stage_name,
        "total_corrections": len(feedback_entries),
        "patterns": defaultdict(lambda: {
            "count": 0,
            "related_golden_rows": set(),
            "entries": []
        }),
    }

    novel_cases = []  # Feedback with no related golden rows

    for entry in feedback_entries:
        pattern = identify_pattern(entry)
        related_rows = map_to_golden_rows(entry, golden_cases, stage_name)

        analysis["patterns"][pattern]["count"] += 1
        analysis["patterns"][pattern]["related_golden_rows"].update(related_rows)
        analysis["patterns"][pattern]["entries"].append({
            "golden_id": entry.get("golden_id"),
            "issue": entry.get("issue"),
            "timestamp": entry.get("timestamp"),
        })

        # Track novel cases (no related golden rows, or golden_id not found)
        if not related_rows:
            novel_cases.append({
                "pattern": pattern,
                "entry": entry,
                "action": "create_new_row"
            })

    # Convert sets to lists for JSON serialization
    patterns_list = []
    for pattern_name, pattern_data in sorted(
        analysis["patterns"].items(),
        key=lambda x: x[1]["count"],
        reverse=True
    ):
        patterns_list.append({
            "pattern": pattern_name,
            "count": pattern_data["count"],
            "related_golden_rows": sorted(list(pattern_data["related_golden_rows"])),
            "action": "boost_weight" if pattern_data["related_golden_rows"] else "create_new_row",
            "sample_issues": [e["issue"] for e in pattern_data["entries"][:2]],
        })

    # Build recommendation
    boost_rows = set()
    new_rows_needed = 0

    for pattern in patterns_list:
        if pattern["action"] == "boost_weight" and pattern["related_golden_rows"]:
            boost_rows.update(pattern["related_golden_rows"])
        elif pattern["action"] == "create_new_row":
            new_rows_needed += len([p for p in patterns_list if p["pattern"] == pattern["pattern"]])

    recommendation = f"Add {len(novel_cases)} new row(s) to golden set, boost weight on {len(boost_rows)} existing row(s)"
    if not patterns_list:
        recommendation = "No feedback to analyze yet."

    return {
        "stage": stage_name,
        "total_corrections": len(feedback_entries),
        "patterns": patterns_list,
        "novel_cases": novel_cases,
        "recommendation": recommendation,
        "boost_these_rows": sorted(list(boost_rows)),
    }


def save_analysis(analysis_data, stage_path):
    """Save analysis to state/feedback_analysis.json."""
    analysis_file = stage_path / "state" / "feedback_analysis.json"

    try:
        analysis_file.parent.mkdir(exist_ok=True)
        analysis_file.write_text(json.dumps(analysis_data, indent=2, default=str))
        return analysis_file
    except OSError as e:
        print(f"Error saving analysis: {e}")
        return None


def main():
    root = Path(__file__).parent

    stages = []
    if "--both" in sys.argv or len(sys.argv) == 1:
        stages = ["stage1", "stage2"]
    else:
        stages = [s for s in sys.argv[1:] if s.startswith("stage")]

    if not stages:
        print("Usage: python3 feedback_analysis.py [stage1|stage2|--both] [--report]")
        sys.exit(1)

    all_analyses = []

    for stage in stages:
        stage_path = root / stage
        if not stage_path.exists():
            print(f"Skipping {stage}: not found")
            continue

        print(f"\nAnalyzing {stage}...")

        feedback = load_feedback(stage_path)
        golden = load_golden(stage_path)

        if not feedback:
            print(f"  No feedback yet in {stage}")
            analysis = {
                "stage": stage,
                "total_corrections": 0,
                "patterns": [],
                "novel_cases": [],
                "recommendation": "No feedback collected yet.",
                "boost_these_rows": []
            }
        else:
            analysis = analyze_feedback_batch(feedback, stage, golden)
            print(f"  ✓ Analyzed {len(feedback)} corrections")
            print(f"  ✓ Identified {len(analysis['patterns'])} patterns")
            print(f"  ✓ Novel cases: {len(analysis['novel_cases'])}")
            print(f"  → {analysis['recommendation']}")

        all_analyses.append(analysis)

        # Save to file if --report
        if "--report" in sys.argv:
            saved_path = save_analysis(analysis, stage_path)
            if saved_path:
                print(f"  📝 Saved to {saved_path.relative_to(root)}")

    # Print summary
    print("\n" + "="*60)
    print("FEEDBACK ANALYSIS SUMMARY")
    print("="*60)

    for analysis in all_analyses:
        print(f"\n{analysis['stage'].upper()}:")
        print(f"  Corrections: {analysis['total_corrections']}")
        print(f"  Patterns: {len(analysis['patterns'])}")
        print(f"  Boost weight on rows: {analysis['boost_these_rows']}")
        print(f"  New rows to create: {len(analysis['novel_cases'])}")
        print(f"  Recommendation: {analysis['recommendation']}")


if __name__ == "__main__":
    main()
