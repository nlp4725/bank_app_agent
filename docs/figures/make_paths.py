"""The same state machine, four runs: where the Checkpoint failed, which Watcher
answered, where the run re-entered. Drawn from real trails, not by hand.

    python docs/figures/make_paths.py            # needs the demo app on :5001

Replays member.read_savings_balance for four members against the demo app and draws
each run's path over the same chain of States. A run that never leaves the chain is
the happy path; the other three show the three ways a Checkpoint miss is answered —
a Business Outcome (stop, it is the answer), a Recoverable (fix it, re-orient, carry
on) and an Escalate (a person acts in the live session, the run resumes). This is the
state-machine claim demonstrated: position is a claim about the screen, so the run can
re-enter anywhere a claim holds.
"""

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from cua.replay import RunContext, replay                      # noqa: E402
from cua.governance.store import load_capability, origin_for               # noqa: E402
from tools.replay.make_evidence import clears_the_flag               # noqa: E402

CAPABILITY = "member.read_savings_balance"
OUT = Path(__file__).resolve().parent / "read_savings_balance_paths.svg"

INK, MUTED, RULE = "#1a1a1a", "#6f6f6f", "#d4d2cc"
BLUE, BLUE_BG = "#2b5fd9", "#eaf0fd"
GREEN, GREEN_BG = "#1b7450", "#e4f2ec"
AMBER, AMBER_BG = "#a1670a", "#fbf0d9"
RED, RED_BG = "#a8251e", "#fae9e6"
GREY_BG = "#f2f1ee"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
CONDITION = {"business_outcome": GREEN, "recoverable": BLUE, "escalate": AMBER,
             "hard_failure": RED}

RUNS = [
    ("12345", "the happy path", {}),
    ("99999", "a Business Outcome: the app's legitimate answer", {}),
    ("88888", "a Recoverable: the session expires, the engine signs in again", {}),
    ("44444", "an Escalate: a supervisor acts in the live session",
     {"attended": True, "operator": clears_the_flag}),
]

W = 1240
X0, NODE_W, NODE_H, GAP = 58, 148, 44, 14
PANEL_H = 250
out = []
add = out.append


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, *, size=11, fill=INK, font=SANS, weight="normal", anchor="start"):
    add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')


def arrow(x1, y1, x2, y2, *, color=MUTED, width=1.5, dash=None, curve=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    path = (f"M {x1} {y1} C {curve[0]} {curve[1]}, {curve[2]} {curve[3]}, {x2} {y2}"
            if curve else f"M {x1} {y1} L {x2} {y2}")
    add(f'<path d="{path}" stroke="{color}" stroke-width="{width}" fill="none" '
        f'marker-end="url(#a{color[1:]})"{d}/>')


def chip(x, y, w, h, title, sub, colour, bg="#ffffff"):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{bg}" '
        f'stroke="{colour}" stroke-width="1.4"/>')
    text(x + 10, y + 17, title, size=10.5, font=MONO, weight="600")
    text(x + 10, y + 31, sub, size=9.5, fill=colour, weight="600")


# ── run the four members for real ───────────────────────────────────────────
art = load_capability(CAPABILITY)
origin = origin_for("bank_a", art.capability.vendor_app)
order = [s.id for s in art.states]
results = []
for member, caption, extra in RUNS:
    urllib.request.urlopen(f"{origin}/reset", timeout=5).read()
    r = replay(art, {"member_number": member},
               RunContext(origin=origin, evidence_root=str(ROOT / "runs"), **extra))
    results.append((member, caption, r))
    print(f"  {member}: {r}")


def passes(trail):
    """The States a run visited, split into passes: a re-entry starts a new pass."""
    runs, current, miss, watcher, human = [[]], [], None, None, None
    for e in trail:
        kind = e["event"]
        if kind == "about_to" and e["step"] not in runs[-1]:
            runs[-1].append(e["step"])
        elif kind == "checkpoint_missed":
            miss = (runs[-1][-1] if runs[-1] else order[0], e["step"])
        elif kind == "watcher_matched":
            watcher = (e["watcher"], e["condition"])
        elif kind == "operator_acted":
            human = e["by"]
        elif kind in ("reoriented", "resumed"):
            runs.append([e["step"]])
        elif kind == "result" and e.get("status") == "succeeded":
            runs[-1].append(order[-1])          # reached, never left
    return runs, miss, watcher, human


H = 96 + PANEL_H * len(results) + 30
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
    f'height="{H}" font-family="{SANS}">')
