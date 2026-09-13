# Feedback-Driven Development Runbook

## Overview

This runbook documents the complete workflow for collecting human feedback, analyzing it, and integrating findings back into the golden test set to improve the agent.

## Prerequisite: Bravo's UI Integration

Once Bravo integrates the feedback form into `stage1/ui/chat.html` and `stage2/ui/chat.html`, the `/feedback` endpoint will accept corrections:

```
POST /feedback
{
  "original_response": "...",
  "corrected_response": "...",
  "timestamp": "2026-09-13T12:00:00Z"
}
```

Logged to: `state/feedback.jsonl` (one JSON object per line)

## Phase 1: Collect Feedback (User-Driven)

**Where:** Live web UI at `http://localhost:8000`

**How:**
1. Run: `python3 web.py` in stage1 (or stage2)
2. Chat with the agent
3. If response is wrong, click "Submit Correction" button
4. Fill form: paste agent response, paste corrected version, add reason (optional)
5. Submit → logs to `state/feedback.jsonl`

**Success metric:** 5-10 feedback entries collected per stage

## Phase 2: Analyze Feedback (Automated)

**When:** After collecting 5+ feedback entries

**Command:**
```bash
python3 feedback_analysis.py --both --report
```

**What it does:**
1. Reads `state/feedback.jsonl` from both stages
2. Identifies patterns:
   - `wrong_tone`: Agent too formal or lacks empathy
   - `policy_gap`: Missing escalation path or policy knowledge
   - `incomplete_info`: Omits relevant details
   - `factual_error`: Incorrect info or passive language
3. Outputs:
   - `state/stage1/feedback_analysis.json` - structured analysis
   - `state/stage2/feedback_analysis.json` - structured analysis
   - Console report with pattern counts and recommendations

**Example output:**
```
Analysis Summary:
  • Total corrections: 5
  • Unique patterns: 4
  • Novel cases needed: 5
  • Existing rows to boost: 0
```

## Phase 3: Generate Golden Set Suggestions (Automated)

**Command:**
```bash
python3 apply_feedback_to_golden.py --both
```

**What it does:**
1. Reads `state/feedback_analysis.json`
2. Generates Python code for new test cases based on feedback patterns
3. Outputs:
   - `feedback_suggestions_stage1.md` - Python code to copy
   - `feedback_suggestions_stage2.md` - Python code to copy
   - Console display with suggested changes

**Example output:**
```python
# Feedback-driven case: wrong_tone
{
    "name": "feedback: tone — empathetic handling (feedback case 1)",
    "description": "Customer with frustration needs empathetic, conversational response",
    "turns": ["I've had multiple issues with my order and the previous responses haven't helped."],
    "reply_has": ["understand", "frustrat", "help"],
    "reply_lacks": ["unfortunately", "procedure"],
},
```

## Phase 4: Expand Golden Set (Manual - Copy-Paste)

**For stage1:**
1. Open `stage1/evals.py`
2. Find the `CASES = [` list
3. Copy all cases from `feedback_suggestions_stage1.md`
4. Paste at the END of the CASES list (before the closing `]`)
5. Save file

**For stage2:**
1. Open `stage2/evals.py`
2. Find the `CASES = [` list
3. Copy all cases from `feedback_suggestions_stage2.md`
4. Paste at the END of the CASES list
5. Save file

**Verification:** Run Python syntax check
```bash
python3 -m py_compile stage1/evals.py stage2/evals.py
```
(No output = success)

## Phase 5: Test New Cases (Automated)

**Run evals with new cases:**

For stage1:
```bash
cd stage1
python3 evals.py --runs 1
```

For stage2:
```bash
cd stage2
python3 evals.py --runs 1
```

**Expected output:**
```
PASS/FAIL  1/1  feedback: tone — empathetic handling...
```

**Success metric:**
- New cases should PASS with both `--planner react` (default) and baseline
- Score delta between planners should be < 5%

