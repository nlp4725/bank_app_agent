"""One Transition of one replay, walked through the engine's six steps.

    python docs/figures/make_transition_walk.py

Three lanes: what the Artifact supplies, what the Replay Engine does, what the browser
or the Policy answers. The Transition is s4_search -> s5_member_number_entered of the
approved read-balance artifact, replayed for member 12345.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ART = yaml.safe_load((ROOT / "artifacts" / "read_savings_balance.1.0.0.yaml").read_text())
OUT = Path(__file__).resolve().parent / "transition_walk.svg"

INK, MUTED = "#1a1a1a", "#6f6f6f"
BLUE, BLUE_BG = "#2f5597", "#e8edf6"
AMBER, AMBER_BG = "#9a6a12", "#faf0d8"
GREY, GREY_BG = "#7a7a7a", "#f2f1ee"
RED, RED_BG = "#a8251e", "#fae9e6"
GREEN = "#1b7450"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

W, H = 1240, 330
X0, LANE_X, COL_W, COL_GAP = 30, 150, 172, 8
ROW_Y = {"step": 40, "artifact": 78, "engine": 150, "answer": 222}
ROW_H = 60
out = []
add = out.append

INDEX = 3                                     # s4_search -> s5_member_number_entered
MEMBER = "12345"
t = ART["transitions"][INDEX]
states = {s["id"]: s for s in ART["states"]}
frm, to = states[t["from_state"]], states[t["to_state"]]
target = ART["targets"][t["action"]["target"]]
rung = target["rungs"][0]


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, *, size=10.5, fill=INK, font=SANS, weight="normal", anchor="middle",
         style="normal"):
    add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" font-style="{style}" text-anchor="{anchor}">{esc(s)}</text>')


def cell(col, row, lines, *, fg, bg, mono=False):
    x = LANE_X + col * (COL_W + COL_GAP)
    y = ROW_Y[row]
    add(f'<rect x="{x}" y="{y}" width="{COL_W}" height="{ROW_H}" rx="5" fill="{bg}" '
        f'stroke="{fg}" stroke-width="1.2"/>')
    top = y + ROW_H / 2 - 7 * (len(lines) - 1) + 4
    for k, line in enumerate(lines):
        text(x + COL_W / 2, top + k * 14, line, size=10, font=MONO if mono else SANS)


def cp_question(cp):
    return f"{cp['target']} " + ("on screen?" if cp["type"] == "element_present" else "non-empty?")


STEPS = ["1 PRECONDITION", "2 RESOLVE", "3 POLICY", "4 RISK GATE", "5 ACT", "6 OBSERVE"]
value = t["action"]["value"]
artifact_says = [
    [f"from {t['from_state']}", "checkpoint:", cp_question(frm["checkpoint"])],
    [f"target {t['action']['target']}", f"rung 1: {rung['kind']}", f"{rung['relation']} '{rung['anchor']}'"],
    ["needs.pages /search", f"needs.actions {t['action']['type']}", "role balance_reader"],
    [f"risk: {t['risk']}"],
    [f"{t['action']['type']} {value}", f"into {t['action']['target']}"],
    [f"to {t['to_state']}", "checkpoint:", cp_question(to["checkpoint"])],
]
engine_does = [
    ["ask the browser", "whether it holds"],
    ["walk the ladder;", "log which rung matched"],
    ["Baseline ∩ Role ∩", "Tenant ∩ Needs", "for /search, type"],
    ["consequential?", "unattended without", "a Verification Check?"],
    [f"render {value}", f"→ {MEMBER}, type it"],
    ["ask the browser;", "else ask the Watchers;", "else Unknown State"],
]
answers = [
    ["yes: the field is", "on the page"],
    ["rung 1 matched", "(no accessible name;", "found by its caption)"],
    ["allowed", "(policy_allow logged)"],
    ["no gate: safe", "action"],
    ["keystrokes land", "in the field"],
    ["yes: field holds a", "value → next Transition"],
]
answer_fg = [GREY, GREY, RED, RED, GREY, GREY]
answer_bg = [GREY_BG, GREY_BG, RED_BG, RED_BG, GREY_BG, GREY_BG]

add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
    f'height="{H}" font-family="{SANS}">')
add(f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
    f'markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" '
    f'fill="{INK}"/></marker></defs>')
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

# lane labels
text(X0, ROW_Y["artifact"] + ROW_H / 2 + 4, "Artifact says", size=11, weight="700", fill=AMBER, anchor="start")
text(X0, ROW_Y["engine"] + ROW_H / 2 + 4, "Engine does", size=11, weight="700", fill=BLUE, anchor="start")
text(X0, ROW_Y["answer"] + ROW_H / 2 - 4, "Browser or", size=11, weight="700", fill=GREY, anchor="start")
text(X0, ROW_Y["answer"] + ROW_H / 2 + 10, "Policy answers", size=11, weight="700", fill=GREY, anchor="start")

for col, step in enumerate(STEPS):
    x = LANE_X + col * (COL_W + COL_GAP)
    text(x + COL_W / 2, ROW_Y["step"], step, size=11, weight="700")
    cell(col, "artifact", artifact_says[col], fg=AMBER, bg=AMBER_BG, mono=True)
    cell(col, "engine", engine_does[col], fg=BLUE, bg=BLUE_BG)
    cell(col, "answer", answers[col], fg=answer_fg[col], bg=answer_bg[col])
    if col < len(STEPS) - 1:
        ym = ROW_Y["engine"] + ROW_H / 2
        add(f'<path d="M {x + COL_W + 1} {ym} L {x + COL_W + COL_GAP - 1} {ym}" stroke="{INK}" '
            f'stroke-width="1.4" fill="none" marker-end="url(#head)"/>')

text(LANE_X, H - 14, f"Transition {t['from_state']} → {t['to_state']} of read_savings_balance 1.0.0, "
     f"replayed for member {MEMBER}. Every step is a question the engine asks; the Artifact never acts.",
     size=10, fill=MUTED, anchor="start")
add("</svg>")
OUT.write_text("\n".join(out) + "\n")
print(f"wrote {OUT}")
