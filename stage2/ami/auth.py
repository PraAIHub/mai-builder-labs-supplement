"""IDENTITY: who is calling. The only module that decides it.

Everything downstream (tools, memory, audit) receives a Principal and
trusts it, so a Principal must only ever be built HERE, from a credential
the server checked. Nothing a client sends — a body field, a tool argument,
a model's guess — may name a user.

    UserStore     the accounts: opaque user_id, email, role, and the HASH of
                  the API key. The key itself is shown once, at issue, and
                  is not recoverable. Lost key -> rotate, never recover.
    Principal     what the rest of the code sees: user_id, email, name, role.

Keys are 32 random bytes, so SHA-256 is enough at rest (there is no weak
password to stretch). Comparison is constant-time. The users file is
re-read when it changes on disk, so `mint_key.py --revoke` takes effect on
a RUNNING server, not at the next restart.
"""

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from ami import ROOT

KEY_PREFIX = "ami_"
ROLES = ("user", "admin")

# Test accounts for scripts/mint_key.py --seed-demo and the test fixtures.
# The emails match the customers in store.py, so the demo orders line up.
DEMO_USERS = [
    ("raj@example.com", "Raj", "user"),
    ("mei@example.com", "Mei", "user"),
    ("zed@example.com", "Zed", "user"),       # no orders: empty must mean empty
    ("admin@example.com", "Admin", "admin"),
]


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. `epoch` bumps when the key is rotated, so a
    session opened with the old key can be told apart from a new one."""
    user_id: str
    email: str
    name: str
    role: str
    epoch: int = 0

    @property
    def is_admin(self):
        return self.role == "admin"


def normalize_email(email):
    return (email or "").strip().lower()


def _hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


def _new_key():
    return KEY_PREFIX + secrets.token_urlsafe(32)


class UserStore:

    def __init__(self, path=None):
        self.path = Path(path) if path else ROOT / "state" / "users.json"
        self._lock = threading.Lock()
        self._stamp = None
        self.users = {}
        self._load()

    # -- reading ----------------------------------------------------------

    def authenticate(self, key):
        """Principal for a valid, unrevoked key, else None. Compares against
        every account with no early exit, so timing does not say which."""
        if not isinstance(key, str) or not key.startswith(KEY_PREFIX) or len(key) > 128:
            return None
        self._refresh()
        digest, found = _hash(key), None
        for rec in list(self.users.values()):
            if hmac.compare_digest(rec["key_hash"], digest) and not rec["revoked_at"]:
                found = rec
        return self._principal(found) if found else None

    def get(self, user_id):
        """The CURRENT principal for an id, or None if gone or revoked. A
        session calls this on every request, so revoking ends it at once."""
        self._refresh()
        rec = self.users.get(user_id)
        return self._principal(rec) if rec and not rec["revoked_at"] else None

    def find(self, email):
        """The active principal for an email — admin tooling only, never a
        request path (an email a caller sends is not an identity)."""
        self._refresh()
        rec = self._active_by_email(normalize_email(email))
        return self._principal(rec) if rec else None

    def listing(self):
        """Every account without its secret, for `mint_key.py --list`."""
        self._refresh()
        return [{k: v for k, v in rec.items() if k != "key_hash"}
                for rec in self.users.values()]

    # -- writing (admin) --------------------------------------------------

    def create(self, email, name, role="user"):
        """New account. Returns (principal, key) — the key is shown ONCE."""
        email = normalize_email(email)
        if "@" not in email:
            raise ValueError(f"not an email address: {email!r}")
        if role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        with self._lock:
            self._refresh()
            if self._active_by_email(email):
                raise ValueError(f"{email} already has an active account")
            key = _new_key()
            rec = {"user_id": uuid.uuid4().hex, "email": email, "name": name,
                   "role": role, "key_hash": _hash(key), "epoch": 0,
                   "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "revoked_at": None}
            self.users[rec["user_id"]] = rec
            self._save()
        return self._principal(rec), key

    def rotate(self, email):
        """Issue a new key; the old one stops working, and so does any session
        opened with it (the epoch moves). Returns the new key, shown once."""
        with self._lock:
            self._refresh()
            rec = self._active_by_email(normalize_email(email))
            if not rec:
                raise KeyError(f"no active account for {email}")
            key = _new_key()
            rec["key_hash"], rec["epoch"] = _hash(key), rec["epoch"] + 1
            self._save()
        return key

    def revoke(self, email):
        with self._lock:
            self._refresh()
            rec = self._active_by_email(normalize_email(email))
            if not rec:
                raise KeyError(f"no active account for {email}")
            rec["revoked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._save()

    # -- internals --------------------------------------------------------

    def _active_by_email(self, email):
        for rec in self.users.values():
            if rec["email"] == email and not rec["revoked_at"]:
                return rec
        return None

    @staticmethod
    def _principal(rec):
        return Principal(rec["user_id"], rec["email"], rec["name"],
                         rec["role"], rec["epoch"])

    def _stat(self):
        # What "the file changed" means. mtime and size alone are not enough:
        # a rotate rewrites the same number of bytes, and on a coarse-clock
        # filesystem it can land in the same tick as the write before it — the
        # running server would miss it and keep honouring the old key's
        # sessions. Every save is an atomic replace, so it also gets a new
        # inode; together these do not collide in practice.
        try:
            st = self.path.stat()
            return (st.st_mtime_ns, st.st_ctime_ns, st.st_size, st.st_ino)
        except FileNotFoundError:
            return None

    def _refresh(self):
        if self._stat() != self._stamp:
            self._load()

    def _load(self):
        # A missing file is a fresh install. A file that exists but will not
        # parse is NOT — carrying on with no users and saving over it would
        # silently wipe every account, so let that raise.
        self._stamp = self._stat()
        self.users = json.loads(self.path.read_text()) if self._stamp else {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            os.fchmod(f.fileno(), 0o600)             # even if tmp pre-existed
            json.dump(self.users, f, indent=1)
        os.replace(tmp, self.path)                   # atomic: no torn file
        self._stamp = self._stat()


class SessionManager:
    """Log in once with the API key; carry a short-lived token after that.

    The long-lived key travels on exactly one route (login). Every other
    request carries the token, so the key is exposed once per session and
    the token — random, server-side, revocable — is what an eavesdropper
    or a leaked log could get. Tokens are held only as hashes, expire on
    idle and on age, and die the moment the account is revoked or its key
    rotated (resolve() re-checks the user store on every request).

    Memory only, on purpose: a restart logs everyone out.
    """

    IDLE = 30 * 60
    ABSOLUTE = 8 * 60 * 60

    def __init__(self, users, idle=IDLE, absolute=ABSOLUTE, clock=time.monotonic):
        self.users, self.idle, self.absolute, self.clock = users, idle, absolute, clock
        self._sessions = {}                  # sha256(token) -> user_id, epoch, start, last
        self._lock = threading.Lock()

    def login(self, key):
        """(token, principal) for a valid key, else None."""
        principal = self.users.authenticate(key)
        if not principal:
            return None
        token, now = secrets.token_urlsafe(32), self.clock()
        with self._lock:
            self._sweep(now)
            self._sessions[_hash(token)] = {"user_id": principal.user_id,
                                            "epoch": principal.epoch,
                                            "start": now, "last": now}
        return token, principal

    def resolve(self, token):
        """The principal a token belongs to right now, else None. A token is
        never a way to NAME a user — only to find the one it was issued to."""
        if not isinstance(token, str) or not token or len(token) > 128:
            return None
        digest, now = _hash(token), self.clock()
        with self._lock:
            s = self._sessions.get(digest)
            if not s:
                return None
            principal = self.users.get(s["user_id"])          # None if revoked
            if (now - s["start"] > self.absolute or now - s["last"] > self.idle
                    or not principal or principal.epoch != s["epoch"]):
                del self._sessions[digest]
                return None
            s["last"] = now
            return principal

    def logout(self, token):
        if isinstance(token, str):
            with self._lock:
                self._sessions.pop(_hash(token), None)

    def _sweep(self, now):
        for d in [d for d, s in self._sessions.items()
                  if now - s["start"] > self.absolute or now - s["last"] > self.idle]:
            del self._sessions[d]
