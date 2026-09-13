# Customer Support Agent Debate Blackboard

## Prosecution's Mandate

I will **attack weak reasoning, expose hidden assumptions, and demand evidence** for every claim.

### What I'm Hunting For:
- ❌ **Unfounded assumptions** → "Why are you assuming that?"
- ❌ **False dichotomies** → "Those aren't the only options."
- ❌ **Unpriced trade-offs** → "What are you sacrificing?"
- ❌ **Missing constraints** → "Under what conditions does your argument fail?"
- ❌ **Cherry-picked examples** → "Show me the counterexample."
- ❌ **Circular reasoning** → "You're assuming what you're trying to prove."

### My Prosecutorial Standard:
1. Every claim needs evidence or concrete reasoning.
2. "Better" means better *at something specific, under real constraints*.
3. Trade-offs must be named, quantified, and acknowledged.
4. If you can't explain it to a student, you don't understand it.

---

## Current Question Under Debate
**Is the two-stage modular architecture (Stage 1 core agent + Stage 2 policy/memory/planner layers) good for building and scaling a customer support agent?**

---

## Defense Position
**Argument:**
The staged modular architecture (Stage 1 core + Stage 2 enhancements) is excellent for building scalable customer support agents because it separates concerns, enables incremental validation, and allows swappable implementations without rewriting.

**Evidence/Reasoning:**

1. **Clear separation of concerns** → each module has one job:
   - Profile (who the agent is)
   - Memory (conversation + long-term, keyed by customer)
   - Planning (ReAct loop vs plan-and-execute, swappable)
   - Action (7 guardrailed tools over a fake database)
   - Knowledge (4-shelf vector retrieval with local 17MB embedding model)
   
   This means you can upgrade Memory without touching Planning, or swap planners without rewriting Knowledge.

2. **Built-in observability from day 1** → tracing, pricing, evals:
   - Every LLM and tool call goes to a trace log
   - Cost tracking per call (knows what to optimize)
   - Two eval approaches: behavior-based (cheap, exact) + LLM-graded (sees what users read)
   - `golden.py --audit` proves the eval judge works before you trust the numbers
   
   This catches silent failures: e.g., the "thought field last" bug (moved from first to last in tool args, 7 empty args → 0, golden score 17/27 → 20/27).

3. **Incremental, non-breaking growth** → Stage 2 is a copy of Stage 1 with additions:
   - Policy layer bolts on (input scrubbing, confirmation gate, escalation checks)
   - Long-term memory added without rewriting conversation memory
   - Second planner swappable via UI flag
   - Each stage runs independently (no "old code paths we forgot to test")
   
   You can diff the two stages to see exactly what changed. This is a blueprint for how to evolve without accruing cruft.

4. **Cost-aware from the start** → uses local retrieval model:
   - bge-micro-v2 is 3 transformer layers, 384-dim embeddings, 17MB on disk
   - Runs on the laptop during retrieval (no API calls for embedding)
   - Traded off against cloud embeddings: slower per query, but known cost, no rate limits, and found the right document 10/10 times on the golden set
   
   A scaling agent that doesn't know what it costs will be a surprise when you bill users.

5. **Testable design** → evals are central, not afterthoughts:
   - Golden set is explicit (28 rows in Stage 2)
   - Evals compare against "asked for vs ran" (spies for confirmation and policy)
   - You can score both planners side-by-side (`--planner baseline` vs ReAct vs `--planner plan`)
   
   This surfaces real trade-offs (e.g., ReAct costs +1 tool call per follow-up because it never keeps what it looked up).

**Trade-offs identified:**

- **Locality vs latency**: Local embedding model is slower per query than a cloud API, but predictable and cheaper. Fine for support (latency <1s is acceptable), breaks if you need <100ms.
- **Copying vs DRY**: Stage 2 is a full copy of Stage 1, not a diff-patched build. Means two places to fix bugs, but guarantees each stage runs without depending on a shared layer that might have been refactored. Trade-off: correctness/clarity over file-size efficiency.
- **Simplicity vs completeness**: Only 48 knowledge chunks (policies/rules/tone/regulations). Scales to 500-1000 easily; at 10k+ the local model will slow down and you'll want a vector DB. But you'll know when to jump because you have evals.
- **Two planners, not one**: ReAct and plan-and-execute are maintained separately. Duplication, but each is simple (~100 lines) and you can A/B test without branching.

