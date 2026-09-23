"""Amazon support agent — profile, memory, planning, action, policy, RAG.

    python3 main.py                  ReAct planner, with the trace
    python3 main.py --plan           plan-and-execute planner
    python3 main.py --quiet          trace hidden
    python3 main.py --baseline       the original loop: no planning, no memory

Type 'memory' at the prompt to dump what the agent currently holds.

Stage 2: --plan selects the second planner; every turn passes through
policy.check_input and policy.check_output; long-term memory is read
before the turn and written after it.

Signed in like the browser is: it asks for your API key (or reads
AMI_API_KEY) and every tool call runs as that user.
"""

import getpass
import os
import sys
import uuid

from ami import agent_profile as profile
from ami import auth
from ami import plan_execute
from ami import planner
from ami import policy
from ami import store
from ami.agent import respond
from ami.llm import MODEL
from ami.memory import ConversationMemory, LongTermMemory, WorkingMemory


def sign_in():
    """The Principal for the key the user gives, or exit. Same check the
    server makes; the terminal is not a trusted back door."""
    users = auth.UserStore()
    try:
        key = os.environ.get("AMI_API_KEY") or getpass.getpass("API key: ")
    except (EOFError, KeyboardInterrupt):
        sys.exit(1)
    principal = users.authenticate(key.strip())
    if not principal:
        sys.exit("That key was not accepted. Issue one with "
                 "scripts/mint_key.py (see AUTH.md).")
    store.bind_owners(users)
    return principal


def main():
    argv = sys.argv[1:]
    principal = sign_in()
    baseline = "--baseline" in argv
    use_plan = "--plan" in argv
    trace = "--quiet" not in argv

    system = profile.system_prompt()
    if use_plan:
        system += plan_execute.PLANNING_RULES
    elif not baseline:
        system += planner.PLANNING_RULES

    convo = ConversationMemory(system)     # what was said
    work = WorkingMemory()                 # what is known and done
    work.principal = principal             # from the credential, never typed in chat
    work.customer_email = principal.email
    work.session_id = "cli-" + uuid.uuid4().hex[:8]
    longterm = LongTermMemory()            # what we know about this customer
    mode = "baseline" if baseline else ("plan-execute" if use_plan else "ReAct")

    print(f"[{profile.NAME} · {MODEL} · {mode}]  (ctrl-c or 'quit' to exit)\n")
    print(f"signed in as {principal.email}\n")
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
            print("-- long-term memory:")
            print(longterm.recall(work.customer_email, work.session_id)
                  or "   (not a returning customer)")
            print()
            continue

        # policy: input
        text, note = policy.check_input(user)
        work.turn += 1
        convo.add_user(text)
        print()

        if baseline:
            reply = respond(convo.messages(), principal, verbose=trace)
        elif use_plan:
            reply = plan_execute.plan_execute(convo, work, trace=trace,
                                              longterm=longterm, extra=note)
        else:
            reply = planner.react(convo, work, trace=trace,
                                  longterm=longterm, extra=note)

        # policy: output, then remember the customer
        reply = policy.check_output(
            reply, work, text,
            context=longterm.recall(work.customer_email, work.session_id) or "")
        longterm.remember(work, session_id=work.session_id)

        print(f"{profile.NAME}: {reply}\n")


if __name__ == "__main__":
    main()
