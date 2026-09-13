# Ami — an Amazon support agent, built in two stages

A class exercise. Three dependencies — `openai`, `python-dotenv` and
`chromadb` — plus a 17 MB embedding model the agent downloads itself, and
the class LLM proxy configured in `.env`.

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # then paste your proxy key into it
cd stage1 && python3 web.py          # http://localhost:8000
```

## Layout

```
agent_design/
├── README.md            this file
├── goals.md             the brief: four elements, simple Python
├── requirements.txt     shared by both stages
├── .env                 the class LLM proxy key, shared by both stages (copy .env.example)
├── stage1/              the core agent
└── stage2/              the same agent, plus a policy layer, long-term memory and a second planner
```

Work through Stage 1 first. Stage 2 is a copy of it with three things
added, so each stage runs on its own and you can diff them. Both stages
have the same shape:

```
stage1/
├── main.py              terminal chat
├── web.py               browser UI at http://localhost:8000, with a /logs page
├── evals.py             score what the agent DID
├── golden.py            score what the agent SAID, against golden.json
├── ami/                 the agent — one module per element, listed in ami/__init__.py
├── ui/                  the two pages the browser gets: chat.html and logs.html
├── knowledge/           the written rules the agent retrieves from
├── results/             what the two eval scripts write; sample runs included
├── state/               generated: sessions.json, trace.jsonl (Stage 2: customers.json)
└── .cache/              generated: the vector index and the embedding model
```

`state/` and `.cache/` appear on first run and can be deleted at any time.

## Stage 1 — the core agent

The four elements from `goals.md`, one module each in `ami/`, plus a web
UI and observability:

| Module | Element |
|---|---|
| `ami/agent_profile.py` | **Profile** — who the agent is (the system prompt) |
| `ami/memory.py` | **Memory** — conversation memory + working memory |
| `ami/planner.py` | **Planning** — the ReAct loop (`ami/agent.py` is the no-planning baseline) |
| `ami/tools.py`, `ami/store.py` | **Action** — seven tools with guardrails, over a fake order database |
| `knowledge/`, `ami/knowledge.py`, `ami/embedder.py` | **Knowledge** — four shelves of written rules in a vector database, retrieved by a model that runs on the laptop |
| `ami/llm.py`, `ami/pricing.py` | the single model entry point, and what a call costs |
| `web.py`, `ami/dashboard.py`, `ui/` | browser UI (stdlib `http.server`) and the `/logs` page; the markup is in `ui/chat.html` and `ui/logs.html` |
| `ami/observe.py` | the trace log every model and tool call writes to |
| `evals.py` | **Evals** — what the agent DID: tools called, refusals, the store afterwards |
| `golden.py`, `golden.json` | **Evals** — what the agent SAID, graded against reference answers |

```
cd stage1
python3 main.py          # terminal chat, ReAct trace shown
python3 web.py           # http://localhost:8000  (and /logs)
python3 evals.py         # score what it did
python3 golden.py        # score what it said  (--audit grades the judge first)
python3 -m ami.knowledge "what if it arrives broken"   # see what retrieval returns
python3 -m ami.embedder  # watch the model separate meaning from wording
```

Both eval scripts write to `results/`. The files already there are sample
runs from 12 September 2026; regenerate before quoting them.

### The knowledge layer

`knowledge/` holds four kinds of writing, because they are used at different
moments — and every retrieved passage says which kind it is:

| | |
|---|---|
| `policies/` | what the customer is entitled to |
| `rules/` | what this agent may and may not do |
| `tone/` | how to say it, especially when the answer is no |
| `regulations/` | the law a policy rests on |

Each `##` section becomes one chunk — 48 of them — embedded by
**bge-micro-v2**: 3 transformer layers, 384 numbers per chunk, 17 MB on
disk, downloaded from Hugging Face on first run into `.cache/models/`.
It is distilled from BGE, a model built for retrieval, which is why
something this small gets the right document 10 times out of 10 here.
Nothing extra is installed to run it: `chromadb` already brings
`onnxruntime` and `tokenizers`.

The index lives in `.cache/chroma/` and rebuilds itself when a document
changes. The whole of `.cache/` is generated — delete it and it comes back.

**One finding worth the detour.** chromadb can filter by metadata while it
searches, so `search_knowledge` first offered the model a `category`
argument. It made things worse. The model guesses the category from a
question it has not yet researched, guesses `policies` for nearly
everything, and a filter does not rank the right passage lower — it
removes it:

