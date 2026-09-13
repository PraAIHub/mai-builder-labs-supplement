# Stage 1: Unit Tests

## Run the tests

```bash
cd stage1
python3 -m pytest tests -q
```

**Note:** pytest must be installed. It is not in `requirements.txt` to keep the project dependencies minimal. If you don't have pytest, install it with:

```bash
pip install pytest
```

## Test coverage by layer

Each test guards against specific bugs or missing features. Tests are organized by module and layer:

| Layer | File | What it pins |
|---|---|---|
| Unit | `test_store.py` | Seed data, status transitions (delivered → return, shipped ↛ cancel), guardrail refusals return dicts not exceptions |
| Unit | `test_tools.py` | Schema required args, tool guardrails (cancel_order refuses shipped/delivered, start_return refuses non-delivered and past-window), tools never raise |
| Unit | `test_memory.py` | ConversationMemory never splits tool/observation pair when trimming, WorkingMemory records facts from tool results and can brief(), both round-trip JSON |
| Unit | `test_planner.py` | `_schemas_with_thought()` adds `thought` as LAST property in each schema, ReAct loop processes tool calls and observations |
| Unit | `test_pricing.py` | rates() finds model row, cost() calculates dollars for known tokens, usd() formats amounts |
| Unit | `test_observe.py` | Events are valid JSON with required fields (seq, ts, kind, session, turn), stats() aggregates correctly, timer works |
| Unit | `test_knowledge.py` | _chunks() splits by `##` sections, chunk count ≈ 48, metadata carries category, chunk IDs unique |
| Eval | `evals.py` CASES | Agent chose the right tool, refused the right things, store changed as expected |
| Golden | `golden.py` + `golden.json` | Agent said the right thing (graded by LLM judge) |

## Style

- Plain `assert`, one behaviour per test
- Test names read as sentences: `test_<thing>_<does_what>_<when>`
- Small, visible test data in the test itself, not loaded from files
- Docstring at top of each file saying what it pins
- Students read these tests as documentation

## Fixtures

All tests use pytest fixtures defined in `conftest.py`:

- **`fresh_store`**: Resets the fake order database before each test, so tests never interfere
- **`tmp_state`**: Points `state/` at a temp directory so tests never read/write real disk files
- **`fake_llm`**: A scripted stand-in for `llm.complete()` so the planner tests run without the network; the `Reply` and `tool_call` helpers it plays back are in `fakes.py`

`tmp_state` is always on: no test can reach the real `state/` or `.cache/` folders.

## Guardrails audit

Every guardrail has a test. A guardrail is a check inside a tool that returns `{"error": ...}` instead of letting a bad call through.

- `test_store.py::TestCancelGuardrail` → cancel_order refuses shipped/delivered
- `test_store.py::TestReturnGuardrail` → start_return refuses non-delivered and past-window
- `test_tools.py::TestFindOrders` → unknown email returns error
- `test_tools.py::TestGetOrder` → unknown order returns error
- `test_tools.py::TestTrackPackage` → unknown order returns error

Each guardrail also appears in `evals.py` CASES so the full agent flow is tested too.
