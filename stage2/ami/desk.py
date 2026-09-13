"""The escalation path, on someone else's server — over MCP.

escalate() used to return a hardcoded ticket number: it promised the
customer a human would follow up, then dropped the summary on the floor.
The class helpdesk is a real MCP server, and the key already in .env
opens it, so the promise can become a ticket somebody can read.

Two things worth noticing:

1. Every other tool in this package is a synchronous function returning
   a plain dict. MCP is async and remote. Rather than make the whole
   agent async for one remote call, each call here opens a session, does
   one round trip, and closes it. A connection per escalation is cheap,
   because escalations are rare — and it keeps tools.py's contract.

2. Only the calls we want are wrapped, by hand. The server also
   advertises its own tool list, and handing that list straight to the
   model would be less code — but then a server we do not control would
   be writing our agent's tool descriptions, which is exactly the
   injection seam the rest of this course keeps closing. The wrapper is
   the guardrail.
"""

import asyncio
import json
import os

import httpx2
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from ami import observe

load_dotenv()

URL = os.environ.get("MCP_DESK_URL", "https://learn.modernaipro.com/desk/mcp")

# A customer is waiting on the other end of this call, so the read
# timeout is seconds rather than the SDK's default five minutes.
TIMEOUT = httpx2.Timeout(10.0, read=30.0)


# --------------------------------------------------------------------------
# The four calls, as plain functions
# --------------------------------------------------------------------------

def create_ticket(title, body, customer_email=None, priority="normal"):
    """Open a ticket for a human. Returns the ticket, or {"error": ...}."""
    args = {"title": title[:200], "body": body[:8000], "priority": priority}
    if customer_email:
        args["customer_email"] = customer_email
    return _call("create_ticket", args)


def add_note(ticket_id, body):
    """Append an internal note. Notes are append-only on the server."""
    return _call("add_note", {"ticket_id": int(ticket_id), "body": body[:8000]})


def get_ticket(ticket_id):
    """Read one ticket in full, with its notes."""
    return _call("get_ticket", {"ticket_id": int(ticket_id)})


def search_tickets(query=""):
    """Search our own queue — used before opening a duplicate."""
    return _call("search_tickets", {"query": query} if query else {})


def ticket_ref(ticket):
    """The label to say out loud, from whatever key the desk used for it."""
    for key in ("number", "ticket_number", "ref", "reference"):
        if ticket.get(key):
            return str(ticket[key])
    for key in ("id", "ticket_id"):
        if ticket.get(key):
            return f"#{ticket[key]}"
    return "(no reference returned)"


# --------------------------------------------------------------------------
# One round trip
# --------------------------------------------------------------------------

def _call(name, args):
    """Call one desk tool. Never raises — failures come back as data."""
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("MAI_API_KEY")
    if not key:
        return {"error": "No OPENAI_API_KEY in .env, so the desk is unreachable."}

    with observe.timer() as t:
        try:
            payload = asyncio.run(_round_trip(name, args, key))
        except Exception as e:            # network, auth, protocol — all data
            payload = {"error": f"Desk unreachable: {type(e).__name__}: {e}"}

    observe.log("mcp", tool=name, args=args, ms=t.ms,
                ok="error" not in payload, error=payload.get("error"))
    return payload


async def _round_trip(name, args, key):
    # The transport takes no headers of its own: auth belongs to the HTTP
    # client you hand it, which is also what would carry a refreshing
    # token if the desk ever wanted OAuth instead of a bearer key.
    headers = {"Authorization": f"Bearer {key}"}
    async with httpx2.AsyncClient(headers=headers, timeout=TIMEOUT) as http:
        async with streamable_http_client(URL, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return _unwrap(await session.call_tool(name, args), name)


def _unwrap(result, name):
    """An MCP result into the plain dict the rest of the agent expects."""
    if result.structured_content is not None:
        data = result.structured_content
    else:
        text = "".join(getattr(b, "text", "") for b in result.content)
        try:
            data = json.loads(text)
        except ValueError:
            data = {"text": text}

    # A tool that fails reports it inside the result, not as a protocol
    # error, so that the model can read the reason and recover.
    if result.is_error:
        return {"error": f"{name} refused: {data}"}
    return data if isinstance(data, dict) else {"result": data}