```
"already disputed the charge with their bank"
    filtered to policies   0.750  policies/cancellations.md     wrong
    no filter              0.885  regulations/refunds-...md     right
```

When the guess was right, the filtered result was identical to the
unfiltered one. So the filter never helped and sometimes broke it, and no
score threshold separates the two cases. The argument is gone from the
tool and the reasoning is next to `search()` in `ami/knowledge.py`.
Retrieval across the golden set went from 0.43 to 0.86 on that one change.

### What the evals caught

Two findings the golden set produced that no amount of reading would have:

**The reasoning field goes last.** The ReAct loop adds a required `thought`
argument to every tool so the model plans before it acts. Putting it FIRST
reads better and cost real answers: the model wrote the thought and stopped,
emitting `cancel_order({})` with no order id. 7 of 41 tool calls came back
with empty arguments, and the customer got "please try Your Orders" instead
of "it already shipped". One key moved to the end of the dict: 0 of 39, and
20 of 27 golden rows clean instead of 17. A model writes JSON left to right,
so whatever comes first is what it commits to.

**The retrieval filter, above.** Both are in the code as comments, with the
numbers, next to the line that depends on them.

Two evals, because they ask different questions. `evals.py` asserts: these
tools in this order, this refusal, this order status afterwards — exact,
cheap, and blind to the sentence the customer actually reads. `golden.py`
grades that sentence against a reference answer written by hand: strings by
substring match, then correctness and groundedness by an LLM judge on a
three-point rubric you can read in the file.

Run `--audit` before believing either. It feeds every reference answer back
as if the agent had said it (the judge must score 1.0) and an unrelated
row's reference as a decoy (the judge must score it lower). A judge that
cannot tell those apart makes every number below it noise.

Both scripts take `--planner baseline` to score `ami/agent.py` instead —
the loop with no planning and no memory. That is the honest way to find out
what the ReAct loop bought you: it costs a tool call more per follow-up,
because it never keeps what it already looked up.

## Stage 2 — `stage2/`

The same agent with three additions, and the evals to match. `stage2/` is
a complete copy of `stage1/`, so it runs on its own:
`cd stage2 && python3 web.py`.

| Addition | Where |
|---|---|
| **Policy layer** — input scrubbing, confirmation gate, escalate-once, output verification | `ami/policy.py` |
| **Long-term memory** — a third kind, keyed by customer, across conversations | `LongTermMemory` in `ami/memory.py`, stored in `state/customers.json` |
| **Second planner** — plan-and-execute, switchable in the UI | `ami/plan_execute.py` |
| **Evals grow with it** — confirmation turns, policy-layer cases, `--planner plan` | `evals.py`, `golden.py`, `golden.json` |

### What changed, file by file

Every file in `stage2/` that differs from its Stage 1 twin says so at the
top of its docstring. Every file not listed as new or changed is
byte-identical to the one in `stage1/`.

| | File | What Stage 2 does to it |
|---|---|---|
| New | `ami/policy.py` | three checkpoints: `check_input`, `guarded_run`, `check_output` |
| New | `ami/plan_execute.py` | plan, execute, answer — same signature as `planner.react`, so the two are interchangeable |
| Changed | `ami/planner.py` | tool calls go through `policy.guarded_run`; the per-step note adds long-term memory |
| Changed | `ami/tools.py` | `cancel_order` and `start_return` declare a `confirmed` flag; the functions themselves are untouched |
| Changed | `ami/agent_profile.py` | one rule added: preview, ask, then confirm |
| Changed | `ami/memory.py` | `LongTermMemory`; `turn` and `pending` on `WorkingMemory` for the confirmation gate |
| Changed | `ami/__init__.py` | lists the two new modules |
| Changed | `main.py`, `web.py`, `ui/chat.html` | policy checks around every turn, long-term memory read and written, `--plan` and a planner switch |
| Changed | `evals.py`, `golden.py`, `golden.json` | two spies (asked for vs ran), a confirmation turn where an order changes, three policy cases and one golden row, `--planner plan` instead of `baseline` |
| Same | `ami/agent.py`, `ami/store.py`, `ami/knowledge.py`, `ami/embedder.py`, `ami/llm.py`, `ami/pricing.py`, `ami/observe.py`, `ami/dashboard.py`, `ui/logs.html`, `knowledge/` | Stage 1, unchanged |

To see the whole delta in one command (`-ru` instead of `-rq` shows the lines):

```
diff -rq -x .cache -x state -x results -x __pycache__ -x '*.md' stage1 stage2
```