add("<defs>")
for c in (MUTED, RED, GREEN, BLUE, AMBER, INK):
    add(f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{c}"/></marker>')
add("</defs>")
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
text(58, 44, f"{art.capability.id}@{art.capability.version} — the same chain, four runs",
     size=17, weight="700")
text(58, 66, "drawn from the trails of four real replays with no model: where the Checkpoint "
             "failed, which Watcher answered, where the run re-entered", size=11.5, fill=MUTED)

xs = {sid: X0 + i * (NODE_W + GAP) for i, sid in enumerate(order)}
for n, (member, caption, r) in enumerate(results):
    top = 96 + n * PANEL_H
    runs, miss, watcher, human = passes(r.trail)
    visited = {s for p in runs for s in p}
    text(58, top + 16, f"member {member} — {caption}", size=12.5, weight="700")
    ny = top + 30
    # the chain
    for i, sid in enumerate(order):
        x = xs[sid]
        seen = sid in visited
        terminal = bool(art.states[i].terminal)
        fill = (GREEN_BG if terminal and seen else BLUE_BG if seen else "#ffffff")
        stroke = GREEN if terminal and seen else BLUE if seen else RULE
        add(f'<rect x="{x}" y="{ny}" width="{NODE_W}" height="{NODE_H}" rx="7" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')
        text(x + 8, ny + 18, sid, size=9, font=MONO, weight="600",
             fill=INK if seen else MUTED)
        cp = art.states[i].checkpoint
        what = getattr(cp, "target", None) or getattr(cp, "value", "")
        text(x + 8, ny + 33, f"{cp.type}{' non_empty' if getattr(cp, 'non_empty', None) else ''}",
             size=8.5, font=MONO, fill=MUTED)
        if i + 1 < len(order):
            nxt = order[i + 1]
            failed_here = miss and miss[1] == nxt
            colour = RED if failed_here else (INK if nxt in visited else RULE)
            arrow(x + NODE_W + 3, ny + NODE_H / 2, xs[nxt] - 3, ny + NODE_H / 2, color=colour,
                  width=1.8 if failed_here else 1.4)
            if failed_here:
                text((x + NODE_W + xs[nxt]) / 2, ny + NODE_H / 2 - 8, "✕", size=13,
                     fill=RED, weight="700", anchor="middle")
    # what answered
    by = ny + NODE_H + 34
    if miss and watcher:
        mx = xs[miss[1]] - GAP / 2
        colour = CONDITION.get(watcher[1], MUTED)
        arrow(mx - 60, ny + NODE_H + 4, mx - 60, by - 4, color=colour, dash="4 3")
        chip(mx - 150, by, 180, 40, watcher[0], watcher[1], colour)      # ends at mx + 30
        rx = min(mx + 80, W - 58 - 270)            # keep the chip on the canvas
        if watcher[1] == "business_outcome":
            arrow(mx + 34, by + 20, rx - 4, by + 20, color=colour)
            chip(rx, by, 270, 40, f"result: {r.status}",
                 f"{(r.outcome or {}).get('code', '')}  → the caller", colour, GREEN_BG)
        elif watcher[1] == "recoverable":
            re_entry = runs[1][0] if len(runs) > 1 else order[0]
            arrow(mx - 150, by + 20, xs[re_entry] + NODE_W / 2, ny + NODE_H + 4, color=colour,
                  curve=(mx - 290, by + 40, xs[re_entry] + NODE_W / 2, by + 30))
            text(mx - 160, by + 58, f"re-oriented: {re_entry} holds → run it again",
                 size=9.5, fill=colour, anchor="end")
            chip(rx, by, 270, 40, f"result: {r.status}",
                 "second pass reaches the terminal State", colour, GREEN_BG)
        elif watcher[1] == "escalate":
            arrow(mx + 34, by + 20, rx - 4, by + 20, color=colour)
            chip(rx, by, 270, 40, "Operator acts in the same browser",
                 f"{human or 'operator'} — never what they typed", colour, AMBER_BG)
            re_entry = runs[1][0] if len(runs) > 1 else miss[1]
            arrow(rx + 135, by - 2, xs[re_entry] + NODE_W / 2, ny + NODE_H + 4, color=colour,
                  curve=(rx + 135, by - 30, xs[re_entry] + NODE_W / 2, by - 20))
            text(rx, by + 58, f"resumed at {re_entry}: the engine re-checks which Checkpoint holds "
                 f"→ {r.status}", size=9.5, fill=colour)
    else:
        chip(W - 58 - 270, by, 270, 40, f"result: {r.status}",
             ", ".join(f"{k}: {v}" for k, v in r.outputs.items()) or "", GREEN, GREEN_BG)
    if n < len(results) - 1:
        add(f'<line x1="58" y1="{top + PANEL_H - 12}" x2="{W - 58}" y2="{top + PANEL_H - 12}" '
            f'stroke="{RULE}" stroke-width="1"/>')

text(58, H - 12, "Generated by docs/figures/make_paths.py from four live replays of "
     "artifacts/read_savings_balance.1.0.0.yaml against fake_bank on :5001", size=9.5, fill=MUTED)
add("</svg>")
OUT.write_text("\n".join(out))
print(f"wrote {OUT.relative_to(ROOT)}")
