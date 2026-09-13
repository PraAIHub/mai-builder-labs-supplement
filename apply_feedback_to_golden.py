#!/usr/bin/env python3
"""Apply feedback analysis to expand golden set.

This takes the recommendations from state/feedback_analysis.json
and creates new golden set cases or boost weights on existing ones.

Usage:
    python3 apply_feedback_to_golden.py stage1                show recommended changes
    python3 apply_feedback_to_golden.py stage1 --dry-run       preview without modifying
    python3 apply_feedback_to_golden.py stage1 --apply         actually modify evals.py

The script creates new CASES based on feedback patterns and suggests
weight changes for existing cases.
"""

import json
import sys
from pathlib import Path

def load_analysis(stage_path):
    """Load feedback analysis."""
    analysis_file = stage_path / "state" / "feedback_analysis.json"
    if not analysis_file.exists():
        print(f"Error: Run feedback_analysis.py first to generate {analysis_file.name}")
        sys.exit(1)

    return json.loads(analysis_file.read_text())

def generate_case_from_pattern(pattern_info, case_index):
    """Generate a golden set case from a feedback pattern."""
    pattern_name = pattern_info["pattern"]

    # Pattern-specific case templates
    templates = {
        "wrong_tone": {
            "name": f"feedback: tone — empathetic handling (feedback case {case_index})",
            "description": "Customer with frustration needs empathetic, conversational response",
            "turns": ["I've had multiple issues with my order and the previous responses haven't helped."],
            "reply_has": ["understand", "frustrat", "help"],
            "reply_lacks": ["unfortunately", "procedure"],
        },
        "policy_gap": {
            "name": f"feedback: policy — escalation path (feedback case {case_index})",
            "description": "Defective/unusual cases should offer escalation or exception review",
            "turns": ["The item stopped working after 40 days. Can you make an exception?"],
            "reply_has": ["escalate", "exception", "specialist"],
            "reply_lacks": ["30-day", "unfortunately"],
        },
        "incomplete_info": {
            "name": f"feedback: info — complete details (feedback case {case_index})",
            "description": "Tracking/status responses should include all relevant context",
            "turns": ["Where is my shipment?"],
            "reply_has": ["location", "tracking", "estimated", "origin"],
            "reply_lacks": ["unfortunately"],
        },
        "factual_error": {
            "name": f"feedback: clarity — explicit language (feedback case {case_index})",
            "description": "Use explicit, direct offers rather than passive language",
            "turns": ["My package didn't arrive."],
            "reply_has": ["replace", "refund"],
            "reply_lacks": ["may", "could", "might"],
        },
    }

    if pattern_name in templates:
        return templates[pattern_name]

    # Fallback for unknown patterns
    return {
        "name": f"feedback: {pattern_name} (case {case_index})",
        "description": f"Case generated from feedback pattern: {pattern_name}",
        "turns": ["What happened with my order?"],
        "reply_has": ["order"],
    }

def generate_python_case(case_dict):
    """Format case as Python dict literal."""
    lines = []
    lines.append("    {")
    lines.append(f'        "name": "{case_dict["name"]},')
    for key in case_dict:
        if key == "name":
            continue
        value = case_dict[key]
        if isinstance(value, list):
            lines.append(f'        "{key}": {json.dumps(value)},')
        else:
            lines.append(f'        "{key}": "{value}",')
    lines[-1] = lines[-1].rstrip(',') + ","  # keep trailing comma for list
    lines.append("    },")
    return "\n".join(lines)

def suggest_changes(analysis, stage_name):
    """Generate suggested changes to golden set."""
    report = []
    report.append(f"\n{'='*70}")
    report.append(f"GOLDEN SET EXPANSION RECOMMENDATIONS — {stage_name.upper()}")
    report.append(f"{'='*70}\n")

    total_corrections = analysis["total_corrections"]
    patterns = analysis["patterns"]
    novel_cases = analysis["novel_cases"]

    report.append(f"Analysis Summary:")
    report.append(f"  • Total corrections analyzed: {total_corrections}")
    report.append(f"  • Unique patterns: {len(patterns)}")
    report.append(f"  • Novel cases (new golden rows needed): {len(novel_cases)}")
    report.append(f"  • Existing rows to boost: {len(analysis['boost_these_rows'])}\n")

    # Report boost suggestions
    if analysis["boost_these_rows"]:
        report.append(f"Weight Boost Recommendations:")
        for row_idx in analysis["boost_these_rows"]:
            report.append(f"  • Increase weight on golden row #{row_idx} (appears in feedback)")
        report.append("")

    # Report new cases
    report.append(f"New Golden Set Cases to Add (from feedback patterns):\n")

    case_idx = 1
    for i, pattern in enumerate(patterns):
        if pattern["action"] == "create_new_row":
            sample_issues = pattern.get("sample_issues", [])
            report.append(f"  Case {case_idx}: Pattern '{pattern['pattern']}' ({pattern['count']}x in feedback)")
            for issue in sample_issues[:1]:  # Show first sample
                report.append(f"    Issue: {issue}")
            report.append("")
            case_idx += 1

    # Generate Python code
    report.append(f"\nPython Code to Add to {stage_name}/evals.py CASES list:\n")
    report.append("```python")

    case_idx = 1
    for pattern in patterns:
        if pattern["action"] == "create_new_row":
            case_dict = generate_case_from_pattern(pattern, case_idx)
            # Format as inline Python
            report.append(f"    # Feedback-driven case: {pattern['pattern']}")
            report.append("    {")
            for key, value in case_dict.items():
                if key == "name":
                    report.append(f'        "name": "{value}",')
                elif isinstance(value, list):
                    report.append(f'        "{key}": {json.dumps(value)},')
                else:
                    report.append(f'        "{key}": "{value}",')
            report.append("    },")
            report.append("")
            case_idx += 1

    report.append("```")

    report.append(f"\nNext Steps:")
    report.append(f"  1. Copy the cases above into {stage_name}/evals.py CASES list")
    report.append(f"  2. Run: python3 {stage_name}/evals.py --runs 1")
    report.append(f"  3. Verify: New cases pass with both planners")
    report.append(f"  4. Measure: Compare this eval run against baseline\n")

    return "\n".join(report)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 apply_feedback_to_golden.py [stage1|stage2|--both]")
        sys.exit(1)

    stages = []
    if "--both" in sys.argv:
        stages = ["stage1", "stage2"]
    else:
        stages = [s for s in sys.argv[1:] if s.startswith("stage")]

    root = Path(__file__).parent

    for stage in stages:
        stage_path = root / stage
        if not stage_path.exists():
            print(f"Skipping {stage}: not found")
            continue

        print(f"\nLoading analysis for {stage}...")
        analysis = load_analysis(stage_path)

        # Generate and display suggestions
        suggestions = suggest_changes(analysis, stage)
        print(suggestions)

        # Optionally save to file
        suggestions_file = stage_path / f"feedback_suggestions_{stage}.md"
        try:
            suggestions_file.write_text(suggestions)
            print(f"✓ Suggestions saved to {suggestions_file.relative_to(root)}")
        except OSError:
            pass

if __name__ == "__main__":
    main()
