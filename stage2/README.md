# Stage 2 — the same agent, plus a policy layer, long-term memory and a second planner

A complete copy of Stage 1 with three things added, so it runs on its own.
The reasoning and the file-by-file map are in `../README.md` under
**Stage 2**. Every file that differs from its Stage 1 twin says so at the
top of its docstring.

    New:        ami/policy.py  ami/plan_execute.py
    Changed:    ami/planner.py  ami/tools.py  ami/agent_profile.py  ami/memory.py
                main.py  web.py  ui/chat.html  evals.py  golden.py  golden.json
    Unchanged:  everything else

    python3 web.py                            # http://localhost:8000 — planner switch in the header
    python3 main.py --plan                    # plan-and-execute in the terminal
    python3 evals.py --runs 2                 # score ReAct
    python3 evals.py --planner plan --runs 2  # score plan-and-execute
    python3 golden.py --audit                 # grade the judge itself, first
    python3 golden.py                         # 28 rows, including the policy layer

`.env` is one folder up. `state/` (sessions, trace, customer records) and
`.cache/` are generated on first run; `results/` is where the eval scripts
write, and holds sample runs.
