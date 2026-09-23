"""Browser UI for the agent, using only Python's built-in http.server.

    python3 web.py        then open http://localhost:8001

No Flask, no install. The point of the page is not the chat box — it is
the right-hand panel, where you can watch the ReAct trace and both kinds
of memory change as you talk.

Stage 2: a planner switch in the header (ReAct or plan-and-execute),
the policy layer around every turn, and a long-term memory panel.

Behind auth: the page asks for an API key at the start of a session and
exchanges it ONCE (POST /session) for a short-lived session cookie. Every
other route needs that cookie; the key is accepted on no other route. Who
is calling is decided only in ami/auth.py, from the credential. Nothing in a
request body, query string or tool call can name a user. Each user has one
conversation, keyed by their user_id on the server, saved to
state/sessions.json so a restart does not lose it (it does log you out).

The page markup lives in ui/chat.html.
"""

import json
import os
import threading
import uuid
from collections import defaultdict
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime
from urllib.parse import unquote, urlparse

from ami import agent_profile as profile
from ami import auth
from ami import dashboard
from ami import observe
from ami import plan_execute
from ami import planner
from ami import policy
from ami import store
from ami import tools
from ami.llm import MODEL
from ami.memory import ConversationMemory, LongTermMemory, WorkingMemory
from ami import ROOT          # the stage folder

# Both stages ship the same server, so PORT is overridable to run them
# side by side: PORT=8002 python3 web.py
PORT = int(os.environ.get("PORT", 8001))
SYSTEM = profile.system_prompt()          # planner rules are added per request

# The two planners are interchangeable: same inputs, same outputs. The page
# has a switch so you can run the same conversation through each.
PLANNERS = {
    "react": (planner.react, planner.PLANNING_RULES),
    "plan":  (plan_execute.plan_execute, plan_execute.PLANNING_RULES),
}

LONGTERM = LongTermMemory()               # shared: it is keyed by customer, not session
FEEDBACK_FILE = ROOT / "state" / "feedback.jsonl"

# Who may call, and the sessions they hold. AMI_ENV=prod adds the Secure
# flag to the cookie (TLS terminates at a proxy in front of this server).
USERS = auth.UserStore()
AUTH = auth.SessionManager(USERS)
COOKIE = "ami_session"
SECURE = os.environ.get("AMI_ENV") == "prod"
MAX_BODY = 64 * 1024
ADMIN_ONLY = ("/logs", "/logs.json", "/trace.jsonl")

# One conversation PER USER, keyed by the user_id the server derived from
# their credential. There is no conversation id for a client to send, so
# there is none to guess: a different user's chat is not addressable at all.
#
# It has to SURVIVE. An in-memory dict means every restart silently wipes
# every conversation — the agent then truthfully says it remembers nothing.
# So sessions are written to disk after each turn and reloaded on boot.
SESSIONS = {}
SESSIONS_FILE = ROOT / "state" / "sessions.json"
_LOCKS = defaultdict(threading.Lock)      # one turn at a time per user


def new_session():
    # conv_id names THIS conversation for long-term memory ("earlier chats");
    # it is minted here and never read from a request.
    return {"convo": ConversationMemory(SYSTEM), "work": WorkingMemory(),
            "conv_id": uuid.uuid4().hex}


def save_sessions():
    try:
        SESSIONS_FILE.parent.mkdir(exist_ok=True)
        SESSIONS_FILE.write_text(json.dumps({
            uid: {"convo": s["convo"].to_dict(), "work": s["work"].to_dict(),
                  "conv_id": s["conv_id"]}
            for uid, s in SESSIONS.items()
        }))
    except OSError:
        pass                      # never let persistence break a reply


def load_sessions():
    try:
        raw = json.loads(SESSIONS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return
    dropped = 0
    for uid, d in raw.items():
        if not USERS.get(uid):
            # Saved before sign-in existed (keyed by a browser cookie), or
            # for an account that is gone. Never hand it to anyone.
            dropped += 1
            continue
        SESSIONS[uid] = {
            "convo": ConversationMemory.from_dict(SYSTEM, d["convo"]),
            "work": WorkingMemory.from_dict(d["work"]),
            "conv_id": d.get("conv_id") or uuid.uuid4().hex,
        }
    print(f"restored {len(SESSIONS)} conversation(s) from {SESSIONS_FILE.name}"
          + (f"; discarded {dropped} with no matching account" if dropped else ""),
          flush=True)


load_sessions()
store.bind_owners(USERS)


def save_feedback(user_id, golden_row_id, original_response, corrected_response, reason):
    """Log feedback entry to state/feedback.jsonl."""
    try:
        FEEDBACK_FILE.parent.mkdir(exist_ok=True)
        feedback_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "golden_row_id": golden_row_id,
            "original_response": original_response,
            "corrected_response": corrected_response,
            "reason": reason
        }
        with open(FEEDBACK_FILE, "a") as f:
            f.write(json.dumps(feedback_entry) + "\n")
    except OSError:
        pass                      # never let persistence break a reply


