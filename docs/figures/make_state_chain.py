"""One capability as its state machine, after PreAct's Figure 4.

    python docs/figures/make_state_chain.py

Read from the approved artifact, so it cannot drift. A box holds a State's name, an arrow
holds the Action that moves between them; the Checkpoints are in the artifact listing,
as PreAct keeps its predicates in Listing 1. Read the top row left to right, then the
bottom row right to left.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "artifacts" / "read_savings_balance.1.0.0.yaml"
OUT = Path(__file__).resolve().parent / "state_chain.svg"

INK, MUTED = "#1a1a1a", "#6f6f6f"
BLUE, BLUE_BG = "#2f5597", "#e8edf6"
GREEN, GREEN_BG = "#1b7450", "#e4f2ec"
AMBER, AMBER_BG = "#9a6a12", "#faf0d8"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

W, H = 1240, 385
BOX_W, BOX_H, GAP, X0, ROW1, ROW2, PER_ROW = 200, 54, 100, 60, 80, 240, 4
CP_H, CP_DY = 24, 6      # the checkpoint box under each state
out = []
add = out.append


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, *, size=12, fill=INK, font=SANS, weight="normal", anchor="middle",
         style="normal"):
    add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" font-style="{style}" text-anchor="{anchor}">{esc(s)}</text>')


def arrow(x1, y1, x2, y2):
    add(f'<path d="M {x1} {y1} L {x2} {y2}" stroke="{INK}" stroke-width="1.4" fill="none" '
        f'marker-end="url(#head)"/>')


art = yaml.safe_load(SRC.read_text())
targets = art["targets"]
states = {s["id"]: s for s in art["states"]}
transitions = art["transitions"]
order = [t["from_state"] for t in transitions] + [transitions[-1]["to_state"]]
terminal = {s["id"] for s in art["states"] if s.get("terminal")}


def checkpoint_question(cp):
    if cp["type"] == "element_present":
        return f"{cp['target']} on screen?"
    if cp["type"] == "field_value":
        return f"{cp['target']} non-empty?"
    return f"{cp['type']}?"


def action_label(t):
    a = t["action"]
    if a["type"] == "type":
        return [f"type {a.get('value_ref') or a['value'].strip('{}')}"]
    if a["type"] == "select":
        return [f"select {a['value'].strip('{}')}"]
    if a["type"] == "read":
        return [f"read {a['into']}"]
    rungs = targets[a["target"]]["rungs"]
    named = next((r for r in rungs if r["kind"] == "role_name"), None)
    if named:
        return [f"click '{named['name']}'"]
    anchored = next((r for r in rungs if r["kind"] == "label_anchor"), None)
    if anchored:                       # no accessible name: the control is found by its caption
        return [f"click the {anchored['role']}", f"beside '{anchored['anchor']}'"]
    return [f"click {a['target']}"]


def slot(i):
    """Box position: top row left to right, bottom row right to left."""
    if i < PER_ROW:
        return X0 + i * (BOX_W + GAP), ROW1
    col = PER_ROW - 1 - (i - PER_ROW)
    return X0 + col * (BOX_W + GAP), ROW2


add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
    f'height="{H}" font-family="{SANS}">')
add(f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
    f'markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" '
    f'fill="{INK}"/></marker></defs>')
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

# key: what a box and an arrow mean
add(f'<rect x="{X0}" y="26" width="52" height="20" rx="4" fill="{BLUE_BG}" stroke="{BLUE}" '
    f'stroke-width="1.2"/>')
text(X0 + 26, 40, "state", size=11, fill=BLUE)
arrow(X0 + 72, 36, X0 + 120, 36)
text(X0 + 96, 30, "action", size=11, style="italic")
add(f'<rect x="{X0 + 140}" y="26" width="76" height="20" rx="4" fill="{AMBER_BG}" stroke="{AMBER}" '
    f'stroke-width="1"/>')
text(X0 + 178, 40, "checkpoint", size=11, fill=AMBER)

for i, sid in enumerate(order):
    x, y = slot(i)
    fg, bg = (GREEN, GREEN_BG) if sid in terminal else (BLUE, BLUE_BG)
    add(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="5" fill="{bg}" '
        f'stroke="{fg}" stroke-width="1.5"/>')
    text(x + BOX_W / 2, y + BOX_H / 2 + 4, sid, size=12.5, weight="600", font=MONO)
    cy = y + BOX_H + CP_DY
    add(f'<rect x="{x}" y="{cy}" width="{BOX_W}" height="{CP_H}" rx="4" fill="{AMBER_BG}" '
        f'stroke="{AMBER}" stroke-width="1"/>')
    text(x + BOX_W / 2, cy + 16, checkpoint_question(states[sid]["checkpoint"]), size=10.5,
         fill=AMBER, font=MONO)
    if i >= len(transitions):
        continue
    lines = action_label(transitions[i])
    nx, ny = slot(i + 1)

    def label(cx, cy, anchor="middle", lines=lines):
        for k, line in enumerate(lines):
            text(cx, cy + k * 14, line, size=11, style="italic", anchor=anchor)

    if ny == y and nx > x:                       # top row, rightwards: label above
        arrow(x + BOX_W + 4, y + BOX_H / 2, nx - 4, y + BOX_H / 2)
        label((x + BOX_W + nx) / 2, y - 10 - 14 * (len(lines) - 1))
    elif ny == y:                                # bottom row, leftwards: label below
        arrow(x - 4, y + BOX_H / 2, nx + BOX_W + 4, y + BOX_H / 2)
        label((x + nx + BOX_W) / 2, y - 10 - 14 * (len(lines) - 1))
    else:                                        # the turn down at the end of the top row
        cx = x + BOX_W / 2
        top = y + BOX_H + CP_DY + CP_H + 4
        arrow(cx, top, cx, ny - 4)
        label(cx + 12, (top + ny) / 2 + 4, anchor="start")

add("</svg>")
OUT.write_text("\n".join(out) + "\n")
print(f"wrote {OUT}")
