"""The same Checkpoint miss, answered three ways: one chain, three Watchers.

    python docs/figures/make_error_paths.py

The chain is read from the approved artifact; each branch's Condition and reaction from
the Watcher that fires, in the artifact or the App Profile. The members are the fake
bank's scenario members (fake_bank/data.py): 99999 is absent, 88888 expires the session
once, 44444 is flagged for supervisor approval.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ART = yaml.safe_load((ROOT / "artifacts" / "read_savings_balance.1.0.0.yaml").read_text())
PROFILE = yaml.safe_load((ROOT / "config" / "profiles" / "demo-core-servicing.yaml").read_text())
OUT = Path(__file__).resolve().parent / "error_paths.svg"

INK, MUTED = "#1a1a1a", "#6f6f6f"
BLUE, BLUE_BG = "#2f5597", "#e8edf6"
GREEN, GREEN_BG = "#1b7450", "#e4f2ec"
AMBER, AMBER_BG = "#9a6a12", "#faf0d8"
RED, RED_BG = "#a8251e", "#fae9e6"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

W, H = 1240, 300
BOX_W, BOX_H, GAP, X0, Y0 = 156, 40, 16, 30, 40
out = []
add = out.append


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, *, size=11, fill=INK, font=SANS, weight="normal", anchor="middle",
         style="normal"):
    add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" font-style="{style}" text-anchor="{anchor}">{esc(s)}</text>')


def arrow(d, color=INK, dash=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<path d="{d}" stroke="{color}" stroke-width="1.4" fill="none" '
        f'marker-end="url(#h{color[1:]})"{dd}/>')


def box(x, y, w, h, title, sub=None, *, fg=BLUE, bg=BLUE_BG, mono=True):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{bg}" stroke="{fg}" '
        f'stroke-width="1.5"/>')
    if sub:
        text(x + w / 2, y + 17, title, size=11, weight="600", font=MONO if mono else SANS)
        text(x + w / 2, y + 32, sub, size=10, fill=fg)
    else:
        text(x + w / 2, y + h / 2 + 4, title, size=10, weight="600", font=MONO if mono else SANS)


watchers = {w["id"]: w for w in PROFILE["watchers"]}
watchers.update({w["id"]: w for w in ART["watchers"]})
transitions = ART["transitions"]
order = [t["from_state"] for t in transitions] + [transitions[-1]["to_state"]]
terminal = {s["id"] for s in ART["states"] if s.get("terminal")}
MISS_AT = 5                                   # index of the State whose Checkpoint misses

# the three scenario members and the Watcher each one triggers
SCENARIOS = [
    ("99999", "w_not_found",         ["stop, tell the caller", "MEMBER_NOT_FOUND"]),
    ("88888", "w_session_expired",   ["which State holds now?", "s1_login: run the chain again"]),
    ("44444", "w_approval_required", ["Operator acts in the live session", "resume at s6 once it holds"]),
]
CONDITION = {"business_outcome": "Business Outcome", "recoverable": "Recoverable",
             "escalate": "Escalate", "hard_failure": "Hard Failure"}

add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
    f'height="{H}" font-family="{SANS}">')
add("<defs>")
for c in (INK, RED, GREEN, BLUE, AMBER):
    add(f'<marker id="h{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" '
        f'fill="{c}"/></marker>')
add("</defs>")
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

# the chain, once
xs = []
for i, sid in enumerate(order):
    x = X0 + i * (BOX_W + GAP)
    xs.append(x)
    fg, bg = (GREEN, GREEN_BG) if sid in terminal else (BLUE, BLUE_BG)
    box(x, Y0, BOX_W, BOX_H, sid, fg=fg, bg=bg)
    if i < len(transitions):
        x1, x2, ym = x + BOX_W + 3, x + BOX_W + GAP - 3, Y0 + BOX_H / 2
        if i + 1 == MISS_AT:
            arrow(f"M {x1} {ym} L {x2} {ym}", RED)
            text(x + BOX_W + GAP / 2, Y0 - 8, "✗ checkpoint misses", size=10, fill=RED, weight="600")
        else:
            arrow(f"M {x1} {ym} L {x2} {ym}")
text(xs[-1] + BOX_W, Y0 - 8, "12345: Succeeded, savings_balance", size=10, fill=GREEN, anchor="end")

# the fork: down from the missed arrow to a bus, then one drop per Watcher
fx = xs[MISS_AT - 1] + BOX_W + GAP / 2
BUS_Y = Y0 + 104
BW, BH, BY = 300, 42, Y0 + 140
bx = [X0 + 60, X0 + 60 + BW + 40, X0 + 60 + 2 * (BW + 40)]
mids = [x + BW / 2 for x in bx]
add(f'<path d="M {fx} {Y0 + BOX_H / 2 + 4} L {fx} {BUS_Y}" stroke="{RED}" stroke-width="1.4" '
    f'fill="none" stroke-dasharray="4 3"/>')
add(f'<path d="M {mids[0]} {BUS_Y} L {mids[-1]} {BUS_Y}" stroke="{RED}" stroke-width="1.4" '
    f'fill="none" stroke-dasharray="4 3"/>')
text(fx + 10, BUS_Y - 22, "which Watcher fires?", size=10.5, fill=RED, style="italic", anchor="start")

for (member, wid, reaction), x, mx in zip(SCENARIOS, bx, mids):
    w = watchers[wid]
    cond = w["condition"]
    fg, bg = {"business_outcome": (GREEN, GREEN_BG), "recoverable": (BLUE, BLUE_BG),
              "escalate": (AMBER, AMBER_BG)}[cond]
    arrow(f"M {mx} {BUS_Y} L {mx} {BY - 4}", fg)
    box(x, BY, BW, BH, wid, CONDITION[cond], fg=fg, bg=bg)
    text(mx, BY + BH + 16, reaction[0], size=10.5)
    text(mx, BY + BH + 31, reaction[1], size=10.5, font=MONO)
    text(mx, BY + BH + 48, f"member {member}", size=10, fill=MUTED)

# where the two runs that continue re-enter the chain: from a box corner, above the boxes
s1x, s6x = xs[0] + BOX_W / 2, xs[MISS_AT] + BOX_W / 2
LOOP_Y = BY - 14
arrow(f"M {bx[1] + 8} {BY} C {bx[1] - 80} {BY - 44}, {X0 - 10} {BY - 60}, {s1x} {Y0 + BOX_H + 4}", BLUE, dash="4 3")
arrow(f"M {bx[2] + BW - 8} {BY} C {bx[2] + BW + 60} {LOOP_Y}, {s6x + 90} {Y0 + BOX_H + 40}, {s6x} {Y0 + BOX_H + 4}", AMBER, dash="4 3")

add("</svg>")
OUT.write_text("\n".join(out) + "\n")
print(f"wrote {OUT}")
