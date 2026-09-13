# Design reference

The house style for anything this skill builds or fixes. Numbers here are
measured, not guessed; re-run the contrast check in the last section if you
change a value.

## Principles

1. **Dark by default.** Near-black surfaces, not pure black. Light is the
   exception, offered only when the user asks, and then both themes share
   the same tokens.
2. **Contrast is a hard gate.** Body text at least 7:1 (AAA) on its surface.
   Secondary text at least 4.5:1. Large text, icons and borders that carry
   meaning at least 3:1. Fail any of these and the design is not done,
   whatever it looks like.
3. **One typeface for reading, one for code.** Both from Google Fonts,
   both with a real fallback stack. Never more than two families on a page.
4. **One framework.** A page is either plain CSS with custom properties, or
   one utility framework. Never both, and never a second framework added
   for one component. This project is plain CSS with tokens in `:root`;
   keep it that way.
5. **Hierarchy from spacing and weight, not colour.** Colour marks state
   (ok, warning, error, accent). Everything else is grey scale and size.
6. **Quiet motion.** 120 to 200 ms transitions on hover and focus only.
   No entrance animations, no bouncing dots; a thinking state is a subtle
   pulse or a static label.
7. **Restraint is the taste.** One accent. One radius. One shadow, or
   none. If a screen looks busy, remove before you add.

## Palette

Tokens go in `:root`. The current `ui/chat.html` already uses this scheme;
the ratios are against the surface each token is meant to sit on.

| Token | Value | Role | Contrast on `--bg` | on `--panel` |
|---|---|---|---|---|
| `--bg` | `#0f1115` | page ground | | |
| `--panel` | `#171a21` | cards, sidebars | | |
| `--line` | `#2a2f3a` | borders, dividers | | |
| `--txt` | `#e6e8ee` | body text | 15.4 | 14.2 |
| `--dim` | `#9aa3b2` | secondary text, labels | 7.4 | 6.8 |
| `--accent` | `#ff9900` | one accent: brand, primary action, links | 8.8 | 8.1 |
| `--ok` | `#4ade80` | success | 10.8 | 10.0 |
| `--err` | `#f87171` | error, refusal | 6.8 | 6.3 |

Rules for using it:

- Text on `--accent` is `--bg`, not white. Orange on white fails; dark on
  orange passes at 8.8:1. White on orange is 2.1:1 and fails.
- `--line` is for borders only. It is 1.4:1 against `--bg` and must never
  carry text or meaning; it is a divider, not a signal.
- Hover states lighten a surface by one step, never change hue.
- Never use pure `#000` or pure `#fff`. Pure white text on near-black
  glares; `--txt` is deliberately a little grey.
- Status colours appear on a dot, a border or a short label, never as the
  background of a block of text.

If a design needs a second neutral step, derive it: `--panel-2: #1d2230`
(cards on a panel) and `--input: #12151c` (fields, one step darker than
the panel so they read as recessed).

## Type

Load from Google Fonts with `display=swap`, and always give the fallback:

| Role | Font | Fallback | Why |
|---|---|---|---|
| UI and reading | Inter | `system-ui, -apple-system, "Segoe UI", sans-serif` | neutral, excellent at 13 to 16 px, tabular figures available |
| Code, traces, logs | JetBrains Mono | `ui-monospace, "SF Mono", Menlo, monospace` | clear 0/O and 1/l, comfortable at 12 px |

Acceptable alternatives when the user wants a different voice, still one
of each:

- Reading: IBM Plex Sans (more character), Source Sans 3 (quieter),
  Manrope (rounder, for consumer-facing).
- Code: IBM Plex Mono (pairs with Plex Sans), Fira Code (if ligatures are
  wanted; usually they are not in a log view).

Scale, in px, with line height:

```
12/16   captions, timestamps, --dim
13/18   dense UI: log rows, tool traces, sidebars
14/20   default body
16/24   chat bubbles, anything the customer reads
20/28   page title, weight 600
```

