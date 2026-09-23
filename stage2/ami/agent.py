"""The agent loop: model -> tool -> model -> ... -> answer.

The model can't run code. It can only *ask* for a tool by name. So the
loop is always the same four steps:

    1. send the conversation (plus the tool menu) to the model
    2. if it replied with text, we're done
    3. if it asked for tools, run them and append the results
    4. go back to 1 so it can use what it learned
"""

import json

from ami import tools
from ami.llm import MODEL, complete

MAX_STEPS = 6   # stop a runaway loop from calling tools forever


def respond(messages, principal, verbose=True):
    """Advance the conversation until the model produces a reply for the user.
    `principal` is who is signed in; the tools bind it, the model never sees it."""
    for _ in range(MAX_STEPS):
        response = complete(messages, tools=tools.SCHEMAS)
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        # No tool requested: this is the answer.
        if not message.tool_calls:
            return message.content

        # Otherwise run each tool it asked for and feed the results back.
        for call in message.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            result = tools.run(name, args, principal)
            if verbose:
                print(f"   [tool] {name}({args}) -> {result}")

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            })

    return ("I'm having trouble completing that. Let me get a human agent "
            "to take a look.")
