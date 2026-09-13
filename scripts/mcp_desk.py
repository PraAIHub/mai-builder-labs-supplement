"""Talk to the class desk MCP server with the key you already have.

The lab's .env holds OPENAI_API_KEY for the class LLM proxy. The desk MCP
server at /desk/mcp takes that same key as a bearer token, so there is
nothing extra to mint.

    python3 scripts/mcp_desk.py list
    python3 scripts/mcp_desk.py call <tool> '{"arg": "value"}'

Three drifts from older mcp releases, all of which the short version of
this snippet trips over: the transport is `streamable_http_client` (not
`streamablehttp_client`), it yields two streams rather than three, and it
takes no `headers=` — auth belongs on an httpx client you pass in. The
wire types are snake_case now too (`input_schema`, `is_error`).

Why this is a script and not part of ami/tools.py: the tools there are
synchronous, return plain dicts, and the policy layer keys off their
names. MCP tools are async and remote, and their descriptions come from
someone else's server. Discovery first, wiring second.
"""

import asyncio
import json
import os
import sys

import httpx2
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DESK_URL = os.environ.get("MCP_DESK_URL",
                          "https://learn.modernaipro.com/desk/mcp")

# 30s everywhere except reads: an MCP server may hold the stream open.
TIMEOUT = httpx2.Timeout(30.0, read=300.0)


def _key():
    load_dotenv()
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("MAI_API_KEY")
    if not key:
        sys.exit("No OPENAI_API_KEY in .env — mint one at "
                 "https://study.modernaipro.com/practice")
    return key


async def _session(fn):
    """One connection, one initialized session, handed to fn."""
    headers = {"Authorization": f"Bearer {_key()}"}
    async with httpx2.AsyncClient(headers=headers, timeout=TIMEOUT) as http:
        async with streamable_http_client(DESK_URL, http_client=http) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                return await fn(s)


def cmd_list():
    tools = asyncio.run(_session(lambda s: s.list_tools())).tools
    if not tools:
        print("Server exposes no tools.")
    for t in tools:
        required = (t.input_schema or {}).get("required", [])
        print(f"{t.name}({', '.join(required)})")
        if t.description:
            print(f"    {t.description.strip().splitlines()[0]}")


def cmd_call(name, raw_args):
    args = json.loads(raw_args) if raw_args else {}
    result = asyncio.run(_session(lambda s: s.call_tool(name, args)))
    if result.is_error:
        print("ERROR", file=sys.stderr)
    for block in result.content:
        print(getattr(block, "text", block))


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("list", "call"):
        sys.exit(__doc__)
    if sys.argv[1] == "list":
        cmd_list()
    else:
        cmd_call(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
