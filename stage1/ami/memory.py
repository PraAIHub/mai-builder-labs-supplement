"""Element 2 of the agent: MEMORY.

There are two kinds, and mixing them up is the usual beginner mistake.

CONVERSATION MEMORY — what was SAID.
    The transcript. Grows every turn, gets sent to the model on every call,
    and is the thing that makes turn 5 understand the word "it". Its job is
    recall, and its enemy is length.

WORKING MEMORY — what is KNOWN and DONE.
    The agent's scratchpad for the current task: facts confirmed by tools,
    actions already taken, the goal it is chasing. It is small, structured,
    and rewritten as the agent learns. Its job is not to remember words but
    to stop the agent repeating itself.

You can see the difference in one question: "did I already escalate this?"
The transcript can answer it only by re-reading everything. Working memory
answers it by looking at one field.
"""

import json


class ConversationMemory:
    """The dialogue transcript, in the shape the model expects."""

    def __init__(self, system_prompt, max_turns=40):
        self.system = system_prompt
        self.history = []          # everything after the system message
        self.max_turns = max_turns

    def add_user(self, text):
        self.history.append({"role": "user", "content": text})

    def add_assistant(self, message):
        """Takes the raw model message (it may carry tool_calls)."""
        self.history.append(message)

    def add_observation(self, tool_call_id, result):
        self.history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(result),
        })

    def messages(self, extra_system=None):
        """What we actually send. `extra_system` is where working memory rides in."""
        head = [{"role": "system", "content": self.system}]
        if extra_system:
            head.append({"role": "system", "content": extra_system})
        return head + self._trimmed()

    def _trimmed(self):
        """Keep the transcript from growing forever.

        We trim from the front, but never leave a 'tool' message stranded
        without the assistant message that requested it — the API rejects that.
        """
        if len(self.history) <= self.max_turns:
            return self.history
        cut = len(self.history) - self.max_turns
        while cut < len(self.history) and self.history[cut].get("role") == "tool":
            cut += 1
        return self.history[cut:]

    def __len__(self):
        return len(self.history)

    # -- persistence ------------------------------------------------------

    def to_dict(self):
        return {"history": self.history, "max_turns": self.max_turns}

    @classmethod
    def from_dict(cls, system_prompt, data):
        m = cls(system_prompt, max_turns=data.get("max_turns", 40))
        m.history = data.get("history", [])
        return m


class WorkingMemory:
    """What the agent has established during this task.

    Updated from tool observations, never from the customer's claims —
    a customer saying "my order shipped" is not a fact, a tool saying it is.
    """

    def __init__(self):
        self.customer_email = None
        self.orders = {}        # order_id -> what we looked up
        self.actions = []       # things that actually changed something
        self.failures = []      # what we tried that was refused, and why
        self.escalation = None  # ticket number, once we have one

    # -- writing ----------------------------------------------------------

    def record(self, tool, args, result):
        """Fold one Observation into what we know."""
        if tool == "find_orders" and "orders" in result:
            self.customer_email = args.get("email")
            for o in result["orders"]:
                self.orders.setdefault(o["order_id"], {}).update(o)

        elif tool in ("get_order", "track_package") and "error" not in result:
            oid = args.get("order_id")
            if oid:
                self.orders.setdefault(oid, {}).update(
                    {k: v for k, v in result.items() if k != "events"})

        if "error" in result:
            # A retryable error is the agent's own slip, not a decision about
            # the customer. Logging it would poison working memory with a
            # refusal that never happened.
            if not result.get("retry"):
                self.failures.append(f"{tool}({args.get('order_id', '')}) "
                                     f"refused: {result['error']}")
            return

        if tool == "cancel_order":
            self.actions.append(f"Cancelled {result['order_id']}, "
                                f"${result['refund_amount']} refunded")
            self.orders.setdefault(result["order_id"], {})["status"] = "cancelled"
        elif tool == "start_return":
            self.actions.append(f"Return started for {result['order_id']}, "
                                f"{result['rma']}, ${result['refund_amount']}")
            self.orders.setdefault(result["order_id"], {})["status"] = "return started"
        elif tool == "escalate":
            self.escalation = result["ticket"]
            self.actions.append(f"Escalated to a human, ticket {result['ticket']}")

    # -- reading ----------------------------------------------------------

    def brief(self):
        """Working memory as a short note the model reads before every step."""
        if not any([self.customer_email, self.orders, self.actions,
                    self.failures, self.escalation]):
            return None

        lines = ["WHAT YOU ALREADY KNOW (do not look these up again):"]
        if self.customer_email:
            lines.append(f"- Customer email: {self.customer_email}")
        for oid, o in self.orders.items():
            bits = [f"{oid}: {o.get('item', 'unknown item')}",
                    f"status={o.get('status', '?')}"]
            if o.get("eta"):
                bits.append(f"eta={o['eta']}")
            if o.get("delivered_on"):
                bits.append(f"delivered={o['delivered_on']}")
            lines.append("- " + ", ".join(bits))
        if self.actions:
            lines.append("ALREADY DONE (never do these twice):")
            lines += [f"- {a}" for a in self.actions]
        if self.failures:
            lines.append("ALREADY REFUSED (do not retry):")
            lines += [f"- {f}" for f in self.failures]
        if self.escalation:
            lines.append(f"NOTE: this conversation is already escalated as "
                         f"{self.escalation}. Refer to that ticket rather than "
                         f"escalating again.")
        return "\n".join(lines)

    # -- persistence ------------------------------------------------------

    def to_dict(self):
        return {"customer_email": self.customer_email, "orders": self.orders,
                "actions": self.actions, "failures": self.failures,
                "escalation": self.escalation}

    @classmethod
    def from_dict(cls, data):
        w = cls()
        w.customer_email = data.get("customer_email")
        w.orders = data.get("orders", {})
        w.actions = data.get("actions", [])
        w.failures = data.get("failures", [])
        w.escalation = data.get("escalation")
        return w

    def __repr__(self):
        return (f"<WorkingMemory orders={len(self.orders)} "
                f"actions={len(self.actions)} escalation={self.escalation}>")