```
cd stage2
python3 main.py --plan                    # plan-and-execute in the terminal
python3 evals.py --runs 2                 # score ReAct
python3 evals.py --planner plan --runs 2  # score plan-and-execute
python3 golden.py                         # 28 rows, now including the policy layer
python3 golden.py --audit                 # grade the judge itself, first
```

Both stages share `.env` and `requirements.txt` from the folder above, and
keep their own `state/`, `.cache/` and `results/`.

## Feedback Loop — Human Corrections into Golden Sets

The feedback system captures human corrections, analyzes patterns, and proposes
updates to golden.json to improve the agent.

### Feedback capture workflow

The workflow starts with human evaluation:

1. **Humans evaluate agent responses**: When running the agent (via `web.py` or
   `main.py`), humans note when the agent gets something wrong.

2. **Bravo captures feedback**: Agent Bravo in the swarm collects corrections
   into `state/feedback.jsonl`, one line per feedback entry. Each entry
   records what the agent should have said, and what category of error it was.

3. **Charlie analyzes feedback**: You run `feedback_analysis.py` to extract
   patterns from the feedback and propose golden.json changes.

### Analysis step-by-step

```bash
# In either stage1 or stage2:
python3 feedback_analysis.py                # Analyze current feedback
python3 feedback_analysis.py --propose      # Show proposed changes
python3 feedback_analysis.py --apply        # Apply proposals to golden.json
```

**What it does:**

1. **Read feedback**: `state/feedback.jsonl` (created by Bravo)
2. **Categorize**: Group corrections by type:
   - `tone`: response is technically correct but sounds wrong
   - `policy_violation`: agent violated a policy rule
   - `incomplete_info`: agent left out key information
   - `factual_error`: agent stated something false
   - `knowledge_gap`: agent didn't know something it should have looked up
3. **Find patterns**: Which golden rows get the most feedback? What
   categories dominate?
4. **Propose changes**: When a row gets 2+ feedback entries in the same
   category, suggest adding tags (e.g., "tone", "policy") to flag it
   for higher weight in training
5. **Output summary**: `state/feedback_summary.json` with patterns,
   recommendations, and next steps

### Feedback format (JSONL)

Bravo writes feedback like this:

```json
{
  "golden_id": "ord-status",
  "correction": "What the agent should have said...",
  "category": "tone",
  "issue": "Agent tone was too formal",
  "timestamp": "2026-09-13T10:00:00Z",
  "feedbacker": "human"
}
```

### Before/after evaluation

Compare golden set scores before and after feedback integration:

```bash
# Stage 1 & 2:
python3 evals.py              # Baseline score on current golden.json
python3 feedback_analysis.py  # Run analysis
python3 feedback_analysis.py --apply  # Apply proposals
python3 evals.py              # New score after proposals applied
```

The `--feedback` flag shows analysis summary during eval runs:

```bash
python3 evals.py --feedback   # Shows feedback impact while running evals
```

### Example: Feedback → Golden Update

**Before:**
```json
{
  "id": "ord-track",
  "tags": ["orders"],
  "turns": ["Where is order 112-2222222-2222222?"],
  "reference": "The Instant Pot Duo 6qt is in transit with Amazon Logistics..."
}
```

**Human feedback:** "Agent response lacked shipping origin location"

**Analysis result:** `incomplete_info` category flagged for `ord-track`

**Proposal:** Update reference to include origin:
```json
{
  "id": "ord-track",
  "tags": ["orders", "knowledge_gap"],
  "turns": ["Where is order 112-2222222-2222222?"],
  "reference": "The Instant Pot Duo 6qt is in transit with Amazon Logistics. It shipped from Edison, NJ on September 12..."
}
```

**Apply with:**
```bash
python3 feedback_analysis.py --apply
```

Then re-run evals to score the updated golden set.

### Integration with policy layer (Stage 2)

Policy violations in feedback suggest the policy.py layer needs tuning:

```
feedback category: policy_violation → suggests: review policy.py guardrails
feedback category: tone              → suggests: review agent_profile.py tone
feedback category: factual_error     → suggests: update knowledge/ documents
```

### Notes

- Feedback is **separate** from the knowledge base (`knowledge/`).
- Feedback **directly updates golden.json** golden rows.
- Golden.json **controls what we grade against** (via `golden.py`), so
  updating it makes the agent "learn" from corrections.
- A golden row gets proposed changes **only if** the same feedback category
  appears 2+ times across the feedback set (threshold prevents noise).
- Backup: `golden.json.bak` is created when applying proposals.
