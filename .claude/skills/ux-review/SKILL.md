---
name: ux-review
description: Review the user experience and visual design of a web UI, a terminal interface, or an agent's conversation, and report findings by severity with concrete fixes. Carries the house design style (dark theme, measured contrast, Google Fonts, one framework) and applies it when asked to fix or build UI. Use when asked for a UX review, design review, usability check, accessibility check, restyle, or "does this feel right to a user".
argument-hint: [web | chat | terminal | all] [path] [--fix]
---

# UX design review

A review, not a rewrite. Produce findings first. Apply fixes only when the
user asks, or when they asked for review-and-fix together (`--fix`).

Read `design.md` in this folder before reviewing or touching any visual
surface. It is the house style: palette with measured contrast ratios, the
two Google Fonts and their fallbacks, the type scale, spacing, components
and a starter stylesheet. A review judges the page against it; a fix
brings the page to it.

## Scope

Decide which surfaces are in scope and say so at the top of the report:

| Surface | Where in this project | Who uses it |
|---|---|---|
| `web` | `stage*/ui/chat.html`, `stage*/ui/logs.html`, routes in `web.py` | a student running the agent, and a pretend customer |
| `chat` | the agent's replies, driven by `ami/agent_profile.py`, `knowledge/tone/`, `policy.py` | the customer talking to Ami |
| `terminal` | `main.py` output and its ReAct trace | a student watching the loop |

## Procedure

1. **Use it before judging it.** For `web`, start the server and walk the
   primary path in the browser: open the page, send a message, trigger a
   refusal, trigger a confirmation (Stage 2), open `/logs`, reset. Take
   screenshots at each step. For `chat`, read three transcripts from
   `results/golden_*.json` including one refusal and one escalation. For
   `terminal`, run `main.py` for two turns.
2. **Walk the checklist below** and note every miss with the file and line
   that causes it.
3. **Rank** each finding: Blocker (user cannot complete the task), Major
   (user completes it but is confused or misled), Minor (polish), Nit.
4. **Write the report** in the format at the end. Lead with the three
   findings that matter most.

## Checklist: web UI

Visibility of state
- Is it obvious when the agent is thinking? A pending request needs a
  visible indicator and a disabled send button.
- Does an error from the server reach the screen in plain words, or die in
  the console? Check `fetch` error paths in `ui/chat.html`.
- Is the current planner, session and customer visible where it matters
  (Stage 2 has a planner switch: is the active choice unmistakable)?

Task flow
- Can a first-time student find the primary action within three seconds?
- Does Enter send, and Shift+Enter add a line? Is that discoverable?
- After reset, is it clear the conversation is gone and the store is fresh?
- Confirmation gate (Stage 2): does the UI make the "yes, cancel it" step
  feel deliberate, and is the preview readable before the user confirms?

Reading the output
- Are tool calls and reasoning distinguishable from the customer-facing
  reply? Students need to see the loop; customers must not.
- Does `/logs` answer "what did the last call cost and why" without
  scrolling through raw JSON?
- Long replies: line length, wrapping, monospace only where it earns it.

Accessibility
- Every input has a label. Buttons have text, not just icons.
- Focus is visible and moves to the reply, or the reply is announced
  (`aria-live`) after a send.
- Colour is never the only carrier of meaning (refused vs succeeded).
- Contrast: 7:1 for body text, 4.5:1 for secondary, 3:1 for meaningful
  borders and icons (the measured rules in `design.md`). Check both
  themes if the page supports two.
- The page works at 375px wide and with keyboard only.

Consistency
- Same words for the same thing across chat, logs and the README
  ("session", "planner", "trace").
- Empty states exist: no sessions yet, no logs yet, no results yet.
- `chat.html` and `logs.html` share the same tokens, fonts and component
  styles. Diff their `:root` blocks; any drift is a finding.

## Checklist: visual design

The taste rules live in `design.md`. Check the page against them:

Theme and colour
- Dark theme, near-black surfaces, no pure `#000` or `#fff`. A light
  theme is a finding unless the user asked for one.
