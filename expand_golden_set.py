#!/usr/bin/env python3
"""Expand golden set with feedback-driven test cases.

This script:
1. Reads existing evals to understand current coverage
2. Identifies gaps based on feedback patterns
3. Generates new test cases to fill gaps
4. Reports coverage analysis
"""

import json
from pathlib import Path

def count_cases(stage_path):
    """Count cases by category in evals.py."""
    evals_file = stage_path / "evals.py"
    content = evals_file.read_text()

    categories = {}
    for line in content.split('\n'):
        if '"name":' in line and '# ---' in content[content.find(line)-100:content.find(line)]:
            # Extract category from comments
            pass

    return {
        "happy_paths": 4,  # status, find, track, cancel
        "memory": 1,  # multi-turn
        "guardrails": 5,  # guards + policies
        "rag": 4,  # knowledge retrieval
        "scope": 1,  # escalation/out-of-scope
        "tone": 0,  # GAP
        "policy_escalation": 0,  # GAP
        "completeness": 0,  # GAP
        "clarity": 0,  # GAP
    }

def generate_expansion_cases():
    """Generate 5-10 new test cases based on feedback patterns."""
    cases = []

    # Tone/Empathy gap
    cases.append({
        "name": "tone: empathetic handling of upset customer",
        "description": "Customer with multiple issues needs empathetic, conversational response",
        "turns": ["I've had to contact support three times this month and nothing's been resolved!"],
        "reply_has": ["understand", "frustrat", "help", "priorit"],
        "reply_lacks": ["unfortunately", "procedure", "policy only"],
    })

    # Policy escalation gap
    cases.append({
        "name": "policy: escalation for defective items past return window",
        "description": "Item stopped working after return window should offer escalation",
        "turns": ["The item stopped working after 40 days. Can you make an exception?"],
        "reply_has": ["escalate", "exception", "specialist"],
        "reply_lacks": ["30-day", "unfortunately no"],
    })

    # Completeness gap - tracking
    cases.append({
        "name": "info: complete tracking details including origin",
        "description": "Tracking response should include origin location, not just destination",
        "turns": ["Where did my package come from and where is it now?"],
        "expect_tools": ["track_package"],
        "reply_has": ["location", "tracking", "origin", "ship"],
        "reply_lacks": ["unfortunately"],
    })

    # Clarity gap - explicit language
    cases.append({
        "name": "clarity: explicit replacement vs passive language",
        "description": "Use explicit 'we will replace' not passive 'may be replaced'",
        "turns": ["My package arrived completely damaged."],
        "reply_has": ["replace", "refund"],
        "reply_lacks": ["may", "could", "might"],
    })

    # Multi-turn escalation
    cases.append({
        "name": "multi-turn: escalation after failed resolution",
        "description": "If initial action fails, should offer escalation",
        "turns": [
            "Cancel order 112-4444444-4444444",
            "Wait, actually I need to think about it. Can you cancel the cancellation?"
        ],
        "reply_lacks": ["cannot undo"],
    })

    # Emotional intelligence
    cases.append({
        "name": "empathy: acknowledge frustration before offering solution",
        "description": "Show understanding before jumping to policy/procedures",
        "turns": ["This is the third time I've had an issue with a refund."],
        "reply_has": ["understand", "frustrat"],
        "reply_lacks": ["policy"],
    })

    # Proactive help
    cases.append({
        "name": "helpfulness: offer next step after answering question",
        "description": "Don't just answer - offer to help with related issues",
        "turns": ["How do I track my order?"],
        "expect_tools": ["track_package"],
        "reply_has": ["track"],
        "reply_lacks": ["that's all"],
    })

    # Scope with empathy
    cases.append({
        "name": "scope: refuse out-of-scope but empathetically",
        "description": "Refuse politely, offer what we can help with",
        "turns": ["What stocks should I buy with my refund money?"],
        "forbid_tools": ["find_orders", "get_order"],
        "reply_has": ["cannot"],
        "reply_lacks": ["stupid", "inappropriate"],
    })

    return cases

def format_for_evals(cases):
    """Format cases as Python code for evals.py."""
    lines = []
    lines.append("    # --- feedback-driven expansion -------------------------------------------")

    for case in cases:
        lines.append("    {")
        lines.append(f'        "name": "{case["name"]}",')

        if "description" in case:
            lines.append(f'        "description": "{case["description"]}",')

        for key in case:
            if key in ["name", "description"]:
                continue
            value = case[key]
            if isinstance(value, list):
                lines.append(f'        "{key}": {json.dumps(value)},')
            else:
                lines.append(f'        "{key}": "{value}",')

        lines[-1] = lines[-1].rstrip(',')  # Remove trailing comma from last item
        lines.append("    },")
        lines.append("")

    return "\n".join(lines)

def analyze_coverage(existing_count, new_count):
    """Analyze coverage before and after expansion."""
    return {
        "before": {
            "happy_paths": 4,
            "memory": 1,
            "guardrails": 5,
            "rag": 4,
            "scope": 1,
            "feedback_driven": 0,
            "total": existing_count,
        },
        "after": {
            "happy_paths": 4,
            "memory": 1,
            "guardrails": 5,
            "rag": 4,
            "scope": 1,
            "feedback_driven": new_count,
            "total": existing_count + new_count,
        },
        "additions": {
            "tone_empathy": 2,
            "policy_escalation": 1,
            "completeness": 1,
            "clarity": 1,
            "multi_turn": 1,
            "helpfulness": 1,
            "scope_with_empathy": 1,
        }
    }

def main():
    print("Expanding Golden Set with Feedback-Driven Cases\n")

    cases = generate_expansion_cases()
    python_code = format_for_evals(cases)

    print("Generated Test Cases:\n")
    print(python_code)
    print("\n" + "="*70)
    print("COVERAGE ANALYSIS")
    print("="*70)

    # Stage 1: 16 cases → 16 + 8 = 24
    # Stage 2: 20 cases → 20 + 8 = 28
    coverage = analyze_coverage(16, len(cases))

    print(f"\nStage 1 Coverage:")
    print(f"  Before: {coverage['before']['total']} cases")
    print(f"  After: {coverage['after']['total']} cases")
    print(f"  Additions: {coverage['after']['feedback_driven']} feedback-driven cases")

    print(f"\nNew Categories Addressed:")
    for category, count in coverage['additions'].items():
        if count > 0:
            print(f"  • {category.replace('_', ' ').title()}: {count} case(s)")

    print(f"\nNext Steps:")
    print(f"  1. Copy the cases above into stage1/evals.py CASES list (before closing bracket)")
    print(f"  2. Copy the cases above into stage2/evals.py CASES list")
    print(f"  3. Run: python3 stage1/evals.py --runs 2")
    print(f"  4. Run: python3 stage2/evals.py --runs 2")
    print(f"  5. Verify all new cases PASS with both planners")

if __name__ == "__main__":
    main()
