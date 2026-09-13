"""Amazon support agent — profile, memory, planning, action.

    python3 main.py              ReAct, with the Thought trace
    python3 main.py --quiet      trace hidden
    python3 main.py --baseline   the old loop, no planning and no memory

Type 'memory' at the prompt to dump what the agent currently holds.
"""

import sys

from ami import agent_profile as profile
from ami import planner
from ami.agent import respond
from ami.llm import MODEL
from ami.memory import ConversationMemory, WorkingMemory


def main():
    argv = sys.argv[1:]
    baseline = "--baseline" in argv
    trace = "--quiet" not in argv

    system = profile.system_prompt()
    if not baseline:
        system += planner.PLANNING_RULES

    convo = ConversationMemory(system)     # what was said
    work = WorkingMemory()                 # what is known and done
    mode = "baseline" if baseline else "ReAct"

    print(f"[{profile.NAME} · {MODEL} · {mode}]  (ctrl-c or 'quit' to exit)\n")
    print(f"{profile.NAME}: {profile.GREETING}\n")

    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user:
            continue
        if user.lower() in {"quit", "exit"}:
            break

        if user.lower() == "memory":
            print(f"\n-- conversation memory: {len(convo)} messages")
            print("-- working memory:")
            print(work.brief() or "   (empty)")
            print()
            continue

        convo.add_user(user)
        print()

        if baseline:
            reply = respond(convo.messages(), verbose=trace)
        else:
            reply = planner.react(convo, work, trace=trace)

        print(f"{profile.NAME}: {reply}\n")


if __name__ == "__main__":
    main()