## Phase 6: Measure Impact (Analysis)

**Compare before/after:**
1. Save baseline eval results (before feedback cases):
   ```bash
   python3 stage1/evals.py > baseline_stage1.txt
   ```
2. Add feedback cases, re-run:
   ```bash
   python3 stage1/evals.py > updated_stage1.txt
   ```
3. Compare:
   ```bash
   diff baseline_stage1.txt updated_stage1.txt
   ```

**Key metrics:**
- Total pass rate (did new cases pass?)
- Cost delta (any regression in latency/cost?)
- Planner comparison (are both planners still aligned?)

## Repeat Cycle

Once new feedback comes in:
1. Run `feedback_analysis.py --both --report`
2. Run `apply_feedback_to_golden.py --both`
3. Add new cases to evals.py
4. Re-run evals and measure impact

## Troubleshooting

### No feedback collected
**Problem:** `state/feedback.jsonl` is empty after running web.py
**Solution:** 
- Verify web.py is running (`http://localhost:8000` loads)
- Check that feedback form HTML is present (open browser DevTools → Elements)
- Manually test: Chat, intentionally give wrong response, submit correction
- Check `state/feedback.jsonl` exists and is writable

### Analysis fails
**Problem:** `python3 feedback_analysis.py` raises error
**Solution:**
- Verify `state/feedback.jsonl` exists and has content
- Check JSON format: `cat state/feedback.jsonl | head -1 | python3 -m json.tool`
- Ensure both stages exist

### New cases don't parse
**Problem:** Python syntax error after pasting cases into evals.py
**Solution:**
- Check for missing commas between cases
- Ensure quotes are balanced
- Run `python3 -m py_compile stage1/evals.py` to identify line number
- Copy-paste code from suggestions file more carefully

### New cases fail evals
**Problem:** New feedback-driven cases report "FAIL"
**Solution:**
- Review the case assertions (reply_has, reply_lacks)
- May need to adjust agent prompt to match expectations
- Or case definition was too strict — relax assertions and re-run
- This is expected for cases that expose real agent gaps; goal is to expose and fix

## Files Created by This Workflow

```
stage1/
  ├── state/
  │   ├── feedback.jsonl             ← User feedback (logged by /feedback endpoint)
  │   ├── feedback_analysis.json     ← Analyzed patterns & recommendations
  │   └── feedback_suggestions_stage1.md  ← Python code to add to evals.py
  └── evals.py                        ← Modified with new feedback-driven cases

stage2/
  ├── state/
  │   ├── feedback.jsonl
  │   ├── feedback_analysis.json
  │   └── feedback_suggestions_stage2.md
  └── evals.py                        ← Modified with new feedback-driven cases

Root:
  ├── feedback_analyzer.py            ← Basic pattern extraction
  ├── feedback_analysis.py            ← Main analysis pipeline
  ├── integrate_feedback.py           ← Gap identification
  ├── apply_feedback_to_golden.py    ← Generate Python code
  └── FEEDBACK_INTEGRATION_RUNBOOK.md ← This file
```

## Key Insights

1. **Feedback closes the loop:** Measure → Feedback → Improve → Measure again
2. **Patterns matter:** Grouping by tone/policy/info helps prioritize fixes
3. **Golden set grows:** Each feedback cycle adds 1-5 new test cases
4. **Both planners tested:** New cases validate that modularity still works
5. **Local and reversible:** All feedback analysis runs locally; no model calls needed (proxy budget safe)

## Next Steps

1. ✅ Bravo: Integrate feedback UI into web.py (in progress, ETA soon)
2. ✅ Charlie: Feedback analysis pipeline ready (Phases 2-3 scripted)
3. 🔄 User: Run web.py, collect feedback, trigger analysis cycle
4. 🔄 User: Copy-paste new cases into evals.py, measure impact
5. 📊 Measure: Compare eval results before/after each feedback cycle
