"""Browser UI for the agent, using only Python's built-in http.server.

    python3 web.py        then open http://localhost:8000

No Flask, no install. The point of the page is not the chat box — it is
the right-hand panel, where you can watch the ReAct trace and both kinds
of memory change as you talk.

One session per browser, kept in a cookie and saved to state/sessions.json,
so a reload or a restart does not lose the conversation.
"""

import json
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ami import agent_profile as profile
from ami import dashboard
from ami import observe
from ami import planner
from ami.llm import MODEL
from ami.memory import ConversationMemory, WorkingMemory
from ami import ROOT          # the stage folder

PORT = 8000
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


PAGE = r"""<!doctype html>
<meta charset="utf-8">
<title>Ami — Amazon support agent</title>
<style>
  :root { --bg:#0f1115; --panel:#171a21; --line:#2a2f3a; --txt:#e6e8ee;
          --dim:#9aa3b2; --accent:#ff9900; --ok:#4ade80; --err:#f87171; }
  * { box-sizing: border-box; }
  body { margin:0; height:100vh; display:flex; background:var(--bg); color:var(--txt);
         font:14px/1.55 ui-sans-serif, system-ui, -apple-system, sans-serif; }
  .col { display:flex; flex-direction:column; height:100vh; }
  #left { flex:1 1 55%; border-right:1px solid var(--line); }
  #right { flex:1 1 45%; background:var(--panel); }
  header { padding:12px 16px; border-bottom:1px solid var(--line);
           display:flex; align-items:center; gap:10px; }
  header b { color:var(--accent); }
  header span { color:var(--dim); font-size:12px; }
  button { margin-left:auto; background:#222733; color:var(--txt);
           border:1px solid var(--line); border-radius:6px; padding:5px 11px; cursor:pointer; }
  button:hover { border-color:var(--accent); }
  #chat, #panel { flex:1; overflow-y:auto; padding:16px; }
  .msg { margin-bottom:14px; max-width:85%; }
  .msg.you { margin-left:auto; }
  .bubble { padding:9px 13px; border-radius:12px; white-space:pre-wrap; }
  .bubble strong { color:#fff; }
  /* Customer-facing record of what the agent DID. The chat text can be
     re-read or scrolled past; an action on someone's account should not
     depend on them noticing a sentence. */
  #activity { padding:0 16px; }
  #activity:not(:empty) { padding:12px 16px 4px; }
  .entry { display:flex; gap:9px; align-items:flex-start; border-radius:8px;
         padding:9px 12px; margin-bottom:8px; font-size:13px;
         border:1px solid var(--line); background:#12151c; }
  .entry .dot { width:7px; height:7px; border-radius:50%; margin-top:6px; flex:none; }
  .entry.done .dot { background:var(--ok); }
  .entry.esc  { border-color:#5b4a1f; background:#1c1710; }
  .entry.esc .dot { background:var(--accent); }
  .entry.lost { border-color:#5b2a2a; background:#1d1112; }
  .entry.lost .dot { background:#d03b3b; }
  .entry b { color:var(--txt); }
  .entry span { color:var(--dim); }
  .you .bubble { background:#2b3242; }
  .ami .bubble { background:#1d2230; border:1px solid var(--line); }
  .who { font-size:11px; color:var(--dim); margin-bottom:3px; }
  .you .who { text-align:right; }
  form { display:flex; gap:8px; padding:12px 16px; border-top:1px solid var(--line); }
  input { flex:1; background:#12151c; color:var(--txt); border:1px solid var(--line);
          border-radius:8px; padding:10px 12px; font:inherit; }
  input:focus { outline:none; border-color:var(--accent); }
  h3 { margin:0 0 8px; font-size:11px; letter-spacing:.09em; text-transform:uppercase;
       color:var(--dim); }
  .step { border:1px solid var(--line); border-left:3px solid var(--accent);
          border-radius:6px; padding:9px 11px; margin-bottom:9px; background:#12151c; }
  .lbl { font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--accent); }
  .step .lbl.act { color:#7dd3fc; } .step .lbl.obs { color:var(--dim); }
  code, pre { font-family:ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12px; }
  pre { margin:2px 0 8px; white-space:pre-wrap; word-break:break-word; color:var(--dim); }
  pre.ok { color:var(--ok); } pre.err { color:var(--err); }
  #wm { background:#12151c; border:1px solid var(--line); border-radius:6px;
        padding:11px; white-space:pre-wrap; color:var(--dim); font-size:12px; }
  .stats { display:flex; gap:14px; color:var(--dim); font-size:12px; margin:12px 0 6px; }
  .stats b { color:var(--txt); }
  .empty { color:var(--dim); font-style:italic; }
</style>

<div class="col" id="left">
  <header><b>Ami</b><span>__MODEL__ &middot; ReAct</span>
    <button onclick="reset()">Reset session</button></header>
  <div id="activity"></div>
  <div id="chat"></div>
  <form onsubmit="send(event)">
    <input id="box" autocomplete="off" placeholder="Ask about an order…" autofocus>
    <button type="submit" style="margin:0">Send</button>
  </form>
</div>

<div class="col" id="right">
  <header><b>Agent internals</b><span>what it thought, what it remembers</span>
    <a href="/logs" target="_blank" style="margin-left:auto; color:var(--dim);
       text-decoration:none; border:1px solid var(--line); border-radius:6px;
       padding:5px 11px; font-size:12px">Logs &rarr;</a></header>
  <div id="panel">
    <h3>Last turn — ReAct trace</h3>
    <div id="steps" class="empty">No tools called yet.</div>
    <div class="stats">
      <div>conversation: <b id="nmsg">0</b> msgs</div>
      <div>orders known: <b id="nord">0</b></div>
      <div>ticket: <b id="tkt">—</b></div>
    </div>
    <h3>Working memory</h3>
    <div id="wm">(empty)</div>
  </div>
</div>

<script>
const GREETING = __GREETING__;
const $ = id => document.getElementById(id);

// The model writes **bold**. Escape everything first, THEN allow bold —
// never the other way round, or a customer could inject HTML.
function render(text) {
  const safe = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

function bubble(who, text) {
  const d = document.createElement('div');
  d.className = 'msg ' + (who === 'You' ? 'you' : 'ami');
  d.innerHTML = '<div class="who"></div><div class="bubble"></div>';
  d.querySelector('.who').textContent = who;
  d.querySelector('.bubble').innerHTML = render(text);
  $('chat').append(d);
  $('chat').scrollTop = $('chat').scrollHeight;
  return d;
}

// What the agent has done to this customer's account, shown to the customer.
function drawActivity(d) {
  const box = $('activity');
  box.innerHTML = '';
  for (const a of d.actions || []) {
    const esc = a.startsWith('Escalated');
    const el = document.createElement('div');
    el.className = 'entry ' + (esc ? 'esc' : 'done');
    el.innerHTML = '<div class="dot"></div><div></div>';
    const body = el.querySelector('div:last-child');
    if (esc) {
      body.innerHTML = '<b>Handed to a human agent</b> · ticket <b>' +
        (d.escalation || '') + '</b><br><span>They will email you within 24 hours.</span>';
    } else {
      body.innerHTML = '<b>Done</b> <span></span>';
      body.querySelector('span').textContent = '— ' + a;
    }
    box.append(el);
  }
}

function draw(d) {
  drawActivity(d);
  $('nmsg').textContent = d.messages;
  $('nord').textContent = d.orders;
  $('tkt').textContent = d.escalation || '—';
  $('wm').textContent = d.working;

  const box = $('steps');
  box.className = '';
  if (!d.steps || !d.steps.length) {
    box.className = 'empty';
    box.textContent = 'No tools called this turn — answered from memory.';
    return;
  }
  box.innerHTML = '';
  for (const s of d.steps) {
    const err = 'error' in s.observation;
    const el = document.createElement('div');
    el.className = 'step';
    el.innerHTML =
      '<div class="lbl">Thought ' + s.n + '</div><pre class="th"></pre>' +
      '<div class="lbl act">Action</div><pre class="ac"></pre>' +
      '<div class="lbl obs">Observation</div>' +
      '<pre class="ob ' + (err ? 'err' : 'ok') + '"></pre>';
    el.querySelector('.th').textContent = s.thought;
    el.querySelector('.ac').textContent =
      s.tool + '(' + JSON.stringify(s.args).slice(1, -1) + ')';
    el.querySelector('.ob').textContent = JSON.stringify(s.observation, null, 1);
    box.append(el);
  }
}

async function send(e) {
  e.preventDefault();
  const text = $('box').value.trim();
  if (!text) return;
  $('box').value = '';
  bubble('You', text);
  const pending = bubble('Ami', 'thinking…');
  try {
    const r = await fetch('/chat', {method:'POST', body: JSON.stringify({message:text})});
    const d = await r.json();
    pending.querySelector('.bubble').innerHTML = render(d.reply);
    draw(d);
  } catch (err) {
    pending.querySelector('.bubble').textContent = 'Connection failed: ' + err;
  }
}

async function reset() {
  const r = await fetch('/reset', {method:'POST', body:'{}'});
  const d = await r.json();
  $('chat').innerHTML = '';
  bubble('Ami', GREETING);
  draw({...d, steps: []});
}

// A reload must not show a clean slate over a session that is not clean.
// Ask the server what it holds for this browser before drawing anything.
bubble('Ami', GREETING);
fetch('/state').then(r => r.json()).then(d => {
  draw({...d, steps: []});
  if (d.stale) {
    // The server did not recognise this browser's session. Never pretend
    // that is a fresh chat — the customer can still see their old messages.
    const el = document.createElement('div');
    el.className = 'entry lost';
    el.innerHTML = '<div class="dot"></div><div><b>Earlier conversation not found</b>'
                 + '<br><span>The server was restarted, so Ami no longer has this '
                 + 'chat\'s history. Anything above this line is not remembered.</span></div>';
    $('activity').append(el);
  } else if (d.messages > 0) {
    bubble('Ami', '(Picking up an earlier conversation — the summary above '
                + 'shows what has already happened. Press Reset session to start over.)');
  }
});
</script>
"""

PAGE = (PAGE.replace("__MODEL__", MODEL)
            .replace("__GREETING__", json.dumps(profile.GREETING)))


if __name__ == "__main__":
    print(f"Ami is running at http://localhost:{PORT}   (ctrl-c to stop)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
