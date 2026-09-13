"""Browser UI for the agent, using only Python's built-in http.server.

    python3 web.py        then open http://localhost:8000

No Flask, no install. The point of the page is not the chat box — it is
the right-hand panel, where you can watch the ReAct trace and both kinds
of memory change as you talk.

One session per browser, kept in a cookie and saved to state/sessions.json,
so a reload or a restart does not lose the conversation.

The page markup lives in ui/chat.html.
"""

import json
import os
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime

from ami import agent_profile as profile
from ami import dashboard
from ami import observe
from ami import planner
from ami.llm import MODEL
from ami.memory import ConversationMemory, WorkingMemory
from ami import ROOT          # the stage folder

# Both stages ship the same server, so PORT is overridable to run them
# side by side: PORT=8002 python3 web.py
PORT = int(os.environ.get("PORT", 8000))
SYSTEM = profile.system_prompt() + planner.PLANNING_RULES

# One session PER BROWSER, keyed by a cookie. The earlier version kept a
# single global conversation, which meant two people on the same server —
# or the same person after a reload — silently shared one customer's
# orders, cancellations and escalations. Memory has to be scoped to whose
# memory it is.
#
# And it has to SURVIVE. An in-memory dict means every restart silently
# wipes every conversation while the customer's browser still shows the
# transcript — the agent then truthfully says it remembers nothing. So
# sessions are written to disk after each turn and reloaded on boot.
SESSIONS = {}
SESSIONS_FILE = ROOT / "state" / "sessions.json"
FEEDBACK_FILE = ROOT / "state" / "feedback.jsonl"


def new_session():
    return {"convo": ConversationMemory(SYSTEM), "work": WorkingMemory()}


def save_sessions():
    try:
        SESSIONS_FILE.parent.mkdir(exist_ok=True)
        SESSIONS_FILE.write_text(json.dumps({
            sid: {"convo": s["convo"].to_dict(), "work": s["work"].to_dict()}
            for sid, s in SESSIONS.items()
        }))
    except OSError:
        pass                      # never let persistence break a reply


def load_sessions():
    try:
        raw = json.loads(SESSIONS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return
    for sid, d in raw.items():
        SESSIONS[sid] = {
            "convo": ConversationMemory.from_dict(SYSTEM, d["convo"]),
            "work": WorkingMemory.from_dict(d["work"]),
        }
    print(f"restored {len(SESSIONS)} session(s) from {SESSIONS_FILE.name}", flush=True)


load_sessions()


def save_feedback(golden_row_id, original_response, corrected_response, reason):
    """Log feedback entry to state/feedback.jsonl."""
    try:
        FEEDBACK_FILE.parent.mkdir(exist_ok=True)
        feedback_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "golden_row_id": golden_row_id,
            "original_response": original_response,
            "corrected_response": corrected_response,
            "reason": reason
        }
        with open(FEEDBACK_FILE, "a") as f:
            f.write(json.dumps(feedback_entry) + "\n")
    except OSError:
        pass                      # never let persistence break a reply


def state(session):
    """Everything the page needs to redraw its panels."""
    work = session["work"]
    return {
        "working": work.brief() or "(empty — nothing established yet)",
        "messages": len(session["convo"]),
        "orders": len(work.orders),
        # Customer-facing: what the agent actually DID on their account.
        "actions": work.actions,
        "escalation": work.escalation,
    }


class Handler(BaseHTTPRequestHandler):

    def _session(self):
        """Find this browser's session, minting one (and a cookie) if new."""
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        sid = cookie["sid"].value if "sid" in cookie else None
        # A cookie we do not recognise means the session is GONE, not new.
        # Say so, rather than quietly handing back an empty conversation.
        self.stale = bool(sid) and sid not in SESSIONS
        if sid not in SESSIONS:
            sid = uuid.uuid4().hex
            SESSIONS[sid] = new_session()
            self._set_cookie = sid
        return sid, SESSIONS[sid]

    def _send(self, body, content_type="application/json"):
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        if getattr(self, "_set_cookie", None):
            self.send_header("Set-Cookie",
                             f"sid={self._set_cookie}; Path=/; SameSite=Lax")
            self._set_cookie = None
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._session()                      # mint the cookie on first load
            self._send(PAGE, "text/html")
        elif self.path == "/logs":
            self._send(dashboard.PAGE, "text/html")
        elif self.path == "/logs.json":
            self._send(json.dumps({"stats": observe.stats(),
                                   "events": observe.recent(120)}))
        elif self.path == "/trace.jsonl":
            try:
                self._send(observe.LOGFILE.read_text(), "text/plain")
            except OSError:
                self._send("", "text/plain")
        elif self.path == "/state":
            _, session = self._session()
            self._send(json.dumps({**state(session), "stale": self.stale}))
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or "{}")
        sid, session = self._session()

        if self.path == "/reset":
            SESSIONS[sid] = new_session()
            save_sessions()
            self._send(json.dumps({"ok": True, **state(SESSIONS[sid])}))
            return

        if self.path == "/feedback":
            golden_row_id = data.get("golden_row_id") or None
            original_response = data.get("original_response", "").strip()
            corrected_response = data.get("corrected_response", "").strip()
            reason = data.get("reason", "").strip()

            if original_response and corrected_response:
                save_feedback(golden_row_id, original_response, corrected_response, reason)
                self._send(json.dumps({"ok": True, "message": "Feedback saved"}))
            else:
                self._send(json.dumps({"ok": False, "message": "Missing required fields"}))
            return

        if self.path != "/chat":
            self.send_error(404)
            return

        text = (data.get("message") or "").strip()
        if not text:
            self._send(json.dumps({"reply": "", "steps": [], **state(session)}))
            return

        convo, work = session["convo"], session["work"]
        before = len(work.actions)          # so we can tell the customer what changed
        # Tag this thread so every model call and tool call underneath is
        # attributed to this customer and this turn.
        observe.context(session=sid)
        turn_id = observe.new_turn()

        convo.add_user(text)

        steps = []
        with observe.timer() as t:
            try:
                reply = planner.react(convo, work, trace=False, steps=steps)
            except Exception as e:                  # keep the page alive
                reply = f"Something went wrong: {type(e).__name__}: {e}"

        observe.log("turn", user=text, steps=len(steps), ms=t.ms,
                    actions=len(work.actions) - before,
                    cost=observe.turn_cost(turn_id))
        save_sessions()                  # survive a restart

        self._send(json.dumps({"reply": reply, "steps": steps,
                               "new_actions": work.actions[before:],
                               **state(session)}))

    def log_message(self, *args):
        pass                                        # quiet the request spam


PAGE = (ROOT / "ui" / "chat.html").read_text()

PAGE = (PAGE.replace("__MODEL__", MODEL)
            .replace("__GREETING__", json.dumps(profile.GREETING)))


if __name__ == "__main__":
    print(f"Ami is running at http://localhost:{PORT}   (ctrl-c to stop)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
