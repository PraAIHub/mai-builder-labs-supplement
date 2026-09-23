"""Element 4 of the agent: ACTION — the tools, and the guardrails around them.

Two ideas to notice here:

1. Every tool returns a plain dict. On failure it returns
   {"error": ...} instead of raising, so the model can read the problem
   and explain it to the customer.

2. The guardrails live in the TOOLS, not in the prompt. A prompt rule is
   a suggestion the model can talk itself out of. A check inside
   cancel_order() is a rule it cannot get around.

Stage 2: cancel_order and start_return declare a `confirmed` flag in
their schema, and their descriptions tell the model to preview first.
The tool functions themselves are unchanged — the policy layer strips
the flag and decides whether the call goes through (policy.guarded_run).
"""

from datetime import date

from ami import desk
from ami import knowledge
from ami import observe
from ami import store

# --------------------------------------------------------------------------
# The tools themselves
# --------------------------------------------------------------------------


def _not_found(order_id):
    """The one answer for an order that is missing AND for one that is not
    the caller's. They must be indistinguishable: a different reply for
    'exists but not yours' would confirm the id to whoever is guessing."""
    return {"error": f"No order found with id {order_id}."}


def find_orders(principal):
    """The signed-in customer's own orders, for when they don't know the
    order number. Takes no email: whose orders these are comes from the
    credential, not from anything the model or the customer typed."""
    hits = [
        {"order_id": o["order_id"], "item": o["item"],
         "status": o["status"], "ordered_on": o["ordered_on"]}
        for o in store.orders_of(principal)
    ]
    if not hits:
        return {"error": "No orders found on your account."}
    return {"orders": hits}


def get_order(principal, order_id):
    """Full detail for one order."""
    order = store.get_owned(order_id, principal)
    if not order:
        return _not_found(order_id)
    return {
        "order_id": order["order_id"],
        "item": order["item"],
        "price": order["price"],
        "status": order["status"],
        "ordered_on": order["ordered_on"],
        "delivered_on": order["delivered_on"],
        "eta": order.get("eta"),
    }


def track_package(principal, order_id):
    """The carrier scan history for an order."""
    order = store.get_owned(order_id, principal)
    if not order:
        return _not_found(order_id)
    if not order["tracking"]:
        return {"error": "No tracking events yet for this order."}
    return {
        "carrier": order["carrier"],
        "eta": order.get("eta"),
        "events": [{"date": d, "detail": t} for d, t in order["tracking"]],
    }


def cancel_order(principal, order_id):
    """Cancel an order — only allowed before it ships. GUARDRAIL."""
    order = store.get_owned(order_id, principal)
    if not order:
        return _not_found(order_id)

    if order["status"] in ("shipped", "delivered"):
        return {
            "error": f"Order {order_id} already {order['status']} and cannot "
                     f"be cancelled. It can be returned instead."
        }
    if order["status"] == "cancelled":
        return {"error": f"Order {order_id} is already cancelled."}

    order["status"] = "cancelled"
    return {
        "cancelled": True,
        "order_id": order["order_id"],
        "refund_amount": order["price"],
        "refund_eta": "3-5 business days to the original payment method",
    }


def start_return(principal, order_id, reason):
    """Open a return — only for delivered orders inside the return window. GUARDRAIL."""
    order = store.get_owned(order_id, principal)
    if not order:
        return _not_found(order_id)

    if order["status"] != "delivered":
        return {
            "error": f"Order {order_id} is '{order['status']}', not delivered "
                     f"yet, so it can't be returned."
        }

    days = (date.today() - date.fromisoformat(order["delivered_on"])).days
    if days > store.RETURN_WINDOW_DAYS:
        return {
            "error": f"Delivered {days} days ago, past the "
                     f"{store.RETURN_WINDOW_DAYS}-day return window. "
                     f"A human agent can review an exception."
        }

    rma = f"RMA-{len(store.RETURNS) + 1001}"
    store.RETURNS[rma] = {"order_id": order["order_id"], "reason": reason,
                          "owner_id": principal.user_id}
    order["status"] = "return started"
    return {
        "rma": rma,
        "order_id": order["order_id"],
        "refund_amount": order["price"],
        "instructions": "Drop off at any UPS Store with the QR code emailed "
                        "to you. Refund issues once we scan the item.",
    }


def search_knowledge(principal, question):
    """Look up what is written down. The RAG tool.

    Everything else here reads the order database. This one reads the
    filing cabinet: the rules a human support agent would have been
    trained on, which the agent can now quote instead of guessing at.

    One argument, on purpose — see knowledge.search() for why the
    obvious second one (a category to search within) was removed.
    """
    hits = knowledge.search(question, k=3)
    return {"passages": [{"source": h["source"], "category": h["category"],
                          "policy": h["heading"], "text": h["text"]}
                         for h in hits]}


