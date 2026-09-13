---
name: test-suite
description: Create, extend, run and maintain the project's test suite. Use when asked to add tests, write a pytest suite, add an eval case, check coverage, fix a failing test, or decide whether something belongs in evals.py, golden.json or a unit test.
argument-hint: [create | add <feature> | run | audit]
---

# Test suite creation and management

This project has three layers of testing. Pick the cheapest layer that can
catch the bug, and say which layer you chose and why.

| Layer | File | Costs | Answers |
|---|---|---|---|
| Unit tests | `stage*/tests/test_*.py` (pytest) | nothing | does this function do what its docstring says |
| Behaviour evals | `stage*/evals.py` `CASES` | proxy budget | did the agent DO the right thing (tools, refusals, store) |
| Golden set | `stage*/golden.py` + `golden.json` | proxy budget + judge | did the agent SAY the right thing |

**Rule of thumb.** If it can be asserted without calling the model, it is a
unit test. If it needs the model but the answer is checkable by tool trace
or store state, it is an eval case. Only wording, correctness of the reply,
or groundedness goes into the golden set.

## Budget

The class LLM proxy key (`OPENAI_API_KEY` in `.env`) has a budget shared with
students. Before running anything that calls the model:

1. Prefer `--only <substring>` to run one case, not the table.
2. Run once (`--runs 1`, the default) unless flakiness is the question.
3. Never run `golden.py --runs 3` or both stages back to back as "verification".
4. State the expected number of model calls before running, and the cost
   from `results/*.json` afterwards.

Unit tests have no budget. Run them freely.

## Workflow: `create`

When there is no `tests/` folder yet:

1. Read `ami/__init__.py` for the module list, then each module's docstring.
   Read `evals.py` `CASES` to see which behaviours are already covered.
2. Create `stage<N>/tests/` with `conftest.py` and one `test_<module>.py`
   per deterministic module. Do not test `llm.py` against the real model.
3. Every test file starts with a short docstring saying what behaviour it
   pins and which module it belongs to. Students read tests as documentation.
4. Add `pytest` to `requirements.txt` only if the user agrees. Otherwise note
   it in the test folder's README.
5. Add a `tests/README.md` with the run command and the three-layer table.

Deterministic modules in this project, and what to pin:

- `store.py`: seed data, status transitions, that `cancel_order` on a
  shipped order is refused, that `start_return` needs a delivered order.
- `tools.py`: guardrails live in the tools, not the prompt. Assert that each
  refusal comes back as a refusal, not an exception. Assert the tool schema
  (`_tool`) lists the required arguments.
- `planner.py`: `_schemas_with_thought` adds a required `thought` to every
  tool. Assert it is the LAST property in each schema; the README records
  why that position matters, and a test is what keeps it there.
- `memory.py`: conversation memory trims correctly, working memory keeps
  the last order id, (Stage 2) `LongTermMemory` round-trips through JSON.
- `policy.py` (Stage 2): `check_input` scrubs what it should, `guarded_run`
  blocks an unconfirmed `cancel_order` and passes a confirmed one,
  `check_output` flags the patterns it lists, escalate happens once.
- `knowledge.py`: each `##` section becomes one chunk, chunk count matches
  the docs, metadata carries the category. Mock the embedder or use the
  cached model; never download inside a unit test.
- `pricing.py`: cost arithmetic for a known token count.
- `observe.py`: a trace line is valid JSON with the fields the dashboard reads.

Fixtures to put in `conftest.py`:

- `fresh_store`: reset the fake order database before each test.
- `tmp_state`: point `state/` at a temp directory so tests never touch
  `state/sessions.json` or `state/customers.json`.
- `fake_llm`: a stand-in for `llm.call` that returns a scripted tool call or
  reply, so planner and policy tests can run without the network.

## Workflow: `add <feature>`

1. Find the layer. Ask: can I assert this from the store or the tool trace?
2. Unit test: add to the matching `test_<module>.py`. Name the test after the
   behaviour, e.g. `test_cancel_refuses_shipped_order`.
3. Eval case: append to `CASES` in `evals.py` under the right comment
   heading. Use the smallest set of keys that pins the behaviour. Add a
   one-line comment above it saying what bug or feature it guards.
4. Golden row: add to `golden.json` with `id`, `question`, `reference`,
   `facts`, `source`. Write the reference from the order data and the policy
   doc, not from what the agent currently says. Then run
   `golden.py --audit --only <id>` so the judge is checked on the new row.
5. Stage 2 is a copy of Stage 1. If the feature exists in both, add the
   test in both and keep the files diff-able.

## Workflow: `run`

```
cd stage1 && python3 -m pytest tests -q          # free
cd stage1 && python3 evals.py --only guard        # costs proxy budget
cd stage2 && python3 golden.py --audit --only pol # judge first, then rows
```

Report failures with the exact assertion text in a code block. If an eval
case fails, check `results/eval_results.json` for the tool trace before
blaming the case; the model is not deterministic and one failure in one run
is a signal, not a verdict.

## Workflow: `audit`

Review the suite itself, without running the model:

- Every guardrail in `tools.py` and `policy.py` has at least one unit test
  and one eval case that exercises the refusal path.
- Every `CASES` entry has a comment saying what it guards.
- Every golden row's `facts` strings actually appear in its `reference`.
- No test reads or writes the real `state/` or `.cache/` directories.
- No test calls the model unless it lives in `evals.py` or `golden.py`.
- Stage 1 and Stage 2 tests differ only where the code differs. Diff them.

Write the audit as a short table: check, status, file:line to fix.

## Style

- Plain `assert`, no assertion helpers. Students should read a test in
  one pass.
- One behaviour per test. If a test needs a paragraph to explain, split it.
- Test names read as sentences: `test_<thing>_<does_what>_<when>`.
- Keep test data small and visible in the test, not in a fixture file,
  unless it is the shared seed store.
