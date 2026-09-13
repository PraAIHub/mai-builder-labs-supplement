"""Ami, the agent, as a package. One module per element of goals.md:

    agent_profile     PROFILE     who the agent is — the system prompt
    memory            MEMORY      conversation memory and working memory
    planner           PLANNING    the ReAct loop (agent.py is the no-planning baseline)
    tools, store      ACTION      seven tools with guardrails, over a fake order database
    knowledge         KNOWLEDGE   the written rules in ../knowledge/, retrieved by
    embedder                      a small embedding model that runs on the laptop

    llm, pricing      the single model entry point, and what a call costs
    observe           the trace log every model and tool call writes to
    dashboard         the /logs page for web.py

The scripts that run it — main.py, web.py, evals.py, golden.py — live one
folder up, next to this package. Generated files go in ../state/ (sessions,
trace, customer records) and ../.cache/ (the vector index and the model).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent     # the stage folder