def escalate(principal, summary):
    """Hand off to a human. The honest answer when no other tool fits.

    This used to return a fixed ticket number, which meant the promise
    to the customer was fiction. It now opens a real ticket on the
    helpdesk over MCP (see desk.py), and says the number the desk gave
    back. If the desk cannot be reached it returns an error rather than
    a comforting lie — the model can then tell the customer the truth.
    """
    ticket = desk.create_ticket(
        title=summary,
        body="Escalated by Ami, the support agent.\n\n"
             f"What the customer needs:\n{summary}\n",
        customer_email=principal.email,          # the caller, never a shared default
        customer_name=principal.name,
    )
    if "error" in ticket:
        return {"error": f"Could not open a helpdesk ticket: {ticket['error']}"}
    return {
        "escalated": True,
        "ticket": desk.ticket_ref(ticket),      # the number the customer hears
        "ticket_id": ticket.get("id"),          # the integer add_note needs
        "message": "A human agent will email you within 24 hours.",
        "summary": summary,
    }


# --------------------------------------------------------------------------
# Descriptions the model reads to decide which tool to call
# --------------------------------------------------------------------------

def _tool(name, description, properties, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


SCHEMAS = [
    _tool("find_orders",
          "List the signed-in customer's own orders. Use when the customer "
          "does not know their order number. It takes no arguments: whose "
          "orders these are is fixed by who is signed in, and cannot be "
          "changed by asking.",
          {},
          []),

    _tool("get_order",
          "Get the status and details of one order by its order number.",
          {"order_id": {"type": "string",
                        "description": "Order number, e.g. 112-1111111-1111111"}},
          ["order_id"]),

    _tool("track_package",
          "Get carrier tracking events and delivery estimate for an order.",
          {"order_id": {"type": "string", "description": "Order number"}},
          ["order_id"]),

    _tool("cancel_order",
          "Cancel an order that has not shipped yet and refund it. The first "
          "call returns what would happen; ask the customer, then call again "
          "with confirmed=true once they have said yes.",
          {"order_id": {"type": "string", "description": "Order number"},
           "confirmed": {"type": "boolean",
                         "description": "true only after the customer confirmed"}},
          ["order_id"]),

    _tool("start_return",
          "Start a return for a delivered order and issue an RMA number. The "
          "first call returns what would happen; ask the customer, then call "
          "again with confirmed=true once they have said yes.",
          {"order_id": {"type": "string", "description": "Order number"},
           "reason": {"type": "string",
                      "description": "Why the customer is returning it, in their words"},
           "confirmed": {"type": "boolean",
                         "description": "true only after the customer confirmed"}},
          ["order_id", "reason"]),

    _tool("search_knowledge",
          "Look up what is written down, and quote it back rather than "
          "guessing. Covers four kinds of knowledge: what the customer is "
          "entitled to, what you are allowed to do, how to phrase something "
          "difficult, and the law a policy rests on. Use it for any question "
          "about the rules themselves.",
          {"question": {"type": "string",
                        "description": "The question, in plain words"}},
          ["question"]),

    _tool("escalate",
          "Hand the conversation to a human agent. Use when the customer asks "
          "for a human, is very upset, or the request is outside these tools. "
          "This opens a real ticket on the helpdesk and returns its number — "
          "tell the customer the number.",
          {"summary": {"type": "string",
                       "description": "One-line summary of the issue for the human agent"}},
          ["summary"]),
]

REGISTRY = {
    "find_orders": find_orders,
    "get_order": get_order,
    "track_package": track_package,
    "cancel_order": cancel_order,
    "start_return": start_return,
    "search_knowledge": search_knowledge,
    "escalate": escalate,
}


# The only arguments a tool will take from the model. Anything else — an
# `email`, a `user_id`, a `principal` — is refused, not quietly ignored.
_ALLOWED = {s["function"]["name"]: set(s["function"]["parameters"]["properties"])
            for s in SCHEMAS}


def run(name, args, principal):
    """Execute a tool the model asked for. Never raises — errors come back as data.

    `principal` is who is signed in, put here by the server from the
    credential. It is bound to the tool call BELOW the model: the model
    never sees it and cannot supply, replace or widen it.
    """
    with observe.timer() as t:
        result = _dispatch(name, args, principal)
    observe.log("tool", tool=name, args=args, ms=t.ms,
                ok="error" not in result,
                error=result.get("error"),
                retryable=bool(result.get("retry")))
    return result


def _dispatch(name, args, principal):
    fn = REGISTRY.get(name)
    if not fn:
        return {"error": f"No such tool: {name}"}
    if principal is None:
        return {"error": "Not signed in."}          # fail closed, never "everyone"
    stray = set(args) - _ALLOWED[name]
    if stray:
        observe.log("policy", stage="action", rule="unexpected_argument",
                    tool=name, args=sorted(stray))
        return {"error": f"Bad call to {name}: it does not take {sorted(stray)}.",
                "retry": True}
    try:
        return fn(principal, **args)
    except TypeError as e:
        # The agent called its own tool wrongly. That is not a policy
        # refusal — it is a mistake it can fix, so say so explicitly.
        return {"error": f"Bad call to {name}: {e}", "retry": True}