---

## Peer 2 Position
**Argument:**

**Evidence/Reasoning:**

**Trade-offs identified:**

---

## Prosecution's Case Against the Defense

### 🎯 CHARGE 1: "Swappable modularity" is theoretical, not demonstrated

**Claim:** "You can upgrade Memory without touching Planning, or swap planners without rewriting Knowledge."

**Prosecution's Evidence:**
- You've maintained TWO planners (~100 lines each). That's duplication, not modularity.
- **Question:** Have you actually swapped a THIRD planner without touching the rest? Or have you only proven you can copy-paste two implementations?
- **The test:** If modularity is real, describe exactly what changes in `web.py`, `dashboard.py`, and the eval harness when you add a third planner. If the answer is "it's complicated," modularity is more aspirational than real.

---

### 🎯 CHARGE 2: The "thought field last" bug proves observability, not architecture

**Claim:** "This catches silent failures... the 'thought field last' bug (moved from first to last in tool args, 7 empty args → 0, golden score 17/27 → 20/27)"

**Prosecution's Evidence:**
- One bug doesn't prove causation. A monolithic agent with the same evals would also catch this.
- **Question:** How many bugs did the modular architecture actually PREVENT that wouldn't have been caught anyway?
- **The trap:** You're confusing "we ran evals" with "the modular architecture helped." Evals ≠ modularity. You could run the same evals on a monolith.

---

### 🎯 CHARGE 3: "Local embedding = cheaper" hides a false choice

**Claim:** "Local embedding model is slower per query than cloud API, but predictable and cheaper. Fine for support (latency <1s is acceptable), breaks if you need <100ms."

**Prosecution's Evidence:**
- You declared <1s "acceptable" without evidence. What percentage of support chats fail if the bot takes 900ms to respond?
- **Question:** Did you measure user satisfaction at 900ms vs 200ms? Or is "<1s acceptable" a guess?
- **The real trade-off:** You chose a constraint that makes your architecture look good, then optimized for it. That's not design; that's confirmation bias.

---

### 🎯 CHARGE 4: Copying isn't modularity—it's duplication with extra steps

**Claim:** "Stage 2 is a full copy of Stage 1, not a diff-patched build... guarantees each stage runs without depending on a shared layer."

**Prosecution's Evidence:**
- You have 48 knowledge chunks. If you find a bug in the Profile module, you fix it... twice? Three times?
- **Question:** How many copy-paste bugs have you introduced by maintaining two parallel code trees?
- **The fatal flaw:** "Guarantees each stage runs independently" is just another way of saying "we couldn't refactor this, so we duplicated it instead."

---

### 🎯 CHARGE 5: The 28-row golden set—sampling or cherry-picking?

**Claim:** "Golden set is explicit (28 rows in Stage 2)"

**Prosecution's Evidence:**
- How were these 28 rows selected? Random from production? Hand-picked for representativeness? Selected after you knew what your eval should do?
- **Question:** What's the coverage across edge cases: refusals, escalations, multi-turn conversations, policy violations?
- **The accusation:** A 28-row golden set can be misleading. It might show that ReAct vs plan-and-execute differ by 1 tool call, but that difference might not matter in production.

---

### 🎯 CHARGE 6: Scaling predictions are unfounded

**Claim:** "48 knowledge chunks... scales to 500-1000 easily; at 10k+ the local model will slow down and you'll want a vector DB."

**Prosecution's Evidence:**
- You have no data showing this. You're extrapolating.
- **Question:** What's the latency curve from 48 → 500 → 1000 → 10k? Show the graph.
- **The assumption:** You claim "you'll know when to jump," but you've never actually jumped. This is a guess disguised as experience.

---

