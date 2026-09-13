"""Fixtures shared by every test in this folder.

A unit test here never calls the model, never downloads anything, and never
touches the real state/ or .cache/ folders:

    fresh_store   the fake order database, restored around each test
    tmp_state     state/ and .cache/ redirected to a temp folder (always on)
    fake_llm      a scripted stand-in for llm.complete (see fakes.py)
"""

import sys

import pytest

from ami import observe, store
from fakes import FakeLLM


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
    observe.EVENTS.clear()
    monkeypatch.setattr("ami.observe.SEQ", 0)
    return tmp_path


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace llm.complete everywhere it was imported with a scripted fake."""
    fake = FakeLLM()
    for name, module in list(sys.modules.items()):
        if name == "ami.llm" or (name.startswith("ami.") and hasattr(module, "complete")):
            monkeypatch.setattr(module, "complete", fake)
    return fake
