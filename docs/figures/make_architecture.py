"""The system architecture, drawn in the style of PreAct's Figure 2.

    python docs/figures/make_architecture.py

A boxed flow with labelled edges: a goal enters on the left, one model-driven phase
compiles a capability into the store, and every later invocation is served from the
store with no model in it. Red is a gate that can refuse; green is a person.
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent / "architecture.svg"

INK, MUTED = "#1a1a1a", "#6f6f6f"
BLUE, BLUE_BG = "#2f5597", "#e8edf6"
AMBER, AMBER_BG = "#9a6a12", "#faf0d8"
GREEN, GREEN_BG = "#1b7450", "#e4f2ec"
RED, RED_BG = "#a8251e", "#fae9e6"
GREY, GREY_BG = "#7a7a7a", "#f2f1ee"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

W, H = 1240, 520
out = []
add = out.append


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, *, size=12, fill=INK, font=SANS, weight="normal", anchor="start",
         style="normal"):
    add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" font-style="{style}" text-anchor="{anchor}">{esc(s)}</text>')


class Box:
    def __init__(self, x, y, w, h, title, sub=None, *, fg=BLUE, bg=BLUE_BG, mono=False,
                 mod=None):
        self.x, self.y, self.w, self.h = x, y, w, h
        add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{bg}" '
            f'stroke="{fg}" stroke-width="1.5"/>')
        cx = x + w / 2
        if sub and mod:
            # three lines: what it is, what it guarantees, which module does it
            text(cx, y + 22, title, size=13.5, weight="600", anchor="middle",
                 fill=INK, font=MONO if mono else SANS)
            text(cx, y + 38, sub, size=10.5, anchor="middle", fill=fg)
            text(cx, y + h - 9, mod, size=9.5, anchor="middle", fill=MUTED, font=MONO)
        elif sub:
            text(cx, y + h / 2 - 3, title, size=13.5, weight="600", anchor="middle",
                 fill=INK, font=MONO if mono else SANS)
            text(cx, y + h / 2 + 15, sub, size=10.5, anchor="middle", fill=fg)
        else:
            text(cx, y + h / 2 + 5, title, size=13.5, weight="600", anchor="middle",
                 fill=INK, font=MONO if mono else SANS)

    # anchors
    @property
    def left(self): return (self.x, self.y + self.h / 2)
    @property
    def right(self): return (self.x + self.w, self.y + self.h / 2)
    @property
    def top(self): return (self.x + self.w / 2, self.y)
    @property
    def bottom(self): return (self.x + self.w / 2, self.y + self.h)


def edge(a, b, *, color=INK, dash=None, width=1.4, gap=5):
    (x1, y1), (x2, y2) = a, b
    dx, dy = x2 - x1, y2 - y1
    n = max((dx * dx + dy * dy) ** 0.5, 1)
    x1, y1 = x1 + dx / n * gap, y1 + dy / n * gap
    x2, y2 = x2 - dx / n * gap, y2 - dy / n * gap
    d = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<path d="M {x1} {y1} L {x2} {y2}" stroke="{color}" stroke-width="{width}" '
        f'fill="none" marker-end="url(#h{color[1:]})"{d}/>')


def elabel(x, y, lines, *, color=INK, size=13, anchor="middle", style="italic"):
    for i, line in enumerate(lines):
        text(x, y + i * 15, line, size=size, fill=color, anchor=anchor, style=style)


add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
    f'height="{H}" font-family="{SANS}">')
add("<defs>")
for c in (INK, RED, GREEN, AMBER, MUTED, BLUE):
    add(f'<marker id="h{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{c}"/></marker>')
add("</defs>")
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

# a person, not a step: head, shoulders, a name underneath
class Person:
    def __init__(self, cx, y, label, *, color, w=110, h=78):
        self.x, self.y, self.w, self.h = cx - w / 2, y, w, h
        add(f'<circle cx="{cx}" cy="{y + 14}" r="11" fill="{color}"/>')
        add(f'<path d="M {cx - 22} {y + 52} C {cx - 22} {y + 30}, {cx + 22} {y + 30}, {cx + 22} {y + 52} Z" '
            f'fill="{color}"/>')
        text(cx, y + h - 6, label, size=13, weight="600", anchor="middle", fill=INK)
    left = Box.left; right = Box.right; top = Box.top; bottom = Box.bottom

# ── discovery lane: happens once ────────────────────────────────────────────
text(34, 42, "NON-PRODUCTION: RECORD (LLM)", size=12, weight="700", fill=MUTED)
goal = Box(30, 74, 130, 78, "Goal + Contract", fg=GREY, bg=GREY_BG)
disc = Box(250, 74, 150, 78, "Discovery Run", fg=AMBER, bg=AMBER_BG)
rec = Box(455, 74, 110, 78, "Recorder", fg=BLUE, bg=BLUE_BG)
gate = Person(645, 74, "Review Gate", color=RED, w=70)
verify = Box(745, 74, 130, 78, "Verify Replay", fg=BLUE, bg=BLUE_BG)
store = Box(945, 74, 150, 78, "Artifact Store", fg=AMBER, bg=AMBER_BG)

edge(goal.right, disc.left)
edge(disc.right, rec.left)
elabel(427, 96, ["trace"])
edge(rec.right, gate.left)
elabel(587, 96, ["draft"])
edge(gate.right, verify.left)
elabel(712, 96, ["candidate"])
edge(verify.right, store.left)
elabel(910, 96, ["passed"])

# ── replay lane: happens every time ─────────────────────────────────────────
text(34, 322, "PRODUCTION: REPLAY (DETERMINISTIC)", size=12, weight="700", fill=MUTED)
caller = Box(30, 352, 130, 78, "Calling Agent", fg=GREY, bg=GREY_BG)
engine = Box(250, 346, 236, 90, "Replay Engine", fg=BLUE, bg=BLUE_BG)
operator = Person(660, 352, "Operator", color=GREEN, w=70)

edge((caller.x + caller.w, 372), (engine.x, 372))
elabel(205, 346, ["typed", "inputs"], size=13)
add(f'<path d="M {engine.x} 410 L {caller.x + caller.w + 5} 410" stroke="{INK}" '
    f'stroke-width="1.4" fill="none" marker-end="url(#h{INK[1:]})"/>')
elabel(205, 432, ["one Run", "Result"], size=13)

edge((engine.x + engine.w, 372), (operator.x, 372), color=GREEN)
elabel(555, 360, ["escalate"], size=13)
add(f'<path d="M {operator.x} 410 L {engine.x + engine.w + 5} 410" stroke="{GREEN}" '
    f'stroke-width="1.4" fill="none" marker-end="url(#h{GREEN[1:]})"/>')
elabel(555, 432, ["resume"], size=13)

# the store serves replay: PreAct's dashed "retrieve on next invocation"
add(f'<path d="M {store.x + store.w / 2} {store.y + store.h} L {store.x + store.w / 2} 300 '
    f'L {engine.x + engine.w - 40} 300 L {engine.x + engine.w - 40} {engine.y - 5}" '
    f'stroke="{AMBER}" stroke-width="1.5" fill="none" stroke-dasharray="6 4" '
    f'marker-end="url(#h{AMBER[1:]})"/>')

# ── policy: one gate, both phases ───────────────────────────────────────────
# a check, not a step: a circle on the line between the two phases
PX, PY, PR = disc.x + disc.w / 2, 250, 34
add(f'<circle cx="{PX}" cy="{PY}" r="{PR}" fill="{RED_BG}" stroke="{RED}" stroke-width="1.5"/>')
text(PX, PY + 5, "Policy", size=13, weight="600", anchor="middle", fill=INK)
edge((PX, PY - PR), (PX, disc.y + disc.h), color=RED, dash="5 3")
edge((PX, PY + PR), (PX, engine.y), color=RED, dash="5 3")

add("</svg>")

OUT.write_text("\n".join(out))
print(f"wrote {OUT}")
