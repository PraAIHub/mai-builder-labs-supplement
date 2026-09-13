# Quick Start: Feedback-Driven Development

Everything is ready. Here's how to start collecting and analyzing feedback in 5 minutes.

## Step 1: Start the Web Server (Terminal 1)

```bash
cd stage1
python3 web.py
```

Output:
```
Ami is running at http://localhost:8000
```

## Step 2: Open Browser and Chat (Terminal 2 - your browser)

1. Open http://localhost:8000
2. Chat with the agent
3. Intentionally ask for something to get a wrong response
4. Example: "What's a good stock to buy?" (should refuse)

## Step 3: Submit Feedback (Browser)

When you see a response that's wrong:
1. Scroll down below the chat
2. Click "Submit Correction" button
3. Form appears with:
   - **Original Response:** [auto-filled with last agent response]
   - **Corrected Response:** [type what it should have said]
   - **Reason (optional):** [why was it wrong?]
4. Click "Submit Correction"
5. Form disappears, feedback logged

## Step 4: Analyze Feedback (Terminal 2)

```bash
cd /path/to/learning/agent_design
python3 feedback_analysis.py stage1 --report
```

Output shows:
- Feedback entries analyzed
- Patterns identified (tone, policy, etc.)
- Suggestions for new test cases
- Results saved to `stage1/state/feedback_analysis.json`

## Step 5: Generate Golden Set Suggestions (Terminal 2)

```bash
python3 apply_feedback_to_golden.py stage1
```

Output shows:
- Recommended new test cases
- Python code ready to copy-paste
- Results saved to `stage1/feedback_suggestions_stage1.md`

## Step 6: Add Cases to Eval Set (Your Editor)

1. Open `stage1/evals.py`
2. Find the `CASES = [` list
3. Scroll to the END (before closing `]`)
4. Copy all the Python cases from `stage1/feedback_suggestions_stage1.md`
5. Paste into evals.py
6. Save

## Step 7: Verify & Test (Terminal 2)

Verify syntax:
```bash
python3 -m py_compile stage1/evals.py
```
(No output = success)

Run new cases:
```bash
cd stage1
python3 evals.py --runs 1
```

Expected output:
```
PASS  1/1  feedback: tone — empathetic handling...
PASS  1/1  feedback: policy — escalation path...
...
```

## Repeat for Stage 2

Same steps, but replace `stage1` with `stage2` everywhere.

---

## What's Happening Behind the Scenes

**Phase 1: Feedback Collection**
- User interacts with agent in web.py
- When response is wrong, user clicks "Submit Correction"
- `/feedback` endpoint in web.py captures and logs to `state/feedback.jsonl`

**Phase 2: Analysis**
- `feedback_analysis.py` reads feedback entries
- Groups by pattern (tone, policy, info, factual)
- Outputs structured recommendations to `state/feedback_analysis.json`

**Phase 3: Integration**
- `apply_feedback_to_golden.py` generates Python test cases
- Cases are added to `evals.py` CASES list
- Covers the gaps that feedback revealed

**Phase 4: Validation**
- Run evals with new cases
- Both planners should pass them (modularity works)
- Measure if agent improves on new cases

---

## Troubleshooting

### Form doesn't appear
- Refresh browser
- Check browser console (F12) for errors
- Verify `stage1/ui/chat.html` has feedback-form CSS

### Feedback not logging
- Check `stage1/state/feedback.jsonl` exists
- Check web.py console for errors
- Verify `/feedback` endpoint is accessible

### Analysis fails
- Ensure feedback.jsonl has content
- Check JSON format: `cat state/feedback.jsonl | head -1 | python3 -m json.tool`

### Can't add cases to evals.py
- Check for missing commas between cases
- Run `python3 -m py_compile stage1/evals.py` to find syntax errors
- Look at existing cases for format reference

---

## Expected Workflow Time

- Collecting 1-3 feedback entries: 2-5 minutes
- Analyzing feedback: <1 minute (automatic)
- Copying cases to evals.py: 1-2 minutes
- Running new evals: 1-2 minutes
- **Total: ~5-10 minutes per iteration**

---

## Success Metric

- ✅ Feedback collected
- ✅ Analysis runs without errors
- ✅ New cases pass evals
- ✅ Both planners score within 5% on new cases (modularity confirmed)

**If all checks pass: Feedback-driven development is working!**
