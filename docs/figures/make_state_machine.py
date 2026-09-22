"""Draw an approved Artifact as a state machine, after PreAct's Figure 4.

    python docs/figures/make_state_machine.py

Reads the artifact and the App Profile, so the figure cannot drift from the thing it
describes. Nodes are States carrying the Checkpoint that must hold to believe we are
there; arrows are Transitions carrying an Action. Read the top row left to right, then
drop down and read the second row right to left.
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ARTIFACT = ROOT / "artifacts/open_sub_account.1.0.0.yaml"
PROFILE = ROOT / "config/profiles/demo-core-servicing.yaml"
OUT = Path(__file__).resolve().parent / "open_sub_account.svg"

INK, MUTED, RULE = "#1a1a1a", "#6f6f6f", "#d4d2cc"
BLUE, BLUE_BG = "#2b5fd9", "#eaf0fd"
GREEN, GREEN_BG = "#1b7450", "#e4f2ec"
AMBER, AMBER_BG = "#a1670a", "#fbf0d9"
RED, RED_BG = "#a8251e", "#fae9e6"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

W, H = 1240, 730
NODE_W, NODE_H = 240, 78
ROW_Y = [168, 412]
COL_X = [58, 500, 942]

out = []
add = out.append


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text(x, y, s, *, size=12, fill=INK, font=SANS, weight="normal", anchor="start"):
    add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')


def node(x, y, state, terminal=False):
    fill, stroke = (GREEN_BG, GREEN) if terminal else ("#ffffff", BLUE)
    add(f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="9" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="1.6"/>')
    text(x + 14, y + 27, state["id"], size=14.5, font=MONO, weight="600",
         fill=GREEN if terminal else INK)
    cp = state["checkpoint"]
    what = cp.get("target") or cp.get("value")
    text(x + 14, y + 48, cp["type"], size=10.5, font=MONO, fill=MUTED)
    text(x + 14, y + 64, what, size=10.5, font=MONO, fill=stroke)
    if terminal:
        text(x + NODE_W - 12, y + 27, "terminal", size=10.5, fill=GREEN,
             weight="600", anchor="end")


def arrow(x1, y1, x2, y2, *, color=MUTED, width=1.6, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<path d="M {x1} {y1} L {x2} {y2}" stroke="{color}" stroke-width="{width}" '
        f'fill="none" marker-end="url(#a{color[1:]})"{d}/>')


def self_loop(cx, top, actions):
    """One arc above a node, listing the Actions that do not leave the State."""
    add(f'<path d="M {cx - 34} {top} C {cx - 34} {top - 46}, {cx + 34} {top - 46}, '
        f'{cx + 34} {top - 3}" stroke="{MUTED}" stroke-width="1.5" fill="none" '
        f'marker-end="url(#a{MUTED[1:]})"/>')
    for i, label in enumerate(actions):
        text(cx, top - 58 - (len(actions) - 1 - i) * 15, label, size=11, font=MONO,
             fill=INK, anchor="middle")


def label(x, y, lines, color=INK, size=10.5, anchor="middle"):
    for i, line in enumerate(lines):
        text(x, y + i * 14, line, size=size, font=MONO, fill=color, anchor=anchor)


def act_label(action):
    value = (action.get("value")
             or (f"secret:{action['value_ref']}" if action.get("value_ref") else None)
             or (f"→ {action['into']}" if action.get("into") else ""))
    return f"{action['type']} {action['target']}".strip(), value


# ── read the real thing ─────────────────────────────────────────────────────
art = yaml.safe_load(ARTIFACT.read_text())
profile = yaml.safe_load(PROFILE.read_text())
states = {s["id"]: s for s in art["states"]}
order = [s["id"] for s in art["states"]]
pos = {}                       # state id -> (x, y), snaking
for i, sid in enumerate(order):
    row, col = divmod(i, 3)
    pos[sid] = (COL_X[col] if row == 0 else COL_X[2 - col], ROW_Y[row])

add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
    f'height="{H}" font-family="{SANS}">')
add('<defs>')
for c in (MUTED, RED, GREEN, BLUE, AMBER):
    add(f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{c}"/></marker>')
add('</defs>')
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

cap = art["capability"]
text(58, 44, f'{cap["id"]}@{cap["version"]}', size=17, weight="700")
text(58, 66, f'role {cap["role"]}  ·  {cap["status"]}, approved by '
             f'{len(cap["approvals"])}  ·  {len(art["states"])} states, '
             f'{len(art["transitions"])} transitions', size=11.5, fill=MUTED)
text(W - 58, 44, "each node carries the Checkpoint that must hold to believe we are there",
     size=11, fill=MUTED, anchor="end")
text(W - 58, 62, "read the top row left to right, then drop down and read back",
     size=11, fill=MUTED, anchor="end")

# self-loops first, so arrows draw over nothing
loops = {}
for t in art["transitions"]:
    if t["from_state"] == t["to_state"]:
        name, value = act_label(t["action"])
        loops.setdefault(t["from_state"], []).append(f"{name}  {value}".rstrip())
for sid, actions in loops.items():
    x, y = pos[sid]
    self_loop(x + NODE_W / 2, y, actions)

for sid in order:
    x, y = pos[sid]
    node(x, y, states[sid], terminal=bool(states[sid].get("terminal")))

for t in art["transitions"]:
    a, b = t["from_state"], t["to_state"]
    if a == b:
        continue
    (x1, y1), (x2, y2) = pos[a], pos[b]
    name, value = act_label(t["action"])
    risky = t["risk"] == "consequential"
    colour = RED if risky else MUTED
    if y1 == y2:                                   # along a row
        left_to_right = x2 > x1
        sx = x1 + NODE_W if left_to_right else x1
        ex = x2 if left_to_right else x2 + NODE_W
        arrow(sx + 4, y1 + NODE_H / 2, ex - 4 if left_to_right else ex + 4,
              y1 + NODE_H / 2, color=colour)
        mid = (sx + ex) / 2
        label(mid, y1 + NODE_H / 2 - 22, [name], colour)
        if risky:
            label(mid, y1 + NODE_H / 2 + 22,
                  ["consequential", "verify_effect:", "text_present {{nickname}}"], RED)
    else:                                          # the wrap between rows
        cx = x1 + NODE_W / 2
        arrow(cx, y1 + NODE_H + 4, cx, y2 - 6, color=colour)
        label(cx - 14, y1 + NODE_H + 34, [name], colour, anchor="end")

# ── watchers: global, so a band rather than an edge ─────────────────────────
band_y = 556
add(f'<rect x="58" y="{band_y}" width="{W - 116}" height="130" rx="9" fill="{AMBER_BG}" '
    f'stroke="{AMBER}" stroke-width="1.3" stroke-dasharray="5 4"/>')
for sid in order:
    x, y = pos[sid]
    if y == ROW_Y[1]:
        arrow(x + NODE_W / 2, band_y - 4, x + NODE_W / 2, y + NODE_H + 6,
              color=AMBER, width=1.2, dash="4 4")
text(74, band_y + 25, "Watchers — evaluated at every State, so they belong to none of them",
     size=12.5, weight="700", fill=AMBER)

own = art.get("watchers", [])
shared = profile.get("watchers", [])
CONDITION_COLOUR = {"business_outcome": GREEN, "recoverable": BLUE,
                    "escalate": AMBER, "hard_failure": RED}
own_ids = {w["id"] for w in own}
# An Artifact's own Watcher wins when both match the same screen, so a Profile watcher
# of the same id is shadowed — shown, because a reader should see it was considered.
chips = ([(w["id"], w["condition"], "artifact", False) for w in own]
         + [(w["id"], w["condition"], "App Profile", w["id"] in own_ids) for w in shared])
per_row = 4
cw = (W - 148) / per_row
for i, (wid, condition, source, shadowed) in enumerate(chips):
    row, col = divmod(i, per_row)
    cx = 74 + col * cw
    cy = band_y + 38 + row * 46
    colour = MUTED if shadowed else CONDITION_COLOUR.get(condition, MUTED)
    add(f'<rect x="{cx}" y="{cy}" width="{cw - 12}" height="38" rx="6" '
        f'fill="#ffffff" stroke="{colour}" stroke-width="1.3" '
        f'{"stroke-dasharray=\"4 3\"" if shadowed else ""}/>')
    text(cx + 10, cy + 16, wid, size=10.5, font=MONO, fill=MUTED if shadowed else INK)
    text(cx + 10, cy + 31, condition, size=9.5, fill=colour, weight="600")
    text(cx + cw - 22, cy + 31,
         "shadowed by artifact" if shadowed else source, size=9, fill=MUTED, anchor="end")

text(58, H - 14,
     "Generated from artifacts/open_sub_account.1.0.0.yaml and "
     "config/profiles/demo-core-servicing.yaml by docs/figures/make_state_machine.py",
     size=9.5, fill=MUTED)
add('</svg>')

OUT.write_text("\n".join(out))
print(f"wrote {OUT.relative_to(ROOT)}  ({len(order)} states, "
      f"{len(art['transitions'])} transitions, {len(chips)} watchers)")
