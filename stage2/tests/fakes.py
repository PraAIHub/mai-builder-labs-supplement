"""Stand-ins for the OpenAI client, so planner tests run without the network.

The planner reads three things from a model response: `choices[0].message`,
the message's `content` and `tool_calls`, and each call's `function.name`
and `function.arguments`. These fakes provide exactly that and nothing more.

    fake_llm.script(
        Reply(tool_calls=[tool_call("get_order", order_id="112-...")]),
        Reply(content="It shipped yesterday."),
    )
"""

import json
from types import SimpleNamespace

from ami.auth import Principal
from ami.memory import WorkingMemory


def _person(who, role="user"):
    return Principal(user_id=f"test-{who}", email=f"{who}@example.com",
                     name=who.title(), role=role)


# Fixed identities for unit tests, so an order id can name its owner. The
# real accounts are built by the `users` fixture (random ids, real store).
RAJ, MEI, ZED, ADMIN = _person("raj"), _person("mei"), _person("zed"), _person("admin", "admin")
OWNER_BY_EMAIL = {p.email: p.user_id for p in (RAJ, MEI, ZED, ADMIN)}


def signed_in(principal=RAJ):
    """Working memory the way the server hands it to the agent: with the
    caller's identity set from the credential."""
    work = WorkingMemory()
    work.principal, work.customer_email = principal, principal.email
    return work


def tool_call(name, **args):
    """One tool call, as the model would request it. `args` includes `thought`."""
    return SimpleNamespace(
        id=f"call_{name}",
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


class Reply:
    """One assistant message: either an answer or a list of tool calls."""

    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=False):
        """What the planner stores in conversation memory."""
        message = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name,
                              "arguments": c.function.arguments}}
                for c in self.tool_calls
            ]
        if exclude_none:
            message = {k: v for k, v in message.items() if v is not None}
        return message


class FakeLLM:
    """Plays back scripted replies, one per call, and remembers every call."""

    def __init__(self):
        self.replies = []
        self.calls = []

    def script(self, *replies):
        self.replies = list(replies)
        return self

    def __call__(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        assert self.replies, "fake_llm was called more times than it was scripted for"
        reply = self.replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=reply)])