No weight above 600. Use 500 for emphasis inside UI text, 600 for
headings, 400 for everything else. Letter-spacing stays at 0 except
uppercase labels, which get `0.04em` and never exceed 12 px.

## Layout and shape

- Spacing scale: 4, 8, 12, 16, 24, 32. Nothing in between.
- One radius for the whole page: 6 px for controls and cards. 12 px only
  for chat bubbles. Never fully round rectangles.
- Borders: 1 px `--line`. No 2 px borders; use a background step instead.
- Shadows: none on dark surfaces. Depth comes from the surface step.
- Max reading width 68 ch for prose. Chat bubbles cap at 75% of the column.
- Two-column layouts split 55/45, not 50/50; the primary task gets more.

## Components

Buttons
- Primary: `--accent` background, `--bg` text, weight 500, 8 px 14 px
  padding, radius 6.
- Secondary: transparent, 1 px `--line` border, `--txt` text. Hover: border
  becomes `--accent`.
- Disabled: 40% opacity, `cursor: not-allowed`, and still readable.
- Focus: 2 px outline in `--accent` with 2 px offset. Never remove outlines.

Inputs
- `--input` background, 1 px `--line` border, `--txt` text, `--dim`
  placeholder (placeholder is 7.2:1 against `--input`, verified).
- Focus: border `--accent`. No glow.

Status
- A 8 px dot before the label, colour from `--ok` / `--accent` / `--err`,
  plus the word. The word is what a screen reader gets; the dot is decor.

Chat
- The user's bubble is one surface step lighter than the agent's; the agent
  bubble has a `--line` border, the user's has none. Author label 11 px
  `--dim` above each. Reply text 16/24.

Logs and traces
- Monospace 13/18, `--dim` for keys, `--txt` for values, `--accent` for
  cost and the tool name. Rows separated by 1 px `--line`, no zebra.

## Starter stylesheet

Drop-in for a new page in this project. Everything above, as CSS.

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:#0f1115; --panel:#171a21; --panel-2:#1d2230; --input:#12151c;
    --line:#2a2f3a; --txt:#e6e8ee; --dim:#9aa3b2;
    --accent:#ff9900; --ok:#4ade80; --err:#f87171;
    --sans: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
    --mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;
    --radius: 6px;
    color-scheme: dark;
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font: 400 14px/20px var(--sans); }
  code, pre, .mono { font: 400 13px/18px var(--mono); }
  button { font: 500 14px/20px var(--sans); padding:8px 14px; border-radius:var(--radius);
           border:1px solid var(--line); background:transparent; color:var(--txt);
           cursor:pointer; transition: border-color 150ms, background 150ms; }
  button:hover { border-color:var(--accent); }
  button.primary { background:var(--accent); border-color:var(--accent); color:var(--bg); }
  button:disabled { opacity:.4; cursor:not-allowed; }
  :focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
  input, textarea { font:inherit; background:var(--input); color:var(--txt);
           border:1px solid var(--line); border-radius:var(--radius); padding:8px 12px; }
  input::placeholder, textarea::placeholder { color:var(--dim); }
  input:focus, textarea:focus { border-color:var(--accent); outline:none; }
  .dim { color:var(--dim); }
  .label { font-size:12px; line-height:16px; letter-spacing:.04em; text-transform:uppercase; color:var(--dim); }
</style>
```

## Contrast check

Run this before signing off on any colour change. WCAG needs 4.5 for
normal text, 3 for large text and UI parts; this house style asks 7 for
body text.

```python
def lum(h):
    h = h.lstrip("#"); r, g, b = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def contrast(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)

for fg, bg in [("#e6e8ee", "#0f1115"), ("#9aa3b2", "#171a21"), ("#0f1115", "#ff9900")]:
    print(fg, "on", bg, contrast(fg, bg))
```

Put the numbers in the review report. A colour with no number next to it
has not been checked.
