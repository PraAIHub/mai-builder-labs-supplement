# Multiagent Debate Guide: Customer Support Agent Architecture

This document walks through a real debate between three agents—**Defense**, **Prosecution**, and **Judge**—on whether a two-stage modular architecture is good for building scalable customer support agents. Use this as a template for structuring your own debates.

---

## Part 1: Setting Up the Debate

### Roles

- **Defense**: Makes the affirmative case with evidence.
- **Prosecution**: Attacks weak reasoning, demands proof, finds hidden assumptions.
- **Judge**: Evaluates both sides, identifies cruxes, makes a ruling.

### The Question (Clear & Scoped)

*"Is the two-stage modular architecture (Stage 1 core agent + Stage 2 policy/memory/planner layers) good for building and scaling a customer support agent?"*

**Why this matters:** The word "scalable" is critical. It sets a high bar. "Good for teaching" ≠ "good for production."

---

## Part 2: The Defense's Opening

### What Made It Strong

1. **Specificity**: Named 5 concrete reasons (not hand-waving):
   - Clear separation of concerns
   - Built-in observability from day 1
   - Incremental, non-breaking growth
   - Cost-aware from the start
   - Testable design

2. **Evidence**: Provided real details:
   - "bge-micro-v2 is 3 transformer layers, 384-dim embeddings, 17MB on disk"
   - "thought field last" bug: "golden score 17/27 → 20/27"
   - "28 rows in Stage 2" (golden set)
   - "Found the right document 10/10 times on the golden set"

3. **Trade-offs Named**: Didn't hide the downsides:
   - "Locality vs latency: slower per query, but predictable"
   - "Copying vs DRY: two places to fix bugs"
   - "Simplicity vs completeness: 48 chunks → 500-1000 easy, 10k+ breaks"

### What Looked Weak (Before Prosecution Attacked)

- "Scales to 500-1000 easily" — no data, just a claim
- "<1s is acceptable" — declared without user research
- "Copying guarantees independence" — sounds like a rationalization
- "You'll know when to jump" — assumes you'll measure

---

## Part 3: The Prosecution's Opening Attack

### The Prosecution's Mandate (Good Practice)

They declared what they'd hunt for:
- ❌ Unfounded assumptions
- ❌ False dichotomies  
- ❌ Unpriced trade-offs
- ❌ Missing constraints
- ❌ Cherry-picked examples
- ❌ Circular reasoning

**Lesson:** Make your evaluation criteria explicit. This prevents debates from wandering.

### Six Specific Charges

1. **Modularity is theoretical, not demonstrated** → "Only 2 planners proven, no third"
2. **Bug-catching ≠ modularity** → "A monolith + evals would catch the same bug"
3. **Latency assumption is unfounded** → "No user data on 900ms tolerance"
4. **Copying isn't modularity** → "It's duplication with extra steps"
5. **Golden set is unrepresentative** → "28 rows, no proof of coverage"
6. **Scaling is extrapolation** → "No data from 48 → 10k chunks"

**Lesson:** Format your attacks as numbered charges. Makes them easy to reference and rebut.

---

## Part 4: The Defense's Rebuttal

### How They Responded

- **Charge 1 (Modularity)**: Defined the interface precisely (`(memory, knowledge, tools, profile) → (action, thought)`) and claimed it's stable. "A third planner needs only 3 lines in evals.py."
  
- **Charge 2 (Bug-catching)**: Conceded the point but reframed. "Evals + modularity work together (antibiotics + vaccines)."
  
- **Charge 3 (Latency)**: Defended with industry baseline ("Slack, Discord, GPT all target <1s").
  
- **Charge 4 (Copying)**: **Made a big concession.** "This is the strongest hit. I'll concede. Copying is a liability in production."
  
- **Charge 5 (Golden set)**: Provided detail: "From Amazon order issues, documented in golden.json, versioned."
  
- **Charge 6 (Scaling)**: Reframed the claim. "Not 'scales to 10k' but 'system is instrumented to decide when to jump.'"

### What Made This Rebuttal Strong

1. **Conceded on Charge 4** — a smart move. Taking the hit honestly earns credibility.
2. **Reframed Charges 3 & 6** — shifted to defensible claims ("industry baseline," "instrumented").
3. **Provided missing detail on Charge 5** — showed the golden set wasn't arbitrary.

### What Remained Weak

- Still no data for Charges 3 & 6
- Charge 1: "3 lines" claim was untested
- Charge 2: Didn't name a bug that modularity *prevented* (only detected)

---

## Part 5: The Prosecution's Counter-Rebuttal

### The Pivot: Identifying the Fatal Contradiction

The Prosecution noticed something critical:

> **Original claim:** "excellent for building *scalable* customer support agents"
> 
> **Defense's concession:** "copying is a liability in production"
> 
> **Contradiction:** If the production version looks different (shared base + plugins), you're defending a *hypothetical architecture*, not this one.

**Lesson:** Always check if a concession undermines the original thesis. This is the crux of debate.

### Their Responses

On each charge, they either:
- **Accepted** (golden set versioning: "good practice")
- **Challenged** (latency: "post-hoc rationalization to fit your architecture")
- **Reframed** (scaling: "goalpost shift from 'scales easily' to 'you'll know when it breaks'")

### Final Case

They summarized what Defense IS good for vs. what it ISN'T:

**✅ Good for:**
- Teaching modularity at small scale
- Measuring quality with evals
- Isolating planners for comparison

**❌ NOT proven good for:**
- Production scaling
- Edge case coverage
- Latency-sensitive use cases
- Knowledge bases >10k chunks