- Every colour is a token in `:root`; no hex values inline in rules. Count
  the distinct colours on the page; more than about ten is a finding.
- One accent colour. A second accent needs a reason in the report.
- Status colour appears with a word or icon, never alone.

Contrast, measured
- Run the contrast script from `design.md` on every text/surface pair
  actually used. Body text under 7:1, secondary under 4.5:1, or a border
  or icon that carries meaning under 3:1, is a Major.
- Report the numbers in a table. A colour without a number is unchecked.

Type
- At most two font families: one reading face and one monospace, both
  from Google Fonts with a fallback stack and `display=swap`. A system
  font with no Google Font is a Minor; three families is a Major.
- Sizes and line heights come from the scale in `design.md`. Body text
  under 13 px is a Major; 16 px minimum for what a customer reads.
- Weights 400, 500, 600 only. Uppercase labels tracked, small, and dim.

Layout and shape
- Spacing on the 4/8/12/16/24/32 scale. Eyeball, then read the CSS.
- One radius across the page, one border weight, no shadows on dark.
- Reading width capped; chat bubbles capped; nothing stretched full width
  on a wide screen.

Framework
- Exactly one styling approach per page. Plain CSS with tokens in this
  project. A utility framework, a CSS-in-JS library or a component kit
  added alongside is a Major, and mixing two frameworks is a Blocker.
- No CDN stylesheet or script that the page does not visibly use.

Motion
- Transitions 120 to 200 ms, on hover and focus only. Entrance
  animations, spinners that bounce, or anything over 300 ms is a Minor.
- `prefers-reduced-motion` respected if there is any motion at all.

## Workflow: `--fix`

When asked to fix or build rather than only review:

1. Start from the starter stylesheet in `design.md`. Replace the page's
   `:root` and base rules with it; keep the page's own layout rules.
2. Add the Google Fonts `<link>` tags, with `preconnect`, once, in `<head>`.
3. Move every inline hex value to a token. Add a token only if none fits;
   name it for its role (`--panel-2`), never its colour (`--dark-grey`).
4. Re-run the contrast script on the final pairs and paste the table into
   the report.
5. Take a before and after screenshot at 1280 px and at 375 px wide.
6. Do the same to every sibling page (`logs.html` when you touch
   `chat.html`, Stage 2 when you touch Stage 1) so the pages stay
   diff-able. Say in the report which files changed.

## Checklist: agent conversation

- First reply sets expectations: who Ami is, what it can do, in one line.
- A refusal says what it cannot do, why in one sentence, and what the user
  can do instead. Compare against `knowledge/tone/`.
- A confirmation request restates the exact order and consequence before
  asking. "Cancel order 112-…, $149.99, not yet shipped. Confirm?"
- The agent never exposes tool names, JSON, or internal reasoning to the
  customer.
- Follow-ups with "it" or "that one" resolve to the right order (memory).
- Escalation tells the user what happens next and does not repeat.
- Replies are short. Flag any reply over about 80 words that is not a
  policy explanation.

## Checklist: terminal

- The trace is readable at a glance: step number, tool, arguments, result
  truncated sensibly.
- The customer-facing reply is visually separate from the trace.
- Startup tells the user what to do next (type a question, `/reset`, Ctrl+C).
- First-run downloads (the embedding model) announce themselves and their
  size before the wait.

## Report format

```
## UX review: <surface(s)>, <stage>

Walked: <what you actually did, with screenshot paths if any>

### Top findings
1. [Blocker] <one sentence>. `file:line`. Fix: <one sentence>.
2. [Major] ...
3. [Major] ...

### All findings
| # | Severity | Surface | Finding | Where | Fix |
|---|---|---|---|---|---|

### Contrast
| Text | Surface | Ratio | Needs | Pass |
|---|---|---|---|---|

### What already works
- <two or three things worth keeping, so a student knows what good looks like>
```

Keep findings to one sentence each. Every finding names a file and line, or
a transcript row id. A finding with no location is an opinion; leave it out
or label it "impression".