### Key Disagreements
- ✗ Is modularity proven by copying, or disproven by it?
- ✗ Does the two-stage architecture prevent bugs, or just make them visible?
- ✗ Is "local embedding <1s is acceptable" a constraint or a rationalization?
- ✗ Is a 28-row golden set representative of production support scenarios?

### Critical Questions to Resolve
1. **What bugs did modularity prevent that a monolith + evals would miss?** (Or did evals do all the work?)
2. **How many production support calls have failed due to >1s latency?** (The 900ms tradeoff needs data.)
3. **At what knowledge chunk size does the local model actually break?** (Predictions aren't evidence.)
4. **How many bugs came from maintaining two parallel code trees?** (Duplication tax must be priced.)

### Points of Agreement
- ✅ Evals catch bugs (but this is orthogonal to modularity)
- ✅ Cost visibility matters (but local embedding's cost vs. cloud needs real numbers)
- ✅ Incremental growth is desirable (but copying isn't the only way)

---

## Defense Rebuttal

### ⚔️ RESPONSE TO CHARGE 1: Modularity is testable, not just theoretical

**Prosecution claims:** "You've only proven you can copy-paste two implementations."

**Defense rebuttal:**
The prosecution conflates "haven't built a third planner yet" with "the architecture doesn't support it." Fair critique—but backward reasoning.

**Evidence that modularity is real:**
1. **The interface is thin and stable:** Both planners accept `(memory, knowledge, tools, profile)` and return `(action, thought)`. This contract hasn't changed. A third planner needs only to implement this interface—nothing in `web.py`, `dashboard.py`, or evals changes. **The burden is on prosecution to explain what WOULD change.**
2. **Isolation is proven:** Each planner can be tested independently via `--planner baseline|react|plan`. Evals can score them side-by-side without code changes. A monolith can't do this without refactoring.
3. **The test:** Add `--planner new_strategy` to evals.py in 3 lines (import, add to CLI choices, call it). No changes to Memory, Knowledge, or Policy. If the interface is modular, this works. Prosecution's claim that "it's complicated" is a guess.

**Concession:** You're right that two examples don't prove general modularity. But they DO prove the hypothesis enough that a third wouldn't require rewriting surrounding systems—and that's what modularity means. A monolith would require rewriting.

---

### ⚔️ RESPONSE TO CHARGE 2: Observability AND modularity are different, and both matter

**Prosecution claims:** "A monolith + evals would also catch the bug."

**Defense rebuttal:**
True. But this is like saying "antibiotics and vaccines both save lives, so vaccines are pointless." They work together.

**What modularity gives you that a monolith doesn't:**
1. **Isolation debugging:** The "thought field last" bug was caught because you could run `evals.py --planner baseline` and see the baseline doesn't have the bug. If the code were a monolith, you'd have to add a test harness to isolate the planner. Modularity gave you the test harness for free.
2. **Root cause clarity:** Because planners are swappable, when one fails differently from the other, you immediately know it's a planner issue, not Memory or Knowledge. A monolith demands a debugger or print statements.
3. **Reuse of evals:** The fact that the same evals work on baseline|react|plan proves modularity is real. A monolith would need a separate harness for each variant.

**Concession:** You're right that the bug itself doesn't *prove* modularity caused it. But the ease of *locating* it and the ability to *compare two implementations* on the same task—that's modularity in action.

---

### ⚔️ RESPONSE TO CHARGE 3: Latency is a constraint, not a rationalization

**Prosecution claims:** "You declared <1s 'acceptable' without evidence."

**Defense rebuttal:**
Fair hit. I don't have user study data. But this isn't a flaw in the architecture—it's a choice that the architecture *makes visible*.

**What I can defend:**
1. **<1s is industry standard for chat:** Slack, Discord, GPT, and most LLM chat UIs target <1s. I didn't invent this; it's the baseline expectation. If you need <100ms, you're not building a chat agent—you're building real-time trading or autonomous vehicles.
2. **The architecture measures it:** Every tool call logs latency. You have the data to know if <1s is good enough. A monolith would also have this, but modularity makes it easier to isolate whether the latency is from the embedding model (Knowledge), LLM calls (Planning), or tool execution (Action).
3. **The decision is reversible:** If you find that <1s isn't acceptable in production, you can:
   - Switch to a cloud embedding API (1 line change in `knowledge.py`)
   - Or use a GPU-accelerated embedding model on the server
   - The modularity means you don't rewrite the whole system.

**Concession:** You're right that I haven't A/B tested <1s vs 200ms with real users. But the claim isn't "1s is perfect"—it's "this architecture lets you measure and decide." That's defensible.

---

### ⚔️ RESPONSE TO CHARGE 4: Copying is a pedagogical choice, not an architectural flaw

**Prosecution claims:** "Copying introduces maintenance tax and copy-paste bugs."

**Defense rebuttal:**
This is the strongest hit. I'll concede the point and explain why it was the right choice anyway.

**Why Stage 2 is a copy, not a shared base:**
1. **This is a class exercise, not production code.** The goal is for students to see how Stage 1 evolves into Stage 2. If it's a shared base + plugins, students see inheritance, generics, and abstraction—complexity that obscures the pedagogical intent.
2. **Independence guarantees testability:** Each stage runs in isolation. No shared bug (e.g., in Profile) breaks both. Evals for Stage 1 don't accidentally use Stage 2's policy layer. This clarity is worth the duplication in an educational context.
3. **Duplication tax is low here:** 48 knowledge chunks + 100-line modules means a bug fix lands in two files. In production code with 48,000 lines, you'd refactor immediately. But at this scale, the cost is acceptable.

**What production code would do:** Extract a `stage_base/` module with Profile, Memory, Knowledge, Observe, LLM. Stage 1 and Stage 2 would inherit and extend. The prose explanation would be the same; the code would be cleaner.

**Concession:** You're absolutely right that this isn't a scalable pattern. For production, it's a liability. But for teaching, it's the right trade-off. The architecture itself (modularity) is sound; the deployment pattern (copying) is a pedagogical choice.

---

### ⚔️ RESPONSE TO CHARGE 5: Golden set sampling is explicit and auditable

**Prosecution claims:** "How were these 28 rows selected? This could be cherry-picking."

**Defense rebuttal:**
Fair question. Let me answer it directly:

**How the 28 rows were selected:**
1. They come from a specific class of support requests: Amazon order issues (returns, cancellations, refunds, tracking).
2. They were written to exercise specific agent behaviors: tool calls (search, cancel, refund), refusals (can't process without confirmation), policy gates (escalation triggers), and long-term memory (recognizing repeat customers).
3. They're **explicitly documented in `golden.json`** so you can audit them.

**Why 28 rows is sufficient for a class exercise:**
- It's enough to surface differences between baseline|react|plan (1-3 tool calls per follow-up).
- It's small enough to grade by hand (the rubric is in `golden.py`).
- It's large enough to catch the bug (thought field issue, confirmation gates, etc.).

**Why this isn't cherry-picking:**
- The rows are versioned in the repo. They didn't change based on what the agent did.
- The `--audit` flag proves the rubric works (perfect reference answers score 1.0, unrelated rows score lower).
- Running `golden.py` after every change would surface regressions.

**Concession:** 28 rows is a *sample*, not complete coverage. You're right that edge cases (multi-turn refusals, policy escalations under load) might not be represented. But the evals framework supports growing the golden set—it's not a fixed cap. The architecture enables this auditing; a monolith wouldn't.

---

### ⚔️ RESPONSE TO CHARGE 6: Scaling is predictable because the architecture is instrumented

**Prosecution claims:** "You have no data. You're extrapolating."

**Defense rebuttal:**
You're right that I haven't measured the 48 → 10k latency curve. But my claim isn't "10k chunks will definitely work fine"—it's "you'll know when to jump because the system is instrumented."

**Evidence for this:**
1. **Every retrieval logs latency:** The `search_knowledge()` call records how long it takes. At 1000 chunks, if latency is 50ms, you know you have headroom. At 10k, if it's 500ms, you can measure the curve.
2. **The decision threshold is observable:** When latency exceeds your SLA (e.g., 500ms for embedding + 200ms for LLM = 700ms total), you switch to a vector DB. You don't guess.
3. **The architecture doesn't lock you in:** If bge-micro-v2 gets slow, you can swap it for a GPU-accelerated model, or switch to Pinecone/Weaviate. The modularity means you don't rewrite Planning or Memory.

**What I'm NOT claiming:**
- "48 chunks definitely scales to 10k without change." (I don't know this.)
- "The curve is linear." (Transformer inference is usually quadratic or worse.)

**What I AM claiming:**
- "This architecture is instrumented to make the scaling decision data-driven, not guesswork."
- "When you hit a wall, swapping Knowledge doesn't break the agent."

**Concession:** You're right to call out that this is a prediction, not evidence. But the *process* (measure, decide, swap) is sound. A monolith would require architectural refactoring at scale.

---

### Key Disagreements (Updated)

- **Modularity:** Is proven by the planner interface, but not yet by a third implementation. Defense: the test is reversible—add a third planner and see if it works.
- **Bug prevention:** Modularity enables isolation and comparison; evals catch bugs either way. Defense: the combination is powerful, neither alone.
- **Latency:** <1s is an industry baseline, but untested in production with real users. Defense: the architecture makes this measurable.
- **Copying vs. refactoring:** Stage 2 copying is a pedagogical choice, not a scalability blueprint. Defense: production code would extract a shared base.
- **Golden set bias:** 28 rows are a sample, possibly unrepresentative. Defense: auditable, versioned, and the framework supports growth.
- **Scaling:** Unproven predictions. Defense: the architecture is instrumented to make the decision data-driven.

---

### Critical Questions Remaining (for Judge and Prosecution)

1. **Add a third planner:** Does it work without changes to surrounding systems? (This decides if modularity is real.)
2. **Measure latency curve:** What's the embedding model's latency at 100, 500, 1000, 5000 chunks? (This decides if the scaling prediction is sound.)
3. **Production code pattern:** Would a shared-base + plugins architecture be better? At what scale is copying unacceptable? (This decides if the pedagogical choice is defensible at scale.)
4. **Duplication bugs:** How many bugs came from maintaining two parallel trees? (This decides if the maintenance tax is real.)
5. **User satisfaction:** Is <1s acceptable for support chat? What percentage of users abandon if response time is >3s? (This decides if the latency constraint is justified.)

---

## Prosecution Counter-Rebuttal

### 🔨 SUMMARY: Defense concedes the core thesis; debate now hinges on scope

The Defense has conceded on **Charge 4** with an explicit admission:
> "copying is a liability" in production code.

This is fatal. The original claim was that the architecture is "excellent for building **scalable** customer support agents." If the scalable version requires abandoning the copying pattern, then the Defense is no longer defending their own architecture—they're defending a *different* architecture that doesn't exist in the codebase.

---

### ⚔️ PROSECUTION'S COUNTER ON DEFENSE REBUTTAL

#### **On Charge 1 (Modularity):**

Defense claims: "The interface is thin and stable; a third planner needs only to implement the interface."

**Prosecution reply:**
- They've specified *what* needs to be stable (the interface), but not *how stable* it actually is.
- **Challenge:** Show me `search_knowledge()` and `execute_action()` interfaces. Are they thin? Or do they leak planning details (e.g., "thought" field ordering)?
- The fact that the "thought field last" bug existed at all suggests the interface isn't as stable as claimed.
- **Concession accepted:** The architecture *could* support a third planner. But "could" ≠ "proven." Until you add it, this remains theoretical.

---

#### **On Charge 2 (Bug Attribution):**

Defense claims: "Modularity + evals work together; modularity gives you the test harness for free."

**Prosecution reply:**
- The test harness (the ability to run `--planner baseline|react|plan`) is nice, but it's not *unique* to modularity.
- A monolith can expose multiple planner implementations via flags too.
- **The real question:** Did modularity *prevent* bugs, or just make them *easier to find*? The Defense has only shown the latter.
- **Challenge:** Name one bug that modularity prevented from existing in the first place. (As opposed to bugs it made easier to detect.)

---

#### **On Charge 3 (Latency Constraint):**

Defense claims: "<1s is industry standard; the architecture makes latency measurable."

**Prosecution reply:**
- **Accepted:** <1s is a reasonable industry baseline.
- **Rejected:** "The architecture makes latency measurable" is true of ANY system with logging. This isn't a modularity feature.
- **The real flaw:** Defense chose a latency constraint that happens to favor their local embedding model, then called it "industry standard" to justify it.
- If the industry standard were <200ms, the Defense would need a different architecture—proving the choice is post-hoc rationalization, not principled design.

---

#### **On Charge 4 (Copying):**

Defense explicitly concedes: "This is a liability in production."

**Prosecution's response:**
This concession **undermines the core thesis.** The claim was that the architecture is "excellent for building scalable customer support agents." If the scalable version looks different (shared base + plugins), then you're not defending *this* architecture—you're defending a *hypothetical* one.

**What this means:**
- For a class exercise: The copying is fine. Modularity is demonstrated at small scale.
- For production: The architecture requires refactoring before it's defensible.
- **The problem:** The original claim doesn't distinguish between these. A student following this pattern to production would hit the "liability" wall.

**Prosecution demands clarity:** Does the Defense recommend this architecture for production customer support agents, or only for educational exercises?

---

#### **On Charge 5 (Golden Set):**

Defense provides details: 28 rows are from Amazon order issues, explicitly documented, versioned.

**Prosecution reply:**
- **Accepted:** The set is auditable and versioned (good practice).
- **Challenged:** Amazon order issues are *one domain*. How many rows cover:
  - Multi-turn conversations (customer escalates after first response fails)?
  - Refusal boundary cases (policy says "escalate," agent refuses)?
  - Long-term memory edge cases (customer mentions a previous interaction from 6 months ago)?
- A 28-row set can look representative and still miss critical behaviors.
- **Challenge:** Show the distribution of evals by category. Are escalations <5 rows? If so, can you trust the eval on escalation logic?

---

#### **On Charge 6 (Scaling):**

Defense reframes: "Not 'scaling works,' but 'system is instrumented to decide when to jump.'"

**Prosecution reply:**
- **Accepted:** Instrumentation is valuable.
- **Shifted goalposts detected:** The original claim was "scales to 500-1000 easily." The reframed claim is just "you'll know when it breaks."
- These are not the same. A monolith with logging also tells you when it breaks.
- **Challenge:** Provide the latency measurements at 48, 100, 500, 1000 chunks. If you have none, this is extrapolation. If you have them, share them. If you don't plan to measure, why make the claim at all?

---

### 🎯 PROSECUTION'S FINAL CASE

**The Defense's architecture is good for:**
- ✅ Teaching modularity in a small-scale setting
- ✅ Measuring quality with evals
- ✅ Isolating planners for comparison

**The Defense's architecture is NOT proven good for:**
- ❌ Production scaling (Defense concedes copying is a liability)
- ❌ Edge case coverage (28-row golden set is a sample)
- ❌ Latency-sensitive use cases (claims lack user data)
- ❌ Knowledge bases >10k chunks (predictions, no measurements)

**The core flaw:** The original claim was "excellent for building **scalable** customer support agents." The Defense has demonstrated excellence at building *small, measurable* customer support agents, then claimed this scales to production. It doesn't—not without architectural refactoring that they've explicitly acknowledged.

---

### Critical Settlement Question

**For the Judge:** Should the verdict be:

1. **"The architecture is excellent for *educational* customer support agents"** (which it is), or
2. **"The architecture is excellent for *scalable production* customer support agents"** (which it's not, by Defense's own admission)?

The original claim was (2). The Defense has proven (1).

---

## 🏛️ JUDGE'S FINAL RULING

### The Question
**"Is the two-stage modular architecture good for building and scaling a customer support agent?"**

### The Verdict

**PROSECUTION WINS on the original question.** 

The Defense contradicted their own thesis by conceding that Stage 2's copying pattern is "a liability in production." If the production-scalable version requires extracting a shared base + plugins (as Defense admitted), then the Defense is defending a *hypothetical architecture*, not the codebase as written.

**However, the Defense wins on reframe.**

If the question is reframed to "*educational* customer support agents," the Defense's architecture is excellent and the Prosecution concedes this.

---

### What This Architecture IS Good For

✅ **Teaching modularity** at small scale (48 chunks, 100-line modules)
✅ **Demonstrating evals** as a first-class design practice
✅ **Isolating concerns** (Profile, Memory, Planning, Knowledge, Action)
✅ **Comparing implementations** (baseline vs. ReAct vs. plan-and-execute)
✅ **Making costs visible** (every LLM + tool call is tracked)

### What This Architecture IS NOT Proven Good For

❌ **Production scaling** beyond 1000 knowledge chunks (copying becomes unmaintainable)
❌ **Latency-sensitive use cases** (<1s is assumed, not validated with user data)
❌ **Edge case coverage** (28-row golden set is insufficient for production)
❌ **Bug prevention** (it enables detection, not prevention)

---

### Settled Design Decisions

| Decision | Judge's Rationale | Recommendation |
|----------|-------------------|-----------------|
| **Use modularity** | Proven effective for teaching and measurement | ✅ Adopt for Stage 1/2 |
| **Copy vs. share** | Copying is pedagogically clear but not production-scalable | ⚠️ Use only for educational exercises; extract `stage_base/` for production |
| **Local embeddings** | Cost-visible but latency unvalidated; <1s assumption needs user research | ⚠️ Measure before committing to production; keep cloud API option reversible |
| **Golden set (28 rows)** | Sufficient for teaching, insufficient for production | ⚠️ Grow to 100+ rows before shipping; stratify by behavior (escalations, refusals, multi-turn) |
| **Planner interface** | Stable for 2 examples, untested for 3+; needs proof | ⏳ Add a third planner to validate; if it requires UI/eval changes, refactor the interface |
| **Instrumentation** | Logging latency is valuable but not unique to modularity | ✅ Keep; use to drive scaling decisions |

---

### The Path Forward

**For this codebase (educational):**
- ✅ Keep the copying pattern (clarity for students)
- ✅ Grow golden set to 50+ rows (add multi-turn, escalations)
- ✅ Add a third planner (validate modularity claims)
- ✅ Measure embedding latency at 100, 500, 1000 chunks

**For production use:**
- ⚠️ Extract `stage_base/` with shared Profile, Memory, Knowledge, Observe, LLM
- ⚠️ Make Stage 1 and Stage 2 inherit and extend (DRY)
- ⚠️ A/B test latency: measure user satisfaction at <1s vs. <200ms
- ⚠️ Grow knowledge base to 5k+ chunks and stress-test with vector DB

---

### Critical Unresolved Questions (for Future Work)

These remain open because they require *measurement*, not debate:

1. **Does a third planner work without UI/eval changes?** (Validates modularity)
2. **What's the embedding latency at 1000, 5000, 10k chunks?** (Validates scaling)
3. **Do users abandon at >1s latency?** (Validates the constraint)
4. **How many copy-paste bugs appeared in Stage 2?** (Validates the tax)
5. **What's the distribution of golden set rows by behavior?** (Validates coverage)

---

## Settled Decisions
- ✅ **Modularity is sound** for small-scale educational agents
- ✅ **Evals catch bugs** and enable measurement (orthogonal to architecture)
- ✅ **Copying enables clarity** in teaching but is a production liability
- ⚠️ **Latency assumption (<1s) needs user validation** before production
- ⏳ **Scaling to 10k chunks is unproven** and needs measurement

---

## Open Questions

---

## Design Decisions Log

| Decision | Rationale | Status |
|----------|-----------|--------|
| | | ⏳ |
| | | ✅ |

---

## Constraints & Requirements
- **Context:** Building a customer support agent
- **Goal:** Reach consensus on best approach
- **Scope:** 
- **Timeline:**

---

**Last Updated:** 2026-09-13
