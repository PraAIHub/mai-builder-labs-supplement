
======================================================================
GOLDEN SET EXPANSION RECOMMENDATIONS — STAGE1
======================================================================

Analysis Summary:
  • Total corrections analyzed: 5
  • Unique patterns: 4
  • Novel cases (new golden rows needed): 5
  • Existing rows to boost: 0

New Golden Set Cases to Add (from feedback patterns):

  Case 1: Pattern 'wrong_tone' (2x in feedback)
    Issue: Agent tone was too formal, should be more conversational

  Case 2: Pattern 'policy_gap' (1x in feedback)
    Issue: Agent did not offer escalation path for defective items

  Case 3: Pattern 'incomplete_info' (1x in feedback)
    Issue: Agent response lacked shipping origin location

  Case 4: Pattern 'factual_error' (1x in feedback)
    Issue: Agent should explicitly say we can replace or refund, not just offer options passively


Python Code to Add to stage1/evals.py CASES list:

```python
    # Feedback-driven case: wrong_tone
    {
        "name": "feedback: tone — empathetic handling (feedback case 1)",
        "description": "Customer with frustration needs empathetic, conversational response",
        "turns": ["I've had multiple issues with my order and the previous responses haven't helped."],
        "reply_has": ["understand", "frustrat", "help"],
        "reply_lacks": ["unfortunately", "procedure"],
    },

    # Feedback-driven case: policy_gap
    {
        "name": "feedback: policy — escalation path (feedback case 2)",
        "description": "Defective/unusual cases should offer escalation or exception review",
        "turns": ["The item stopped working after 40 days. Can you make an exception?"],
        "reply_has": ["escalate", "exception", "specialist"],
        "reply_lacks": ["30-day", "unfortunately"],
    },

    # Feedback-driven case: incomplete_info
    {
        "name": "feedback: info — complete details (feedback case 3)",
        "description": "Tracking/status responses should include all relevant context",
        "turns": ["Where is my shipment?"],
        "reply_has": ["location", "tracking", "estimated", "origin"],
        "reply_lacks": ["unfortunately"],
    },

    # Feedback-driven case: factual_error
    {
        "name": "feedback: clarity — explicit language (feedback case 4)",
        "description": "Use explicit, direct offers rather than passive language",
        "turns": ["My package didn't arrive."],
        "reply_has": ["replace", "refund"],
        "reply_lacks": ["may", "could", "might"],
    },

```

Next Steps:
  1. Copy the cases above into stage1/evals.py CASES list
  2. Run: python3 stage1/evals.py --runs 1
  3. Verify: New cases pass with both planners
  4. Measure: Compare this eval run against baseline