**Lesson:** End with a clear summary table. Forces you to be honest about scope.

---

## Part 6: The Judge's Ruling

### The Crux Identified

The core question became: **Is this architecture good for educational agents or production-scalable agents?**

- The Defense proved (A) but claimed to prove (B).
- The Prosecution caught the contradiction.

### The Verdict Structure

1. **Award the original question** → Prosecution wins (Defense contradicted themselves)
2. **Acknowledge the reframe** → Defense wins if question is "educational only"
3. **Map what's proven** → Modularity works at this scale; scaling unproven
4. **Settle design decisions** → Which claims are firm? Which need measurement?
5. **List open questions** → What still needs testing?

### Key Lessons

- **Don't over-claim.** "Good for teaching" is defensible. "Good for production scaling" requires data.
- **Scope matters.** The original question included "scaling." That's a high bar.
- **Concessions are powerful.** Defense's honesty about the copying liability was good debate practice but undermined their original thesis.
- **Measurement beats debate.** Many open questions could only be settled by experiments.

---

## Part 7: Template for Your Own Debates

### Setup Phase

1. **Define the question clearly** (include scope words like "scalable," "production," "teaching")
2. **Assign roles** (Defense, Prosecution, Judge)
3. **Declare evaluation criteria** (Prosecution states what they'll hunt for)

### Opening Positions

1. **Defense makes case**: 3-5 evidence points, each with specifics
2. **Defense names trade-offs**: Show you understand the downsides
3. **Prosecution lists charges**: 4-6 numbered attacks

### Rebuttals

1. **Defense responds to each charge**: Accept, challenge, or reframe
2. **Prosecution counter-rebuts**: Identify contradictions and goal-post shifts
3. **Judge identifies the crux**: What's the real disagreement?

### Resolution

1. **Judge awards the original question** (who proved their case?)
2. **Judge identifies what IS proven** (where do both sides agree?)
3. **Judge maps the reframe** (if the question changes, does the verdict change?)
4. **Judge settles design decisions** (what's firm? What needs measurement?)
5. **Judge lists open questions** (what still needs testing?)

---

## Part 8: Common Debate Moves (and How to Counter Them)

### Move: "It's an industry standard"
- **Defense uses it for**: Latency <1s (because Slack, Discord, GPT use it)
- **Prosecution counters**: "That doesn't mean it's right for YOUR use case"
- **Judge rules**: Needs user data, not just competitive parity

### Move: "The architecture makes it measurable"
- **Defense uses it for**: Scaling (logs latency, so you'll know when to jump)
- **Prosecution counters**: "A monolith with logging also tells you when it breaks"
- **Judge rules**: True, but the isolation benefit is real (easier to debug)

### Move: Reframing the claim
- **Defense uses it for**: "Not 'scales to 10k,' but 'instrumented to decide when to jump'"
- **Prosecution catches it**: "Goalpost shift"
- **Judge rules**: Reframes are OK if you acknowledge them; hiding them is not

### Move: Conceding strategically
- **Defense does it for**: Copying (admits it's a liability)
- **Prosecution uses it against them**: "Then why claim it's good for production?"
- **Judge appreciates it**: Honesty earns credibility, but don't concede the thesis

---

## Part 9: What Students Should Learn

### Strong Debate Skills

1. **Make claims specific** — "separates concerns" is weak; "Profile, Memory, Planning, Action, Knowledge are independent" is strong
2. **Back claims with evidence** — "found the right document 10/10 times" beats "works well"
3. **Name your trade-offs** — "faster vs. cheaper" shows you think clearly
4. **Concede when hit** — Honesty builds credibility (but don't concede the thesis)
5. **Demand evidence** — "Show the latency curve at 1000 chunks" is a better question than "Why doesn't this work?"

### Debate Traps to Avoid

1. **Moving goalposts** — "scales easily" → "you'll know when to jump" (Prosecution caught this)
2. **Confusing detection with prevention** — "evals catch bugs" ≠ "modularity prevents bugs"
3. **Cherry-picking constraints** — Choosing a latency target that favors your architecture
4. **Claiming victory on a different question** — Proving something is "good for teaching" doesn't prove it's "good for production"
5. **Letting concessions undermine your thesis** — If you say "copying is a liability in production," don't claim the architecture is "scalable"

### How to Judge Well

- Identify the **crux** (the one thing that, if resolved, settles the debate)
- Distinguish what's **proven** from what's **assumed**
- Accept **reframes** only if the other side acknowledges them
- Demand **measurement** when debate can't settle it
- Award based on the **original question**, not a reframed one
- **Summarize concessions** clearly (they're evidence of clear thinking)

---

## Part 10: The Debate Record

The full blackboard is in `blackboard.md`. Use it as a reference:
- See the exact wording of charges and rebuttals
- Notice how Defense conceded on Charge 4 (copying)
- Watch how Prosecution caught the goalpost shift on Charge 6 (scaling)
- Read the Judge's ruling on the crux (educational vs. production)

---

## Conclusion

This debate models good thinking:
- ✅ Specific claims with evidence
- ✅ Honest concessions
- ✅ Sharp attacks on weak reasoning
- ✅ Reframing when appropriate (but only if acknowledged)
- ✅ Measurement as the tiebreaker

The Defense built a good architecture for teaching. They proved it. But they over-claimed about production scaling, and the Prosecution caught them. That's not a failure—that's how debate sharpens thinking.

**For your own projects:** Use this structure to debate architectural choices with your team. It makes disagreements productive instead of emotional.
