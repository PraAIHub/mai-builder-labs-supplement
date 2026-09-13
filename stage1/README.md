# Stage 1 — the core agent

Profile, memory, planning and action, plus a knowledge layer, a web UI, a
trace log and two kinds of evals. The reasoning is in `../README.md`; the
modules are listed in `ami/__init__.py`.

    python3 main.py          # terminal chat, ReAct trace shown
    python3 web.py           # http://localhost:8000  (and /logs)
    python3 evals.py         # score what it did
    python3 golden.py        # score what it said  (--audit grades the judge first)
    python3 -m ami.knowledge "what if it arrives broken"   # see what retrieval returns
    python3 -m ami.embedder  # watch the model separate meaning from wording

`.env` is one folder up. `state/` and `.cache/` are generated on first run;
`results/` is where the eval scripts write, and holds sample runs.
