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
    def __init__(self, x, y, w, h, title, sub=None, *, fg=BLUE, bg=BLUE_BG, mono=False):
        self.x, self.y, self.w, self.h = x, y, w, h
        add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{bg}" '
            f'stroke="{fg}" stroke-width="1.5"/>')
        cx = x + w / 2
        if sub:
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


def elabel(x, y, lines, *, color=INK, size=10.5, anchor="middle", style="italic"):
    for i, line in enumerate(lines):
        text(x, y + i * 13, line, size=size, fill=color, anchor=anchor, style=style)


add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
    f'height="{H}" font-family="{SANS}">')
add("<defs>")
for c in (INK, RED, GREEN, AMBER, MUTED, BLUE):
    add(f'<marker id="h{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{c}"/></marker>')
add("</defs>")
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

# ── discovery lane: happens once ────────────────────────────────────────────
text(34, 42, "RECORDED ONCE", size=10.5, weight="700", fill=MUTED)
goal = Box(30, 74, 168, 62, "Goal + Contract", "fixed by a Reviewer", fg=GREY, bg=GREY_BG)
disc = Box(250, 74, 196, 62, "Discovery Run", "the only model in the system",
           fg=AMBER, bg=AMBER_BG)
rec = Box(498, 74, 150, 62, "Recorder", "decides nothing", fg=BLUE, bg=BLUE_BG)
gate = Box(700, 74, 196, 62, "Review Gate", "a person decides", fg=RED, bg=RED_BG)
store = Box(948, 74, 176, 62, "Artifact Store", "versioned capabilities",
            fg=AMBER, bg=AMBER_BG)

edge(goal.right, disc.left)
edge(disc.right, rec.left)
elabel(472, 96, ["trace"])
edge(rec.right, gate.left)
elabel(674, 96, ["draft"])
edge(gate.right, store.left)
elabel(922, 96, ["approved"])

elabel(348, 160, ["non-production only", "(ADR 0003)"], color=AMBER, size=10)
elabel(798, 160, ["lint · verify-replay on unseen", "inputs · two approvals"],
       color=RED, size=10)

# the gate can refuse, and that is the interesting arrow
add(f'<path d="M 760 74 C 760 34, 590 34, 573 70" stroke="{RED}" stroke-width="1.4" '
    f'fill="none" marker-end="url(#h{RED[1:]})"/>')
elabel(666, 30, ["refused — it was, three times"], color=RED, size=10)

# ── replay lane: happens every time ─────────────────────────────────────────
text(34, 320, "REPLAYED EVERY TIME AFTER", size=10.5, weight="700", fill=MUTED)
caller = Box(30, 344, 168, 62, "Calling Agent", "the AI the member talks to",
             fg=GREY, bg=GREY_BG)
engine = Box(276, 336, 236, 78, "Replay Engine", "no model in the decision loop",
             fg=BLUE, bg=BLUE_BG)
app = Box(596, 344, 176, 62, "Legacy app", "one Surface module", fg=GREY, bg=GREY_BG)
operator = Box(858, 344, 190, 62, "Operator", "the tenant's own staff",
               fg=GREEN, bg=GREEN_BG)

edge(caller.right, (engine.x, 362))
elabel(237, 344, ["typed", "inputs"], size=10)
add(f'<path d="M {engine.x} 392 L {caller.x + caller.w + 5} 392" stroke="{INK}" '
    f'stroke-width="1.4" fill="none" marker-end="url(#h{INK[1:]})"/>')
elabel(237, 414, ["one Run", "Result"], size=10)

edge(engine.right, app.left)
elabel(554, 336, ["click · type", "select · read"], size=10)
add(f'<path d="M {app.x} 392 L {engine.x + engine.w + 5} 392" stroke="{MUTED}" '
    f'stroke-width="1.4" fill="none" marker-end="url(#h{MUTED[1:]})"/>')
elabel(554, 414, ["checkpoint after", "every action"], size=10, color=MUTED)

edge(app.right, operator.left, color=GREEN)
elabel(806, 334, ["escalate:", "the same live session"], size=10, color=GREEN)
add(f'<path d="M {operator.x} 392 C 800 440, 560 452, {engine.x + engine.w / 2} 420" '
    f'stroke="{GREEN}" stroke-width="1.4" fill="none" '
    f'marker-end="url(#h{GREEN[1:]})"/>')
elabel(690, 470, ["resume — the engine re-orients rather than assuming they finished"],
       size=10, color=GREEN)

# the store serves replay: PreAct's dashed "retrieve on next invocation"
add(f'<path d="M {store.x + store.w / 2} 136 L {store.x + store.w / 2} 250 '
    f'L {engine.x + engine.w / 2} 250 L {engine.x + engine.w / 2} {engine.y - 5}" '
    f'stroke="{AMBER}" stroke-width="1.5" fill="none" stroke-dasharray="6 4" '
    f'marker-end="url(#h{AMBER[1:]})"/>')
elabel(700, 243, ["invoked by name, with typed arguments — no model, no re-reasoning"],
       color=AMBER, size=10.5)

# ── policy: one gate, both phases ───────────────────────────────────────────
policy = Box(30, 196, 236, 66, "Policy", "Baseline ∩ Role ∩ Tenant ∩ Needs",
             fg=RED, bg=RED_BG)
edge(policy.top, (306, disc.y + disc.h), color=RED, dash="5 3")
edge(policy.bottom, (engine.x + 44, engine.y), color=RED, dash="5 3")
elabel(280, 222, ["checked in code before every action,"], color=RED, size=10,
       anchor="start")
elabel(280, 235, ["in both phases — never by instructing the model"], color=RED,
       size=10, anchor="start")

text(34, 502, "Every run writes redacted evidence to runs/<run_id>/trail.jsonl — the only "
              "record, and the one a Reviewer reads afterwards.", size=10.5, fill=MUTED)
text(W - 34, 502, "docs/figures/make_architecture.py", size=9.5, fill=MUTED, anchor="end")
add("</svg>")

OUT.write_text("\n".join(out))
print(f"wrote {OUT}")
