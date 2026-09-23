"""Fixtures shared by every test in this folder.

A unit test here never calls the model, never downloads anything, and never
touches the real state/ or .cache/ folders:

    fresh_store   the fake order database, restored around each test
    bound_orders  seed orders owned by the fixed principals in fakes.py (always on)
    tmp_state     state/ and .cache/ redirected to a temp folder (always on)
    fake_llm      a scripted stand-in for llm.complete (see fakes.py)
    users         the demo accounts in a temp users file, with their keys
    desk_calls    the helpdesk is faked for every test (always on); this records what was sent
"""

import sys

import pytest

from ami import auth, observe, store
from fakes import OWNER_BY_EMAIL, FakeLLM


@pytest.fixture(autouse=True)
def bound_orders():
    """The seed orders belong to the fixed test principals in fakes.py, so a
    unit test can say whose order it is touching. (Tests of the real accounts
    use the `users` fixture, which rebinds them to real ids.)"""
    for order in store.ORDERS.values():
        order["owner_id"] = OWNER_BY_EMAIL.get(order["email"])


@pytest.fixture
def fresh_store():
    """Snapshot the seed orders, hand the test a clean copy, restore after."""
    orders = {k: dict(v) for k, v in store.ORDERS.items()}
    returns = dict(store.RETURNS)
    store.RETURNS.clear()
    yield
    store.ORDERS.clear()
    store.ORDERS.update(orders)
    store.RETURNS.clear()
    store.RETURNS.update(returns)


@pytest.fixture(autouse=True)
def tmp_state(monkeypatch, tmp_path):
    """Point every on-disk path at a temp folder, for every test.

    observe writes state/trace.jsonl, knowledge builds .cache/chroma, and
    (Stage 2) LongTermMemory writes state/customers.json. Each module has
    already imported ROOT, so the paths are patched where they are used.
    """
    monkeypatch.setattr("ami.ROOT", tmp_path)
    monkeypatch.setattr("ami.observe.ROOT", tmp_path)
    monkeypatch.setattr("ami.observe.LOGFILE", tmp_path / "state" / "trace.jsonl")
    monkeypatch.setattr("ami.knowledge.STORE", tmp_path / ".cache" / "chroma")
    monkeypatch.setattr("ami.memory.ROOT", tmp_path, raising=False)
    monkeypatch.setattr("ami.auth.ROOT", tmp_path, raising=False)
    observe.EVENTS.clear()
    monkeypatch.setattr("ami.observe.SEQ", 0)
    return tmp_path


class Users:
    """The demo accounts, minted into a temp users file. `keys` holds the
    plaintext each account was issued — the only place a test can get it,
    exactly as in production, where the store keeps only the hash."""

    def __init__(self, path):
        self.store = auth.UserStore(path)
        self.keys, self.principals = {}, {}
        for email, name, role in auth.DEMO_USERS:
            who = email.split("@")[0]
            self.principals[who], self.keys[who] = self.store.create(email, name, role)


@pytest.fixture
def users(tmp_state):
    return Users(tmp_state / "state" / "users.json")


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace llm.complete everywhere it was imported with a scripted fake."""
    fake = FakeLLM()
    for name, module in list(sys.modules.items()):
        if name == "ami.llm" or (name.startswith("ami.") and hasattr(module, "complete")):
            monkeypatch.setattr(module, "complete", fake)
    return fake


@pytest.fixture(autouse=True)
def desk_calls(monkeypatch):
    """No test opens a real ticket on the class helpdesk. Every call to the
    desk is answered locally and recorded here as (tool, args)."""
    calls = []

    def fake_call(name, args):
        calls.append((name, args))
        return {"id": len(calls), "number": f"TEST-{len(calls)}"}

    monkeypatch.setattr("ami.desk._call", fake_call)
    return calls
