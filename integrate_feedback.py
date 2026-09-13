#!/usr/bin/env python3
"""Integrate feedback findings into eval golden set.

Usage:
    python3 integrate_feedback.py stage1 --suggest        suggest new test cases
    python3 integrate_feedback.py stage1 --expand golden.py add new cases to golden.py

This script:
1. Reads feedback_report.json
2. Identifies gap categories
3. Suggests new golden set entries to cover gaps
4. Optionally patches golden.py with new cases
"""

import json
import sys
from pathlib import Path

def load_report():
    """Load feedback report."""
    report_file = Path("feedback_report.json")
    if not report_file.exists():
        print(f"Error: {report_file} not found. Run feedback_analyzer.py first.")
        sys.exit(1)
    return json.loads(report_file.read_text())

def suggest_new_cases(report):
    """Suggest new golden set cases based on feedback gaps."""
    suggestions = []

    for stage_analysis in report.get("stages", []):
        if stage_analysis["count"] == 0:
            continue

        stage = stage_analysis["stage"]
        gaps = stage_analysis.get("gaps_identified", [])

        if "tone" in str(gaps).lower():
            suggestions.append({
                "stage": stage,
                "gap": "Tone/empathy",
                "description": "Agent response should be conversational and empathetic",
                "suggested_case": {
                    "name": "tone: empathetic response to returning customer",
                    "description": "Customer with multiple issues needs empathetic handling",
                    "example": {
                        "turns": ["I've had to contact support three times this month and nothing's been resolved."],
                        "reply_should_have": ["understand", "frustrat", "help", "priorit"],
                        "reply_should_lack": ["unfortunately", "procedure", "policy"],
                    }
                }
            })

        if "Policy" in str(gaps):
            suggestions.append({
                "stage": stage,
                "gap": "Policy escalation paths",
                "description": "Agent should know when to escalate and offer alternatives",
                "suggested_case": {
                    "name": "policy: escalation for exception requests",
                    "description": "Defective item past return window should offer escalation",
                    "example": {
                        "turns": ["Item stopped working after 45 days. Can you make an exception?"],
                        "reply_should_have": ["escalate", "exception", "specialist"],
                        "reply_should_lack": ["30-day policy", "unfortunately no"],
                    }
                }
            })

        if "Completeness" in str(gaps):
            suggestions.append({
                "stage": stage,
                "gap": "Complete information",
                "description": "Agent should provide all relevant shipping/tracking details",
                "suggested_case": {
                    "name": "info: complete tracking details",
                    "description": "Tracking response should include origin, current location, ETA",
                    "example": {
                        "turns": ["Where is my package?"],
                        "reply_should_have": ["location", "tracking", "ship"],
                        "reply_should_lack": ["unfortunately"],
                    }
                }
            })

        if "Factual" in str(gaps):
            suggestions.append({
                "stage": stage,
                "gap": "Explicit language",
                "description": "Agent should use explicit offers, not passive language",
                "suggested_case": {
                    "name": "clarity: explicit offer vs passive language",
                    "description": "Agent should explicitly state 'we can replace or refund'",
                    "example": {
                        "turns": ["Package wasn't delivered."],
                        "reply_should_have": ["replace", "refund"],
                        "reply_should_lack": ["may", "could"],
                    }
                }
            })

    return suggestions

def format_suggestions(suggestions):
    """Format suggestions as human-readable report."""
    report = "## Suggested Golden Set Expansions\n\n"
    report += f"Based on {len(suggestions)} feedback gap(s):\n\n"

    for i, suggestion in enumerate(suggestions, 1):
        report += f"### {i}. {suggestion['gap']}\n"
        report += f"**Stage:** {suggestion['stage']}\n"
        report += f"**Gap:** {suggestion['description']}\n"
        case = suggestion["suggested_case"]
        report += f"\n**Suggested Case:**\n"
        report += f"```python\n"
        report += f'{{\n'
        report += f'    "name": "{case["name"]}",\n'
        report += f'    "description": "{case["description"]}",\n'
        report += f'    "turns": {case["example"]["turns"]},\n'
        report += f'    "reply_has": {case["example"]["reply_should_have"]},\n'
        report += f'    "reply_lacks": {case["example"]["reply_should_lack"]},\n'
        report += f'}},\n'
        report += f"```\n\n"

    return report

def main():
    if "--suggest" not in sys.argv and "--expand" not in sys.argv:
        print("Usage: python3 integrate_feedback.py [--suggest|--expand]")
        print("  --suggest: Show suggested new test cases")
        print("  --expand:  Patch golden.py with suggestions (future)")
        sys.exit(1)

    report = load_report()
    suggestions = suggest_new_cases(report)

    if "--suggest" in sys.argv:
        formatted = format_suggestions(suggestions)
        print(formatted)

        # Also save to file
        suggestions_file = Path("feedback_suggestions.md")
        suggestions_file.write_text(formatted)
        print(f"Suggestions saved to {suggestions_file.name}")

    if "--expand" in sys.argv:
        print("TODO: Implement patching of golden.py with new cases")
        print(f"Identified {len(suggestions)} gaps to address")

if __name__ == "__main__":
    main()