def conversation(principal):
    """This user's conversation, made if new, and stamped with who they are.
    The principal is set fresh from the credential on EVERY request — a
    saved session file cannot carry an identity across."""
    session = SESSIONS.get(principal.user_id)
    if session is None:
        session = SESSIONS[principal.user_id] = new_session()
    session["work"].principal = principal
    session["work"].customer_email = principal.email
    return session


def state(session, principal):
    """Everything the page needs to redraw its panels."""
    work = session["work"]
    return {
        "user": {"email": principal.email, "name": principal.name,
                 "role": principal.role},
        "working": work.brief() or "(empty — nothing established yet)",
        "messages": len(session["convo"]),
        "orders": len(work.orders),
        # Customer-facing: what the agent actually DID on their account.
        "actions": work.actions,
        "escalation": work.escalation,
        "longterm": LONGTERM.recall(work.customer_email, session["conv_id"]),
    }


class Handler(BaseHTTPRequestHandler):

    # -- who is calling ---------------------------------------------------

    def _principal(self):
        """(principal, token) from the session cookie, or (None, None).
        The API key is not accepted here — it works on /session only."""
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie[COOKIE].value if COOKIE in cookie else None
        return AUTH.resolve(token), token

    def _same_origin(self):
        """Refuse a browser request that another site caused. SameSite=Strict
        on the cookie already stops it; this is the second lock."""
        if self.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
            return False
        origin = self.headers.get("Origin")
        return origin is None or urlparse(origin).netloc == self.headers.get("Host")

    def _cookie(self, token, max_age=None):
        parts = [f"{COOKIE}={token}", "Path=/", "HttpOnly", "SameSite=Strict"]
        if SECURE:
            parts.append("Secure")
        if max_age is not None:
            parts.append(f"Max-Age={max_age}")
        return "; ".join(parts)

    # -- responses --------------------------------------------------------

    def _send(self, body, content_type="application/json", status=200, cookie=None):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")     # never cache anyone's data
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        if status == 401:
            self.send_header("WWW-Authenticate", 'Bearer realm="ami"')
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(payload)

    def _deny(self, status, message):
        self._send(json.dumps({"error": message}), status=status)

    # -- routes -----------------------------------------------------------

    def do_GET(self):
        path = urlparse(self.path).path       # the query string is never read
        if path in ("/", "/index.html"):
            self._send(PAGE, "text/html")     # holds no data: it asks for a key
            return

        principal, _ = self._principal()
        if not principal:
            self._deny(401, "sign in required")
            return
        if path in ADMIN_ONLY and not principal.is_admin:
            self._deny(403, "admin only")
            return

        if path == "/logs":
            self._send(dashboard.PAGE, "text/html")
        elif path == "/logs.json":
            self._send(json.dumps({"stats": observe.stats(),
                                   "events": observe.recent(120)}))
        elif path == "/trace.jsonl":
            try:
                self._send(observe.LOGFILE.read_text(), "text/plain")
            except OSError:
                self._send("", "text/plain")
        elif path == "/state":
            self._send(json.dumps(state(conversation(principal), principal)))
        elif path == "/orders":
            # The same code the agent's tools run, so the two cannot disagree
            # about what is yours.
            found = tools.find_orders(principal)
            self._send(json.dumps({"orders": found.get("orders", [])}))
        elif path.startswith("/orders/"):
            order = tools.get_order(principal, unquote(path[len("/orders/"):]))
            if "error" in order:
                # 404 whether the id is unknown or someone else's. A 403 here
                # would confirm the order exists.
                self._deny(404, "not found")
            else:
                self._send(json.dumps(order))
        else:
            self._deny(404, "not found")

    def do_POST(self):
        if not self._same_origin():
            self._deny(403, "cross-origin request refused")
            return
        path = urlparse(self.path).path

        if path == "/session":
            self._login()
            return

        principal, token = self._principal()
        if not principal:
            self._deny(401, "sign in required")
            return

        if path == "/logout":
            AUTH.logout(token)
            self._send(json.dumps({"ok": True}), cookie=self._cookie("", max_age=0))
            return

        # JSON only. A browser cannot send this Content-Type cross-origin
        # without a preflight this server never approves.
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            self._deny(415, "send application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = -1
        if not 0 <= length <= MAX_BODY:
            self._deny(413, "body too large")
            return
        try:
            data = json.loads(self.rfile.read(length) or "{}")
        except json.JSONDecodeError:
            data = None
        if not isinstance(data, dict):
            self._deny(400, "body must be a JSON object")
            return

        # Whatever else is in `data` — user_id, email, scope — is never read.
        with _LOCKS[principal.user_id]:
            self._post(path, data, principal)

    def _login(self):
        header = self.headers.get("Authorization", "")
        key = header[7:].strip() if header[:7].lower() == "bearer " else ""
        got = AUTH.login(key)
        if not got:
            # One answer for unknown, revoked and malformed keys alike.
            self._deny(401, "invalid key")
            return
        token, principal = got
        store.bind_owners(USERS)      # demo orders follow the current accounts
        self._send(json.dumps({"email": principal.email, "name": principal.name,
                               "role": principal.role}),
                   cookie=self._cookie(token))

    def _post(self, path, data, principal):
        session = conversation(principal)

        if path == "/reset":
            SESSIONS[principal.user_id] = new_session()
            save_sessions()
            fresh = conversation(principal)
            self._send(json.dumps({"ok": True, **state(fresh, principal)}))
            return

        if path == "/feedback":
            golden_row_id = data.get("golden_row_id") or None
            original_response = str(data.get("original_response") or "").strip()
            corrected_response = str(data.get("corrected_response") or "").strip()
            reason = str(data.get("reason") or "").strip()

            if original_response and corrected_response:
                save_feedback(principal.user_id, golden_row_id, original_response,
                              corrected_response, reason)
                self._send(json.dumps({"ok": True, "message": "Feedback saved"}))
            else:
                self._send(json.dumps({"ok": False, "message": "Missing required fields"}))
            return

        if path != "/chat":
            self._deny(404, "not found")
            return

        text = data.get("message")
        text = text.strip() if isinstance(text, str) else ""
        if not text:
            self._send(json.dumps({"reply": "", "steps": [],
                                   **state(session, principal)}))
            return

        convo, work = session["convo"], session["work"]
        before = len(work.actions)          # so we can tell the customer what changed
        run, rules = PLANNERS.get(data.get("planner"), PLANNERS["react"])
        convo.system = SYSTEM + rules

        # Tag this thread so every model call and tool call underneath is
        # attributed to this conversation and this turn.
        conv_id = session["conv_id"]
        observe.context(session=conv_id)
        turn_id = observe.new_turn()

        # policy: input — before the text touches memory
        text, note = policy.check_input(text)
        work.turn += 1
        work.session_id = conv_id        # so long-term recall excludes THIS chat
        convo.add_user(text)

        steps = []
        with observe.timer() as t:
            try:
                reply = run(convo, work, trace=False, steps=steps,
                            longterm=LONGTERM, extra=note)
            except Exception as e:                  # keep the page alive
                reply = f"Something went wrong: {type(e).__name__}: {e}"

        # policy: output — before the customer sees it
        reply = policy.check_output(
            reply, work, text,
            context=LONGTERM.recall(work.customer_email, conv_id) or "")

        # long-term memory: remember this customer (identified by sign-in)
        LONGTERM.remember(work, session_id=conv_id)

        observe.log("turn", user=text, steps=len(steps), ms=t.ms,
                    actions=len(work.actions) - before,
                    planner=data.get("planner", "react"),
                    cost=observe.turn_cost(turn_id))
        save_sessions()                  # survive a restart

        self._send(json.dumps({"reply": reply, "steps": steps,
                               "new_actions": work.actions[before:],
                               **state(session, principal)}))

    def log_message(self, *args):
        pass                                        # quiet the request spam


PAGE = (ROOT / "ui" / "chat.html").read_text()

PAGE = (PAGE.replace("__MODEL__", MODEL)
            .replace("__GREETING__", json.dumps(profile.GREETING)))


if __name__ == "__main__":
    if not USERS.listing():
        print("No accounts yet. Issue keys first:  "
              "python3 ../scripts/mint_key.py --seed-demo", flush=True)
    print(f"Ami is running at http://localhost:{PORT}   (ctrl-c to stop)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
